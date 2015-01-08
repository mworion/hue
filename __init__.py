#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#
#  Copyright (C) 2014,2015 Michael Würtenberger
#  Version 0.94 develop
#  Erstanlage mit ersten Tests
#  Basiert auf den Ueberlegungen des verhandenen Hue Plugins.
#  Die Parametrierung des Plugings in der plugin.conf und die authorize() Methode wurden zur
#  Wahrung der Kompatibilitaet uebernommen
# 
#  Umsetzung rgb mit aufgenommen, basiert auf der einwegumrechnung von
#  https://github.com/benknight/hue-python-rgb-converter 
#
#  Basiert aus der API 1.4 der Philips hue API spezifikation, die man unter
#  http://www.developers.meethue.com/documentation/lights-api finden kann
#
#  APL2.0
# 

import logging
import json
import http.client
import time
import threading
from plugins.hue.rgb_cie import Converter
#import pydevd

logger = logging.getLogger('HUE:')

class HUE():

    def __init__(self, smarthome, hue_ip = 'Philips-hue', hue_user = '', hue_port = '80', cycle_lamps = 3, cycle_bridges = 30, default_transitionTime = '0.4'):

        # parameter zu übergabe aus der konfiguration pulgin.conf
#        pydevd.settrace('192.168.2.57')        
        self._sh = smarthome
        self._hue_ip = hue_ip.split(',')
        self._hue_user = hue_user.split(',')
        self._hue_port = hue_port.split(',')
        self._numberHueBridges = len(self._hue_ip)
        if len(self._hue_port) != self._numberHueBridges or len(self._hue_user) != self._numberHueBridges:
            logger.error('HUE: Error in bridge configuration: number of ip, user or port unequal')
        self._hueDefaultTransitionTime = default_transitionTime
        # variablen zur steuerung des plugins
        # hier werden alle bekannte items für lampen eingetragen
        self._sendLampItems = {}
        self._listenLampItems = {}
        # hier werden alle bekannte items für die hues eingetragen
        self._sendBridgeItems = {}
        self._listenBridgeItems = {}
        # locks für die absicherung
        self._hueLampsLock = threading.Lock()
        self._hueBridgesLock = threading.Lock()
        # hier ist die liste der einträge, für die der status auf listen gesetzt werden kann
        self._listenLampKeys = ['on', 'bri', 'sat', 'hue', 'reachable', 'effect', 'alert', 'type', 'name', 'modelid', 'swversion', 'ct']
        # hier ist die liste der einträge, für die der status auf senden gesetzt werden kann
        self._sendLampKeys = ['on', 'bri', 'sat', 'hue', 'effect', 'alert', 'col_r', 'col_g', 'col_b', 'ct']
        # hier ist die liste der einträge, für die der status auf listen gesetzt werden kann
        self._listenBridgeKeys = ['bridge_name','zigbeechannel','mac','dhcp','ipaddress','netmask','gateway','UTC','localtime','timezone','bridge_swversion','apiversion','swupdate','linkbutton','portalservices','portalconnection','portalstate','whitelist']
        # hier ist die liste der einträge, für die der status auf senden gesetzt werden kann
        self._sendBridgeKeys = ['scene']
        # hier ist die liste der einträge, für die ein dimmer DPT3 gesetzt werden kann
        self._dimmKeys = ['bri', 'sat', 'hue']
        # hier ist die liste der einträge, für rgb gesetzt werden kann
        self._rgbKeys = ['col_r', 'col_g', 'col_b']
        # hier ist die liste der einträge, für string
        self._stringKeys = ['effect', 'alert', 'type', 'name', 'modelid', 'swversion', 'bridge_name','mac','ipaddress','netmask','gateway','UTC','localtime','timezone','bridge_swversion','apiversion','portalconnection']
        # hier ist die liste der einträge, für string
        self._boolKeys = ['on', 'reachable', 'linkbutton', 'portalservices', 'dhcp']
        # hier ist die liste der einträge, für string
        self._dictKeys = ['portalstate','swupdate','whitelist']
        # hier ist die liste der einträge, für wertebereich 0-255
        self._rangeInteger8 = ['bri', 'sat', 'col_r', 'col_g', 'col_b']
        # hier ist die liste der einträge, für wertebereich 0-255
        self._rangeInteger16 = ['hue']
        
        # Konfigurationen zur laufzeit
        # scheduler für das polling der status der lampen über die hue bridge
        self._sh.scheduler.add('hue-update-lamps', self._update_lamps, cycle=cycle_lamps)
        # anstossen des updates zu beginn
        self._sh.trigger('hue-update-lamps', self._update_lamps)
        # scheduler für das polling der status der hue bridge
        self._sh.scheduler.add('hue-update-bridges', self._update_bridges, cycle=cycle_bridges)
        # anstossen des updates zu beginn
        self._sh.trigger('hue-update-bridges', self._update_bridges)
        
        
        # konvertierung rgb nach cie xy
        self._rgbConverter = Converter()
        


    def run(self):
        self.alive = True
        # if you want to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        self.alive = False 
    
    def parse_item(self, item):

        # alle konfigurationsfehler sollten in der parsing routinge abgefangen werden
        # fehlende parameter werden mit eine fehlermeldung versehen und auf default werte gesetzt
        # sowie anschliessend in die objektstruktur dynamisch eingepflegt. Damit haben die Auswerte
        # routinen keinen sonderfall mehr abzudecken !
        
        # zunächst einmal die installation der dimmroutine
        if 'hue_dim_max' in item.conf:
            if not 'hue_dim_step' in item.conf:
                item.conf['hue_dim_step'] = '25'
                logger.warning('HUE: dimmenDPT3: no hue_dim_step defined in item [{0}] using default 25'.format(item))
            if not 'hue_dim_time' in item.conf:
                item.conf['hue_dim_time'] = '1'
                logger.warning('HUE: dimmenDPT3: no hue_dim_time defined in item [{0}] using default 1'.format(item))
            return self.dimmenDPT3

        # dann die unterscheidung für die steuerung lampen und bridge
        # zuerst einmal die fallunterscheidung für das parsen:
        if 'hue_lamp_id' in item.conf:
            hueLampId = item.conf['hue_lamp_id']
            # nur wenn eine hue lamp id angegeben ist, 
            # auswertung und setzen der transition time 
            if 'hue_bridge_id' in item.conf:
                # beides definiert, dann lampensteuerung und bridge angegeben -> idealfall
                hueBridgeId = item.conf['hue_bridge_id']
                if int(hueBridgeId) >= self._numberHueBridges:
                    logger.error('HUE: bdridge id in item [{0}] is higher than number of bridges configured. Setting to 0'.format(item))
                    hueBridgeId = '0'
            else:
                # nur die lampe angegeben, dann wird bridge auf default = '0' gesetzt
                hueBridgeId = '0'
                # und bei den objekten gesetzt
                item.conf['hue_bridge_id'] = hueBridgeId
                
            # jetzt die auswertungen der send funktionen der lampen.                
            for child in self._sh.find_children(item, 'hue_send'):
                send_to = child.conf['hue_send']
                if send_to in self._sendLampKeys:
                    # referenzkey erzeugen für die liste. er besteht aus den lampen id und dem state (send_key), der gesetzt werden kann
                    hueIndex = hueBridgeId + '.' + hueLampId + '.' + send_to
                    if not hueIndex in self._sendLampItems:
                        self._sendLampItems[hueIndex] = child
                        child.conf['hue_bridge_id'] = hueBridgeId
                        child.conf['hue_lamp_id'] = hueLampId
                        child.add_method_trigger(self.update_lamp_item)
                    else:
                        logger.warning('HUE: parse_item: atrribute [hue_listen] for lamps is already defined in item [{0}]'.format(self._listenLampItems[hueIndex]))
                
            # jetzt die auswertung der listen funktionen der lampen.
            for child in self._sh.find_children(item, 'hue_listen'):
                listen_to = child.conf['hue_listen']
                if listen_to in self._listenLampKeys:
                    # referenzkey erzeugen für die liste. er besteht aus den lampen id und dem state (send_key), der gesetzt werden kann
                    hueIndex = hueBridgeId + '.' + hueLampId + '.' + listen_to 
                    if not hueIndex in self._listenLampItems:
                        child.conf['hue_bridge_id'] = hueBridgeId
                        child.conf['hue_lamp_id'] = hueLampId
                        self._listenLampItems[hueIndex] = child
                    else:
                        logger.warning('HUE: parse_item: atrribute [hue_lsend] for lamps is already defined in item [{0}]'.format(self._listenLampItems[hueIndex]))

        if 'hue_bridge_id' in item.conf:
            # hier haben wir nur eine steuerung der bridge
            hueBridgeId = item.conf['hue_bridge_id']
            if int(hueBridgeId) >= self._numberHueBridges:
                logger.error('HUE: bdridge id in item [{0}] is higher than number of bridges configured. Setting to 0'.format(item))
                hueBridgeId = '0'
            # jetzt die auswertung fürs senden 
            for child in self._sh.find_children(item, 'hue_send'):
                send_to = child.conf['hue_send']
                if send_to in self._sendBridgeKeys:
                    # referenzkey erzeugen für die liste. er besteht aus den lampen id und dem state (send_key), der gesetzt werden kann
                    hueIndex = hueBridgeId + '.' + send_to 
                    if not hueIndex in self._sendBridgeItems:
                        self._sendBridgeItems[hueIndex] = child
                        child.conf['hue_bridge_id'] = hueBridgeId
                        child.add_method_trigger(self.update_bridge_item)
                    else:
                        logger.warning('HUE: parse_item: atrribute [hue_send] for bridge is already defined in item [{0}]'.format(self._listenLampItems[hueIndex]))
            # jetzt die auswertung der listen funktionen für die bridge.
            for child in self._sh.find_children(item, 'hue_listen'):
                listen_to = child.conf['hue_listen']
                if listen_to in self._listenBridgeKeys:
                    # referenzkey erzeugen für die liste. er besteht aus den lampen id und dem state (send_key), der gesetzt werden kann
                    hueIndex = hueBridgeId + '.' + listen_to
                    if not hueIndex in self._listenBridgeItems:
                        child.conf['hue_bridge_id'] = hueBridgeId
                        self._listenBridgeItems[hueIndex] = child
                    else:
                        logger.warning('HUE: parse_item: atrribute [hue_listen] for bridge is already defined in item [{0}]'.format(self._listenBridgeItems[hueIndex]))  
        
    def _limit_range_int(self, value, minValue, maxValue):
        # kurze routine zur wertebegrenzung
        if value >= maxValue:
            value = int(maxValue)
        elif value < minValue:
            value = int(minValue)
        else:
            value = int(value)
        return value
   
    def update_lamp_item(self, item, caller=None, source=None, dest=None):
        # methode, die bei einer änderung des items ausgerufen wird
        # wenn die änderung von aussen kommt, dann wird diese abgearbeitet
        # im konkreten fall heisst das, dass der aktuelle status der betroffene lampe komplett zusammengestellt wird
        # und anschliessen neu über die hue bridge gesetzt wird.
        if caller != 'HUE':
            # lokale speicherung in variablen, damit funktionen nicht immer aufgerufen werden (performance)
            value = item()
            hueBridgeId = item.conf['hue_bridge_id']
            hueLampId = item.conf['hue_lamp_id']
            hueSend = item.conf['hue_send']
            if 'hue_transitionTime' in item.conf:
                hueTransitionTime = int(float(item.conf['hue_transitionTime'])*10)
            else:
                hueTransitionTime = int(float(self._hueDefaultTransitionTime)*10)

            # index ist immer bridge_id + lamp_id + hue_send
            hueIndex = hueBridgeId + '.' + hueLampId
            
            if hueIndex + '.on' in self._sendLampItems:
                hueLampIsOn = self._sendLampItems[(hueIndex + '.on')]()
            else:
                logger.warning('HUE: update_lamp_item: no item for on/off defined for bridge {0} lampe {1}'.format(hueBridgeId, hueLampId))
                hueLampIsOn = False
                
            # test aus die wertgrenzen, die die bridge verstehen kann
            if hueSend in self._rangeInteger8:
                # werte dürfen zwischen 0 und 255 liegen
                value = self._limit_range_int(value, 0, 255)    
            if hueSend in self._rangeInteger16:
                # hue darf zwischen 0 und 65535 liegen
                value = self._limit_range_int(value, 0, 65535)    
            if hueSend == 'ct':
                # hue darf zwischen 0 und 65535 liegen
                value = self._limit_range_int(value, 153, 500)
                
            if hueLampIsOn:
                # lampe ist an (status in sh). dann können alle befehle gesendet werden
                if hueSend == 'on':
                    # wenn der status in sh true ist, aber mit dem befehl on, dann muss die lampe 
                    # auf der hue seite erst eingeschaltet werden
                    if hueIndex + '.bri' in self._sendLampItems:
                        # wenn eingeschaltet wird und ein bri item vorhanden ist, dann wird auch die hellgkeit
                        # mit gesetzt, weil die lmape das im ausgeschalteten zustand vergisst.
                        self._set_lamp_state(hueBridgeId, hueLampId, {'on': True, 'bri': int(self._sendLampItems[(hueIndex + '.bri')]()) , 'transitiontime': hueTransitionTime})
                    else:
                        # ansonst wird nur eingeschaltet
                        self._set_lamp_state(hueBridgeId, hueLampId, {'on': True , 'transitiontime': hueTransitionTime})
                        logger.info('HUE: update_lamp_item: no bri item defined for restoring the brightness after swiching on again')                        
                else:
                    # anderer befehl gegeben
                    if hueSend in self._rgbKeys:
                        # besonderheit ist der befehl für die rgb variante, da hier alle werte herausgesucht werden müssen
                        if ((hueIndex + '.col_r') in self._sendLampItems) and ((hueIndex + '.col_g') in self._sendLampItems) and ((hueIndex + '.col_b') in self._sendLampItems):
                            # wertebereiche der anderen klären
                            # bri darf zwischen 0 und 255 liegen
                            value_r = self._limit_range_int(self._sendLampItems[(hueIndex + '.col_r')](), 0, 255)    
                            value_g = self._limit_range_int(self._sendLampItems[(hueIndex + '.col_g')](), 0, 255)    
                            value_b = self._limit_range_int(self._sendLampItems[(hueIndex + '.col_b')](), 0, 255)    
                            # umrechnung
                            xyPoint = self._rgbConverter.rgbToCIE1931(value_r, value_g, value_b)
                            # und jetzt der wert setzen
                            self._set_lamp_state(hueBridgeId, hueLampId, {'xy': xyPoint, 'transitiontime': hueTransitionTime})
                        else:
                            logger.warning('HUE: update_lamp_item: on or more of the col... items around item [{0}] is not defined'.format(item))
                    else:
                        # standardbefehle
                        self._set_lamp_state(hueBridgeId, hueLampId, {hueSend: value, 'transitiontime': hueTransitionTime})
            else:
                # lampe ist im status bei sh aus. in diesem zustand sollten keine befehle gesendet werden
                if hueSend == 'on':
                    # sonderfall, wenn der status die transition erst ausgeöst hat, dann muss die lampe
                    # auf der hue seite erst ausgeschaltet werden
                    self._set_lamp_state(hueBridgeId, hueLampId, {'on': False , 'transitiontime': hueTransitionTime})
                else:
                    # die lampe kann auch über das senden bri angemacht werden
                    if hueSend == 'bri':
                        # jetzt wird die lampe eingeschaltet und der wert von bri auf den letzten wert gesetzt
                        self._set_lamp_state(hueBridgeId, hueLampId, {'on': True , 'bri': value, 'transitiontime': hueTransitionTime})
                    else:
                        # ansonsten wird kein befehl abgesetzt !
                        pass
                           
    def update_bridge_item(self, item, caller=None, source=None, dest=None):
        # methode, die bei einer änderung des items ausgerufen wird
        # wenn die änderung von aussen kommt, dann wird diese abgearbeitet
        # im konkreten fall heisst das, dass der aktuelle status der betroffene lampe komplett zusammengestellt wird
        # und anschliessen neu über die hue bridge gesetzt wird.
        if caller != 'HUE':
            # lokale speicherung in variablen, damit funktionen nicht immer aufgerufen werden (performance)
            value = item()
            hueBridgeId = item.conf['hue_bridge_id']
            hueSend = item.conf['hue_send']
            # test aus die wertgrenzen, die die bridge verstehen kann
            if hueSend in self._rangeInteger8:
                # werte dürfen zwischen 0 und 255 liegen
                value = self._limit_range_int(value, 0, 255)    
            if hueSend in self._rangeInteger16:
                # hue darf zwischen 0 und 65535 liegen
                value = self._limit_range_int(value, 0, 65535)    
            self._set_group_state(hueBridgeId, '0', {hueSend: value})
                                   
    def dimmenDPT3(self, item, caller=None, source=None, dest=None):
        # das ist die methode, die die DPT3 dimmnachrichten auf die dimmbaren hue items mapped
        # fallunterscheidung dimmen oder stop
        if caller != 'HUE':
            # auswertung der list werte für die KNX daten
            # [1] steht für das dimmen
            # [0] für die richtung
            # es wird die fading funtion verwendet
            valueMax = float(item.conf['hue_dim_max'])
            valueDimStep = float(item.conf['hue_dim_step'])
            valueDimTime = float(item.conf['hue_dim_time'])
            if item()[1] == 1:
                # dimmen
                if item()[0] == 1:
                    # hoch
                    item.return_parent().fade(valueMax, valueDimStep, valueDimTime)
                else:
                    # runter
                    item.return_parent().fade(0, valueDimStep, valueDimTime)
            else:
                # stop, indem man einen wert setzt. da es nicht der gleiche wert sein darf, erst einmal +1, dann -1
                # das ist aus meiner sicht noch ein fehler in item.py
                item.return_parent()(int(item.return_parent()() + 1), 'HUE_FADE')
                item.return_parent()(int(item.return_parent()() - 1), 'HUE_FADE')
                    
    def _request(self, hueBridgeId='0', path='', method='GET', data=None):
        # hue bridge mit einem http request abfragen
        connectionHueBridge = http.client.HTTPConnection(self._hue_ip[int(hueBridgeId)])
        connectionHueBridge.request(method, "/api/%s%s" % (self._hue_user[int(hueBridgeId)], path), data)
        responseRaw = connectionHueBridge.getresponse()
        connectionHueBridge.close()

        # rückmeldung 200 ist OK
        if responseRaw.status != 200:
            logger.error('HUE: _request: response Raw: Request failed')
            return None
        # lesen, decodieren nach utf-8 (ist pflicht nach der api definition philips) und in ein python objekt umwandeln
        responseJson = responseRaw.read().decode('utf-8')
        response = json.loads(responseJson)
        # fehlerauswertung der rückmeldung, muss noch vervollständigt werden
        if isinstance(response, list) and response[0].get('error', None):
            error = response[0]["error"]
            description = error['description']
            if error['type'] == 1:
                logger.error('HUE: _request: Error: {0} (Need to specify correct hue user?)'.format(description))
            else:
                logger.error('HUE: _request: Error: {0}'.format(description))
            return None
        else:
            return response

    def _set_lamp_state(self, hueBridgeId, hueLampId, state):
        # hier erfolgt das setzen des status einer lampe
        # hier kommt der PUT request, um die stati an die hue bridge zu übertragen
        returnValues = self._request(hueBridgeId, "/lights/%s/state" % hueLampId, "PUT", json.dumps(state))
        if returnValues == None:
            logger.warning('HUE: hue_set_state - returnValues None')
            return
        # der aufruf liefert eine bestätigung zurück, was den numgesetzt werden konnte
        self._hueLampsLock.acquire()
        for hueObject in returnValues:
            for hueObjectStatus, hueObjectReturnString in hueObject.items():
                if hueObjectStatus == 'success':
                    for hueObjectReturnStringPath, hueObjectReturnStringValue in hueObjectReturnString.items():
                        hueObjectReturnStringPathItem = hueObjectReturnStringPath.split('/')[4]
                        # hier werden jetzt die bestätigten werte aus der rückübertragung im item gesetzt
                        # wir gehen durch alle listen items, um die zuordnung zu machen
                        for returnItem in self._listenLampItems:
                            # wenn ein listen item angelegt wurde und dafür ein status zurückkam
                            # verglichen wird mit dem referenzkey, der weiter oben aus lampid und state gebaut wurde
                            if returnItem == (hueLampId + hueObjectReturnStringPathItem):
                                # dafür wir der reale wert der hue bridge gesetzt
                                if hueObjectReturnStringPathItem in self._boolKeys:
                                    # typecast auf bool
                                    value = bool(hueObjectReturnStringValue)
                                elif hueObjectReturnStringPathItem in self._stringKeys:
                                    # typecast auf string
                                    value = str(hueObjectReturnStringValue)
                                else:
                                    # sonst ist es int
                                    value = int(hueObjectReturnStringValue)
                                self._listenLampItems[returnItem](value, 'HUE')
                else:
                    logger.warning('HUE: hue_set_lamp_state - hueObjectStatus no success:: {0}: {1} command state {2}'.format(hueObjectStatus, hueObjectReturnString, state))
        self._hueLampsLock.release()

    def _set_group_state(self, hueBridgeId, hueGroupId , state):
        # hier erfolgt das setzen des status einer gruppe
        # im Moment ist nur der abruf einer szene implementiert
        # hier kommt der PUT request, um die stati an die hue bridge zu übertragen
        returnValues = self._request(hueBridgeId, "/groups/%s/action" % hueGroupId, "PUT", json.dumps(state))
        if returnValues == None:
            logger.warning('HUE: hue_set_group_state - returnValues None')
            return
        # der aufruf liefert eine bestätigung zurück, was den numgesetzt werden konnte
        self._hueLampsLock.acquire()
        for hueObject in returnValues:
            for hueObjectStatus, hueObjectReturnString in hueObject.items():
                if hueObjectStatus == 'success':
                    pass
                else:
                    logger.warning('HUE: hue_set_group_state - hueObjectStatus no success:: {0}: {1} command state {2}'.format(hueObjectStatus, hueObjectReturnString, state))
        self._hueLampsLock.release()

    def _update_lamps(self):
        # mache ich mit der API get all lights
        # hier kommt der PUT request, um die stati an die hue bridge zu übertragen beispiel:

        numberBridgeId = 0
        while numberBridgeId < self._numberHueBridges:
            hueBridgeId = str(numberBridgeId)
            returnValues = self._request(hueBridgeId, '/lights')
            if returnValues == None:
                return
            # schleife über alle gefundenen lampen
            self._hueBridgesLock.acquire()
            for hueLampId, hueLampIdValues in returnValues.items():
                # schleife über alle rückmeldungen der lampen.
                # jetzt muss ich etwas tricksen, da die states eine ebene tiefer als die restlichen infos der lampe liegen
                # in den items ist das aber eine flache hierachie. um nur eine schleife darüber zu haben, baue ich mir ein
                # entsprechendes dict zusammen. 'state' ist zwar doppelt drin, stört aber nicht, da auch auf unterer ebene.
                dictOptimized = hueLampIdValues['state'].copy()
                dictOptimized.update(returnValues[hueLampId].items())
                # jetzt kann der durchlauf beginnen
                for hueObjectItem, hueObjectItemValue in dictOptimized.items():
                    # nachdem alle objekte und werte auf die gleiche ebene gebracht wurden, beginnt die zuordnung
                    # vor hier an werden die ganzen listen items durchgesehen und die werte aus der rückmeldung zugeordnet
                    for returnItem in self._listenLampItems:
                        # wenn ein listen item angelegt wurde und dafür ein status zurückkam
                        # verglichen wird mit dem referenzkey, der weiter oben aus lampid und state gebaut wurde
                        if returnItem == (hueBridgeId + '.' + hueLampId + '.' + hueObjectItem):
                            # dafür wir der reale wert der hue bridge gesetzt
                            if hueObjectItem in self._boolKeys:
                                value = bool(hueObjectItemValue)
                            elif hueObjectItem in self._stringKeys:
                                value = str(hueObjectItemValue)
                            else:
                                value = int(hueObjectItemValue)
                            # wenn der wert gerade im fading ist, dann nicht überschreiben, sonst bleibt es stehen !
                            if not self._listenLampItems[returnItem]._fading:
                                # es werden nur die Einträge zurückgeschrieben, falls die Lampe nich im fading betrieb ist
                                if self._listenLampItems[(hueBridgeId + '.' + hueLampId + '.on')]() or not hueObjectItem == 'bri':
                                    # und falls die lampe aus ist, dann wird keine brightness zurückgeschrieben
                                    # in allen anderen werden wie werte zurückgeschrieben
                                    self._listenLampItems[returnItem](value, 'HUE')
                    
            self._hueBridgesLock.release()
            numberBridgeId = numberBridgeId + 1

    def _update_bridges(self):
        #
        # der datenabruf besteht aus dem befehl get configuration bridge
        #
        numberBridgeId = 0
        while numberBridgeId < self._numberHueBridges:
            hueBridgeId = str(numberBridgeId)
            returnValues = self._request(hueBridgeId, '/config')
            if returnValues == None:
                return
            # schleife über alle gefundenen lampen
            self._hueLampsLock.acquire()
            for hueObjectItem, hueObjectItemValue in returnValues.items():
                # nachdem alle objekte und werte auf die gleiche ebene gebracht wurden, beginnt die zuordnung
                # vor hier an werden die ganzen listen items durchgesehen und die werte aus der rückmeldung zugeordnet
                for returnItem in self._listenBridgeItems:
                    # wenn ein listen item angelegt wurde und dafür ein status zurückkam
                    # verglichen wird mit dem referenzkey, der weiter oben aus lampid und state gebaut wurde
                    if hueObjectItem == 'swversion':
                        hueObjectItem = 'bridge_swversion'
                    if hueObjectItem == 'name':
                        hueObjectItem = 'bridge_name'
                    if returnItem == (hueBridgeId + '.' + hueObjectItem):
                        # dafür wir der reale wert der hue bridge gesetzt
                        if hueObjectItem in self._boolKeys:
                            value = bool(hueObjectItemValue)
                        elif hueObjectItem in self._stringKeys:
                            value = str(hueObjectItemValue)
                        elif hueObjectItem in self._dictKeys:
                            value = dict(hueObjectItemValue)
                        else:
                            value = int(hueObjectItemValue)
                        # wenn der wert gerade im fading ist, dann nicht überschreiben, sonst bleibt es stehen !
                        self._listenBridgeItems[returnItem](value, 'HUE')
            self._hueLampsLock.release()
            numberBridgeId = numberBridgeId + 1


    def authorizeuser(self, hueBridgeId='0'):
        data = json.dumps(
            {"devicetype": "smarthome", "username": self._hue_user[int(hueBridgeId)]})

        con = http.client.HTTPConnection(self._hue_ip[int(hueBridgeId)])
        con.request("POST", "/api", data)
        resp = con.getresponse()
        con.close()

        if resp.status != 200:
            logger.error('HUE: authorize: Authenticate request failed')
            return "Authenticate request failed"

        resp = resp.read()
        logger.debug(resp)

        resp = json.loads(resp)

        logger.debug(resp)
        return resp

