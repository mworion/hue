#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#
#  Copyright (C) 2014 Michael Würtenberger
#
#  Basiert aus der API 1.0 der Philips hue API spezifikation, die man unter
#  http://www.developers.meethue.com/documentation/lights-api finden kann
#  Die Umsetzung des plugings verwaltet auch hue lamps, die nicht im netzwerk
#  auftauchen (z.B. weil sie durch abschalten der Spannung nicht angemeldet sind)
#  diese können dann explizit eingeschatet werden  
#
#  problem ist, dass die hue nach on / off zwar diue farbwerte und auch die sättigung hält, 
#  aber die Helligkeit auf minimum setzt (0) 

import logging
import json
import http.client
import time
import threading
#import pydevd

logger = logging.getLogger('')

class HUE():

    def __init__(self, smarthome, hue_ip='Philips-hue', hue_user=None, hue_port=80, cycle=10):

#        pydevd.settrace('192.168.2.57')        
        # parameter zu übergabe aus der konfiguration pulgin.conf
        self._sh = smarthome
        self._hue_ip = hue_ip
        self._hue_user = hue_user
        # variablen zur steuerung des plugins
        # hier werden alle bekannte items für lampen eingetragen
        self._sendItems = {}
        self._listenItems = {}
        
        self._lampslock = threading.Lock()
     
        # hier ist die liste der einträge, für die der status auf listen gesetzt werden kann
        self._listenKeys = ['on', 'bri', 'sat', 'hue', 'reachable', 'effect', 'alert']
        # hier ist die liste der einträge, für die der status auf senden gesetzt werden kann
        self._sendKeys = ['on', 'bri', 'sat', 'hue', 'effect', 'alert']
        # hier ist die liste der einträge, für die ein dimmer DPT3 gesetzt werden kann
        self._dimmKeys = ['bri', 'sat', 'hue']
   
        # scheduler für das polling der status über die hue bridge
        self._sh.scheduler.add('hue-update', self._update_lamps, cycle=cycle)
        # anstossen des updates zu beginn
        self._sh.trigger('hue-update', self._update_lamps)

    def run(self):
        self.alive = True
        # if you want to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        self.alive = False

    def parse_item(self, item):
        # nur wenn eine hue id angegeben ist, wird referenziert, sonst ist die lmape ja nicht bekannt
        for itemChild in self._sh.find_children(item, 'hue_dim_max'):
            itemChild.add_method_trigger(self._dimmenDPT3)
        if 'hue_id' in item.conf:
            #auswertung und setzen der transition time der hue bridge
            if 'hue_transitionTime' in item.conf:
                transitionTime = float(item.conf['hue_transitionTime']) * 10.0
            else:
                transitionTime = 1.0
            item.transitionTime = int(transitionTime)
            # jetzt die auswertung der send funktionen
            if 'hue_send' in item.conf:
                if item.conf['hue_send'] in self._sendKeys:
                    # referenzkey erzeugen für die liste. er besteht aus den lampen id und dem state (send_key), der gesetzt werden kann
                    key = item.conf['hue_id'] + item.conf['hue_send'] 
                    self._sendItems[key] = item
            # jetzt die auswertung der listen funktionen
            if 'hue_listen' in item.conf:
                if item.conf['hue_listen'] in self._listenKeys:
                    # referenzkey erzeugen für die liste. er besteht aus den lampen id und dem state (send_key), der gesetzt werden kann
                    key = item.conf['hue_id'] + item.conf['hue_listen'] 
                    self._listenItems[key] = item
            # jetzt noch die installation der dimmroutine
            # rückgabe der update methode für das item. ist an dieser stelle das senden an die bridge
            # hier müssen wir ein children finden, dass die dimkonfig enthält
            return self.update_item
        else:
            return None

    def update_item(self, item, caller=None, source=None, dest=None):
        # methode, die bei einer änderung des items ausgerufen wird
        # wenn die änderung von aussen kommt, dann wird diese abgearbeitet
        # im konkreten fall heisst das, dass der aktuelle status der betroffene lampe komplett zusammengestellt wird
        # und anschliessen neu über die hue bridge gesetzt wird.
        if caller != 'HUE':
            # test aus die wertgrenzen, die die bridge verstehen kann
            value = item()
            if item.conf['hue_send'] =='bri':
                # bri darf zwischen 0 und 255 liegen
                if value > 255:
                    value = int(255)
                elif value < 0:
                    value = int(0)
                else:
                    value = int(value)
            if item.conf['hue_send'] =='sat':
                # sat darf zwischen 0 und 255 liegen
                if value > 255:
                    value = int(255)
                elif value < 0:
                    value = int(0)
                else:
                    value = int(value)
            if item.conf['hue_send'] =='hue':
                # sat darf zwischen 0 und 65535 liegen
                if value > 65535:
                    value = int(65535)
                elif value < 0:
                    value = int(0)
                else:
                    value = int(value)
            # da die hue den helligkeitswert bei on / off vergisst, setze ich den nach on wieder auf den wert, den ich ursprünglich hatte
            # wichtig dabei ist, dass bei brighness cache = on gesetzt wird.
            if (item.conf['hue_send'] == 'on') and (item.conf['hue_id'] + 'bri' in self._sendItems):
                # dann wird auch gleich dir bri mit gesetzt
                self._set_state(item.conf['hue_id'], {item.conf['hue_send']: value, 'bri': int(self._sendItems[(item.conf['hue_id']+ 'bri')]()) ,'transitiontime': item.transitionTime})
                
            elif (item.conf['hue_send'] == 'bri') and (item.conf['hue_id'] + 'on' in self._sendItems):
                # wenn ich dir brightness hochdimme und on = False, dann mache ich die lampe auch an !
                self._set_state(item.conf['hue_id'], {'on': True , item.conf['hue_send']: value, 'transitiontime': item.transitionTime})
                
            else:
                # ansonsten nur den wert
                self._set_state(item.conf['hue_id'], {item.conf['hue_send']: value, 'transitiontime': item.transitionTime})
            
    def _dimmenDPT3(self, item, caller=None, source=None, dest=None):
        #das ist die methode, die die DPT3 dimmnachrichten auf die dimmbaren hue items mapped
        # fallunterscheidung dimmen oder stop
        if caller != 'HUE':
            if item()[1] == 1:
                #dimmen
                if item()[0] == 1:
                    # hoch
                    item.return_parent().fade(float(item.conf['hue_dim_max']), float(item.conf['hue_dim_step']), float(item.conf['hue_dim_time']))
                else:
                    #runter
                    item.return_parent().fade(0, float(item.conf['hue_dim_step']), float(item.conf['hue_dim_time']))
            else:
                #stop, indem man einen wert setzt. da es nicht der gleiche wert sein darf, erst einmal +1, dann -1
                item.return_parent()(int(item.return_parent()()+1),'HUE_FADE')
                item.return_parent()(int(item.return_parent()()-1),'HUE_FADE')
                    
    def _request(self, path='', method='GET', data=None):
        # hue bridge mit einem http request abfragen
        connectionHueBridge = http.client.HTTPConnection(self._hue_ip)
        connectionHueBridge.request(method, "/api/%s%s" % (self._hue_user, path), data)
        responseRaw = connectionHueBridge.getresponse()
        connectionHueBridge.close()

        # rückmeldung 200 ist OK
        if responseRaw.status != 200:
            logger.error('Request failed')
            return None
        # lesen, decodieren nach utf-8 (ist pflicht nach der api definition philips) und in ein python objekt umwandeln
        responseJson = responseRaw.read().decode('utf-8')
        response = json.loads(responseJson)
        # fehlerauswertung der rückmeldung, muss noch vervollständigt werden
        if isinstance(response, list) and response[0].get('error', None):
            error = response[0]["error"]
            if error['type'] == 1:
                description = error['description']
                logger.error('Error: {0} (Need to specify correct hue user?)'.format(description))
            else:
                logger.error(error['description'])
            return None
        else:
            return response

    def _set_state(self, hueLampId, state):
        # hier erfolgt das setzen des status einer lampe
        # hier kommt der PUT request, um die stati an die hue bridge zu übertragen
        returnValues = self._request("/lights/%s/state" % hueLampId,"PUT", json.dumps(state))
        if returnValues == None:
            logger.warning('hue set state: keine return values')
            return
        # der aufruf liefert eine bestätigung zurück, was den numgesetzt werden konnte
        self._lampslock.acquire()   
        for hueObject in returnValues:
            for hueObjectStatus, hueObjectReturnString in hueObject.items():
                if hueObjectStatus == 'success':
                    for hueObjectReturnStringPath, hueObjectReturnStringValue in hueObjectReturnString.items():
                        hueObjectReturnStringPathItem = hueObjectReturnStringPath.split('/')[4]
                        # hier werden jetzt die bestätigten werte aus der rückübertragung im item gesetzt
                        # wir gehen durch alle listen items, um die zuordnung zu machen
                        for returnItem in self._listenItems:
                            # wenn ein listen item angelegt wurde und dafür ein status zurückkam
                            #verglichen wird mit dem referenzkey, der weiter oben aus lampid und state gebaut wurde
                            if returnItem == (hueLampId + hueObjectReturnStringPathItem):
                                # dafür wir der reale wert der hue bridge gesetzt
                                if returnItem == (hueLampId + 'on'):
                                    value = bool(hueObjectReturnStringValue)
                                elif (returnItem == (hueLampId + 'effect')) or (returnItem == (hueLampId + 'alert')):
                                    value = str(hueObjectReturnStringValue)
                                else:
                                    value = float(hueObjectReturnStringValue)
                                self._listenItems[returnItem](value,'HUE')
                else:
                    logger.warning('hue: {0}: {1}'.format(hueObjectStatus, hueObjectReturnString))
        self._lampslock.release()
        return

    def _update_lamps(self):
        # mache ich mit der API get all lights
        # hier kommt der PUT request, um die stati an die hue bridge zu übertragen beispiel:

        returnValues = self._request('/lights')
        if returnValues == None:
            return
        # schleife über alle gefundenen lampen
        self._lampslock.acquire()
        for hueLampId, hueLampIdValues in returnValues.items():
            # schleife über alle states in den lampen
            for hueObjectItem, hueObjectItemValue in hueLampIdValues['state'].items():
                # jetzt werden die werte herausgesucht
                for returnItem in self._listenItems:
                    # wenn ein listen item angelegt wurde und dafür ein status zurückkam
                    #verglichen wird mit dem referenzkey, der weiter oben aus lampid und state gebaut wurde
                    if returnItem == (hueLampId + hueObjectItem):
                        # dafür wir der reale wert der hue bridge gesetzt
                        if (returnItem == (hueLampId + 'on')) or (returnItem == (hueLampId + 'reachable')):
                            value = bool(hueObjectItemValue)
                        elif (returnItem == (hueLampId + 'effect')) or (returnItem == (hueLampId + 'alert')):
                            value = str(hueObjectItemValue)
                        else:
                            value = float(hueObjectItemValue)
                        # wenn der wert gerade im fading ist, dann nicht überschreiben, sonst bleibt es stehen !
                        if not self._listenItems[returnItem]._fading:
                            self._listenItems[returnItem](value,'HUE')
        self._lampslock.release()
        return

    def authorizeuser(self):
        data = json.dumps(
            {"devicetype": "smarthome", "username": self._hue_user})

        con = http.client.HTTPConnection(self._hue_ip)
        con.request("POST", "/api", data)
        resp = con.getresponse()
        con.close()

        if resp.status != 200:
            logger.error("Authenticate request failed")
            return "Authenticate request failed"

        resp = resp.read()
        logger.debug(resp)

        resp = json.loads(resp)

        logger.debug(resp)
        return resp

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    myplugin = HUE('smarthome-dummy')
    myplugin.run()
