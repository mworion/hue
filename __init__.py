#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#
#  Copyright (C) 2014,2015 Michael Würtenberger
#
#  Version 1.2 develop
#
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

logger = logging.getLogger('HUE:')

class HUE():

    def __init__(self, smarthome, hue_ip = '', hue_user = '', hue_port = '80', cycle_lamps = '10', cycle_bridges = '60', default_transitionTime = '0.4'):

        # parameter zu übergabe aus der konfiguration pulgin.conf
        self._sh = smarthome
        # parmeter übernehmen, aufteilen und leerzeichen herausnehmen
        self._hue_ip = hue_ip.replace(' ','').split(',')
        self._hue_user = hue_user.replace(' ','').split(',')
        self._hue_port = hue_port.replace(' ','').split(',')
        # verabreitung der parameter aus der plugin.conf
        self._numberHueBridges = len(self._hue_ip)
        if len(self._hue_port) != self._numberHueBridges or len(self._hue_user) != self._numberHueBridges:
            logger.error('HUE: Error in plugin.conf: if you specify more than 1 bridge, all parameters hue_ip, hue_user and hue_port have to be defined')
            raise Exception('HUE: Plugin stopped due to configuration fault in plugin.conf') 
        if '' in self._hue_user:
            logger.error('HUE: Error in plugin.conf: you have to specify all hue_user')
            raise Exception('HUE: Plugin stopped due to configuration fault in plugin.conf') 
        if '' in self._hue_ip:
            logger.error('HUE: Error in plugin.conf: you have to specify all hue_ip')
            raise Exception('HUE: Plugin stopped due to configuration fault in plugin.conf') 
        if '' in self._hue_port:
            logger.error('HUE: Error in plugin.conf: you have to specify all hue_port')
            raise Exception('HUE: Plugin stopped due to configuration fault in plugin.conf') 
        self._cycle_lamps = int(cycle_lamps)
        if self._cycle_lamps < 5:
            # beschränkung der wiederholrate 
            self._cycle_lamps = 5
        self._cycle_bridges = int(cycle_bridges)
        if self._cycle_bridges < 10:
            # beschränkung der wiederholrate 
            self._cycle_lamps = 10
        self._hueDefaultTransitionTime = float(default_transitionTime)
        if self._hueDefaultTransitionTime < 0:
            # beschränkung der wiederholrate 
            logger.warning('HUE: Error in plugin.conf: the default_transitionTime paremeter cannot be negative. It is set to 0')
            self._hueDefaultTransitionTime = 0
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
        self._listenBridgeKeys = ['bridge_name', 'zigbeechannel', 'mac', 'dhcp', 'ipaddress', 'netmask', 'gateway', 'UTC', 'localtime', 'timezone', 'bridge_swversion', 'apiversion', 'swupdate', 'linkbutton', 'portalservices', 'portalconnection', 'portalstate', 'whitelist','errorstatus']
        # hier ist die liste der einträge, für die der status auf senden gesetzt werden kann
        self._sendBridgeKeys = ['scene']
        # hier ist die liste der einträge, für die ein dimmer DPT3 gesetzt werden kann
        self._dimmKeys = ['bri', 'sat', 'hue']
        # hier ist die liste der einträge, für rgb gesetzt werden kann
        self._rgbKeys = ['col_r', 'col_g', 'col_b']
        # hier ist die liste der einträge, für string
        self._stringKeys = ['effect', 'alert', 'type', 'name', 'modelid', 'swversion', 'bridge_name', 'mac', 'ipaddress', 'netmask', 'gateway', 'UTC', 'localtime', 'timezone', 'bridge_swversion', 'apiversion', 'portalconnection']
        # hier ist die liste der einträge, für string
        self._boolKeys = ['on', 'reachable', 'linkbutton', 'portalservices', 'dhcp']
        # hier ist die liste der einträge, für string
        self._dictKeys = ['portalstate', 'swupdate', 'whitelist']
        # hier ist die liste der einträge, für wertebereich 0-255
        self._rangeInteger8 = ['bri', 'sat', 'col_r', 'col_g', 'col_b']
        # hier ist die liste der einträge, für wertebereich 0-255
        self._rangeInteger16 = ['hue']
        # konvertierung rgb nach cie xy
        self._rgbConverter = Converter()
        # Konfigurationen zur laufzeit
        # scheduler für das polling der status der lampen über die hue bridge
        self._sh.scheduler.add('hue-update-lamps', self._update_lamps, cycle = self._cycle_lamps)
        # anstossen des updates zu beginn
        self._sh.trigger('hue-update-lamps', self._update_lamps)
        # scheduler für das polling der status der hue bridge
        self._sh.scheduler.add('hue-update-bridges', self._update_bridges, cycle = self._cycle_bridges)
        # anstossen des updates zu beginn
        self._sh.trigger('hue-update-bridges', self._update_bridges)
        # jetzt noch den bridge errorstatus default auf false setzen

    def run(self):
        self.alive = True
        # if you want to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        self.alive = False
        
    def _find_item_attribute(self, item, attribute, attributeDefault, attributeLimit=99):
        # zwischenspeichern für die loggerausgabe
        itemSearch = item
        # schleife bis ich ganz oben angekommen bin
        while (not attribute in itemSearch.conf):
            # eine Stufe in den ebenen nach oben
            itemSearch = itemSearch.return_parent()                    
            if (itemSearch is self._sh):
                if attribute == 'hue_bridge_id' and self._numberHueBridges > 1:
                    logger.warning('HUE: _find_item_attribute: could not find [{0}  ] for item [{1}], setting defined default value {2}'.format(attribute, item, attributeDefault))
                elif attribute == 'hue_lamp_id':
                    logger.error('HUE: _find_item_attribute: could not find [{0}  ] for item [{1}], an value has to be defined'.format(attribute, item))
                    raise Exception('HUE: Plugin stopped due to missing hue_lamp_id in item.conf')
                # wenn nicht gefunden, dann wird der standardwert zurückgegeben
                return str(attributeDefault)
        itemAttribute = int(itemSearch.conf[attribute])
        if itemAttribute >= attributeLimit:
            itemAttribute = attributeLimit
            logger.warning('HUE: _find_item_attribute: attribute exceeds upper limit and set to default in item [{0}]'.format(item))
#        logger.warning('HUE: _find_item_attribute: attribute [{0}] found for item [{1}] at item [{2}]'.format(attribute, item, itemSearch))
        return str(itemAttribute)
    
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

        if 'hue_listen' in item.conf:
            hueListenCommand = item.conf['hue_listen']
            if hueListenCommand in self._listenLampKeys:
                # wir haben ein sendekommando für die lampen. dafür brauchen wir die bridge und die lampen id
                hueLampId = self._find_item_attribute(item, 'hue_lamp_id', 1)
                hueBridgeId = self._find_item_attribute(item, 'hue_bridge_id', 0, self._numberHueBridges)
                item.conf['hue_lamp_id'] = hueLampId
                item.conf['hue_bridge_id'] = hueBridgeId
                hueIndex = hueBridgeId + '.' + hueLampId + '.' + hueListenCommand
                if not hueIndex in self._listenLampItems:
                    self._listenLampItems[hueIndex] = item
                else:
                    logger.warning('HUE: parse_item: in lamp item [{0}] command hue_listen = {1} is duplicated to item  [{2}]'.format(item,hueListenCommand,self._listenLampItems[hueIndex]))
            elif hueListenCommand in self._listenBridgeKeys:
                # hier brauche ich nur eine hue_bridge_id
                hueBridgeId = self._find_item_attribute(item, 'hue_bridge_id', 0, self._numberHueBridges)
                item.conf['hue_bridge_id'] = hueBridgeId
                hueIndex = hueBridgeId + '.' + hueListenCommand
                if not hueIndex in self._listenBridgeItems:
                    self._listenBridgeItems[hueIndex] = item
                else:
                    logger.warning('HUE: parse_item: in bridge item [{0}] command hue_listen = {1} is duplicated to item  [{2}]'.format(item,hueListenCommand,self._listenLampItems[hueIndex]))
            else:
                logger.error('HUE: parse_item: command hue_listen = {0} not defined in item [{1}]'.format(hueListenCommand,item))
        
        if 'hue_send' in item.conf:
            hueSendCommand = item.conf['hue_send']
            if hueSendCommand in self._sendLampKeys:
                # wir haben ein sendekommando für die lampen. dafür brauchen wir die bridge und die lampen id
                hueLampId = self._find_item_attribute(item, 'hue_lamp_id', 1)
                hueBridgeId = self._find_item_attribute(item, 'hue_bridge_id', 0, self._numberHueBridges)
                item.conf['hue_lamp_id'] = hueLampId
                item.conf['hue_bridge_id'] = hueBridgeId
                hueIndex = hueBridgeId + '.' + hueLampId + '.' + hueSendCommand
                if not hueIndex in self._sendLampItems:
                    self._sendLampItems[hueIndex] = item
                else:
                    logger.warning('HUE: parse_item: in lamp item [{0}] command hue_send = {1} is duplicated to item  [{2}]'.format(item,hueSendCommand,self._sendLampItems[hueIndex]))
                return self.update_lamp_item
            elif hueSendCommand in self._sendBridgeKeys:
                # hier brauche ich nur eine hue_bridge_id
                hueBridgeId = self._find_item_attribute(item, 'hue_bridge_id', 0, self._numberHueBridges)
                item.conf['hue_bridge_id'] = hueBridgeId
                hueIndex = hueBridgeId + '.' + hueSendCommand
                if not hueIndex in self._sendBridgeItems:
                    self._sendBridgeItems[hueIndex] = item
                else:
                    logger.warning('HUE: parse_item: in bridge item [{0}] command hue_send = {1} is duplicated to item  [{2}]'.format(item,hueSendCommand,self._sendLampItems[hueIndex]))
                return self.update_bridge_item
            else:
                logger.error('HUE: parse_item: command hue_send = {0} not defined in item [{1}]'.format(hueSendCommand,item))

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
                hueTransitionTime = int(float(item.conf['hue_transitionTime']) * 10)
            else:
                hueTransitionTime = int(self._hueDefaultTransitionTime * 10)

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
                            # umrechnung mit try, da es zu division durch 0 kommt (beobachtung)
                            try:
                                # umrechnung
                                xyPoint = self._rgbConverter.rgbToCIE1931(value_r, value_g, value_b)
                            except Exception as e:
                                logger.error('HUE: update_lamp_item: problem in library rgbToCIE1931 exception : {0} '.format(e))
                            else:
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
        try:
            connectionHueBridge = http.client.HTTPConnection(self._hue_ip[int(hueBridgeId)], timeout = 2)
            connectionHueBridge.request(method, "/api/%s%s" % (self._hue_user[int(hueBridgeId)], path), data)
        except Exception as e:
            logger.error('HUE: _request: problem in http.client exception : {0} '.format(e))
            if hueBridgeId + '.' + 'errorstatus' in self._listenBridgeItems:
                # wenn der item abgelegt ist, dann kann er auch gesetzt werden
                self._listenBridgeItems[hueBridgeId + '.' + 'errorstatus'](True,'HUE')
            if connectionHueBridge:
                connectionHueBridge.close()
        else:
            responseRaw = connectionHueBridge.getresponse()
            connectionHueBridge.close()
            if hueBridgeId + '.' + 'errorstatus' in self._listenBridgeItems:
                # wenn der item abgelegt ist, dann kann er auch rückgesetzt werden
                self._listenBridgeItems[hueBridgeId + '.' + 'errorstatus'](False,'HUE')
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
                            if returnItem == (hueBridgeId + '.' + hueLampId + '.' + hueObjectReturnStringPathItem):
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
                                if hueObjectItem == 'bri':
                                    # bei brightness gibt es eine fallunterscheidung
                                    if hueBridgeId + '.' + hueLampId + '.on' in self._listenLampItems:
                                        # geht aber nur, wenn ein solches item vorhanden ist
                                        if self._listenLampItems[(hueBridgeId + '.' + hueLampId + '.on')]():
                                            # die brightness darf nur bei lamp = on zurückgeschrieben werden, den bei aus ist sie immer 0
                                            self._listenLampItems[returnItem](value, 'HUE')
                                else:
                                    # bei allen anderen kann zurückgeschrieben werden
                                    self._listenLampItems[returnItem](value, 'HUE')
            self._hueBridgesLock.release()
            numberBridgeId = numberBridgeId + 1

    def _update_bridges(self):
        # der datenabruf besteht aus dem befehl get configuration bridge
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

    def get_config(self, hueBridgeId='0'):
        # hier eine interaktive routing für di ecli, um den user herauszubekommen, 
        # mit dem die szenen gesetzt worden sind, um ihn dann als user für das plugin einzusetzen
        # und jetzt alle szenen
        response = self._request(hueBridgeId, '/scenes')
        logger.warning('HUE: get_config: scenes {0}'.format(response))
        return response

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

