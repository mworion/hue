# Phillips HUE

###New development of Hue plugin for use in smarthome (C) Michael Würtenberger 2014, 2015
<<<<<<< HEAD

version 0.9 develop
=======
version 0.95 develop
>>>>>>> refs/heads/develop

<<<<<<< HEAD

# rgb is included !!! please read carefully !
until submodules are realized the converter is included to the hue plugin directory
=======
### test for multi bridge support is in !
If you don't have mor than one bridge, no change is needed.

>>>>>>> refs/heads/develop
# Requirements
Needs httplib, rgb_cie from https://github.com/benknight/hue-python-rgb-converter in plugin directory

## Supported Hardware
Philips hue bridge, multiple bridges allowed

# Configuration
## plugin.conf
Typical configuration for 3 bridges
<pre>
[HUE]
   class_name = HUE
   class_path = plugins.hue
   hue_user = 38f625a739562a8bd261ab9c7f5e62c8, 38f625a739562a8bd261ab9c7f5e62c8, 38f625a739562a8bd261ab9c7f5e62c8
   hue_ip = 192.168.2.2,192.168.2.3,192.168.2.4
   hue_port = 80,80,80
   cycle_lamps = 3
   cycle_bridges = 30
   default_transitionTime = 0.4
</pre>
Minimal configuration for single bridge an default settings
<pre>
[HUE]
   class_name = HUE
   class_path = plugins.hue
   hue_user = 38f625a739562a8bd261ab9c7f5e62c8
   hue_ip = 192.168.2.2
</pre>

### hue_user
A user name for the hue bridge. Usually this is a hash value of 32 hexadecimal digits.
If you would like to use more than on bridge, you have to specify all ip adresses, ports and users accordingly.
All users are separated with semicolon !
If the user/hash is not yet authorized, you can use sh.hue.authorizeuser() (via interactive shell or via logic)
to authorize it. The link button must be pressed before.

### hue_ip
IP or host name of the hue bridge. Per default this is "Philips-hue", so that you normally don't have to
specify a value here. 
If you would like to use more than on bridge, you have to specify all ip adresses, ports and users accordingly.
All ip's are separated with semicolon !

### hue_port
Port number of the hue bridge. Default 80. Normally there is no need to change that.
If you would like to use more than on bridge, you have to specify all ip adresses, ports and users accordingly.
All ports are separated with semicolon !

### cycle_lamps
Cycle in seconds to how often update the state of the lights in smarthome.
Note: The hue bridge has no notification feature. Therefore changes can only be detected via polling.

### cycle_bridges
Cycle in seconds to how often update the state of the bridges in smarthome.
Note: The hue bridge has no notification feature. Therefore changes can only be detected via polling.

### default_transitionTime
Time in seconds how fast che states of the lamps are changed through the bridge itself. If you don't set a value in the item, this value
ist used.
Note: The hue bridge has no notification feature. Therefore changes can only be detected via polling.

## items.conf

### hue_bridge_id (formerly hue_bridge !)

Specify the number of the hue_bridge_id. Via this parameter the right hue connection is established.
The numbers start with 0. There must be no missing number in between !

### hue_lamp_id (formerly hue_id)
Specify the lamp id. Via this parameter the right lamp on the hue connection is established.
The numbers are the coresponding numbers of the lamp Id in the bridge. They normally start with 0. There must be a
hue_bridge_id attached to this item as well. If not, a default value of 0 will be set.
 
### hue_send
Specifies the attribute which is send to the lamp when this item is altered.
Available attributes currently are: 'on', 'bri', 'sat', 'hue', 'effect', 'alert', 'col_r', 'col_g', 'col_b', 'ct', 'scene'
The value ranges of the items and the types are:
'on': bool : False / True
'bri': num : 0-255
'sat': num : 0-255
'hue': num : 0-65535
'effect': str : 'none' or 'colorloop'
'alert': dtr : 'none' or 'select' or 'lselect'
'col_r': num : 0-255
'col_g': num : 0-255
'col_b': num : 0-255
'ct' : num : 153 - 500
'scene' : str : string of the programmed scene name in bridge
Please refer to the specs of the API of the hue lamps.
In addition to hue_send an hue_lamp_id and hue_bridge_id has to be set. This could be done in upper layers. If it's missing the parameter is removed.

### hue_listen
Specifies the attribute which is updated on a scheduled timer from the lamps and bridges.
For the lamps the available attributes currently are: 
'on', 'bri', 'sat', 'hue', 'reachable', 'effect', 'alert', 'type', 'name', 'modelid', 'swversion', 'ct'
for the bridges the available attributes currently are : 
'bridge_name','zigbeechannel','mac','dhcp','ipaddress','netmask','gateway','UTC','localtime','timezone','bridge_swversion','apiversion','swupdate',
'linkbutton','portalservices','portalconnection','portalstate','whitelist'

### hue_transitionTime
This parameter specifies the time, which the lamp take to reach the a newly set value. This is done by interpolation of the values inside the lamp. 
This parameter is optional. If not set the time default is 0.1 second.
In addition to hue_send an hue_lamp_id and hue_bridge_id has to be set. This could be done in upper layers. If it's missing the parameter is removed.

### Using DPT3 dimming
If you would like to use a DPT3 dimmer, you have to specify a subitem to the dimmed hue item. To this subitem you link the knx DPT3 part. 
You can control the dimming via some parameters, which have to be specified in this subitem.
If you are using the DPT3 dimmer, please take into account that there is a lower limit of timing. 
A lower value than 0.2 seconds should be avoided, regarding the performance of the overall system. 
Nevertheless to get nice and smooth results of dimming, please set the parameters of hue_transitionTime and hue_dim_time equally. 
In that case, the lamp interpolates the transition as quick as the steps of the dimmer function happen.
If the lamp is set to off (e.g. attribute 'on' = False), changes could be not written to the lamp. 
Warnings in the log will appear. The lamp doesn't support this behaviour. In case of starting dimming the brigthness of the lamp, the
plugin automatically sets the lamp on and starts dimming with the last value.     

### hue_dim_max
Parameter which determines the maximum of the dimmer range. Without this parameter DPT3 dimming will not work.

### hue_dim_step
Parameter which determines the step size.
In addition to hue_dim_max this parameter has to be set. If not a warning will be written and a default value of 25 will be set.

### hue_dim_time
Parameter which determines the time, the dimmer takes for making on step.
In addition to hue_dim_max this parameter has to be set. If not a warning will be written and a default value of 1 will be set.

## Example
# items/test.conf
<pre>
[keller]
	[[hue]]
		# if hue_lamp_id und hue_bridge_id ist set in a highe layer, it is used for all lower layers automatically, this is overwrite mode
		hue_lamp_id = 1
		hue_bridge_id = 0
    	[[[bridge_name]]]
    		type = str
			hue_listen = bridge_name
    	[[[zigbeechannel]]]
    		type = num
			hue_listen = zigbeechannel
    	[[[mac]]]
    		type = str
			hue_listen = mac
    	[[[dhcp]]]
    		type = bool
			hue_listen = dhcp
    	[[[ipaddress]]]
    		type = str
			hue_listen = ipaddress
    	[[[netmask]]]
    		type = str
			hue_listen = netwask
    	[[[gateway]]]
    		type = str
			hue_listen = gateway
    	[[[utc]]]
    		type = str
			hue_listen = UTC
    	[[[localtime]]]
    		type = str
			hue_listen = localtime
    	[[[timezone]]]
    		type = str
			hue_listen = timezone
    	[[[whitelist]]]
    		type = dict
			hue_listen = whitelist
    	[[[bridge_swversion]]]
    		type = str
			hue_listen = bridge_swversion
    	[[[apiversion]]]
    		type = str
			hue_listen = apiversion
    	[[[swupdate]]]
    		type = dict
			hue_listen = swupdate
    	[[[linkbutton]]]
    		type = bool
			hue_listen = linkbutton
    	[[[portalservices]]]
    		type = bool
			hue_listen = portalservices
    	[[[portalconnection]]]
    		type = str
			hue_listen = portalconnection
    	[[[portalstate]]]
    		type = dict
			hue_listen = portalstate
    	[[[power]]]
        	type = bool
        	hue_send = on
        	hue_listen = on
            knx_dpt = 1
            knx_cache = 8/0/1
    	[[[reachable]]]
        	type = bool
        	hue_listen = reachable
        [[[ct]]]
        	type = num
        	hue_send = ct
        	hue_listen = ct
        [[[scene]]]
        	type = str
        	hue_send = scene
        	enforce_updates = true
        [[[bri]]]
        	type = num
        	cache = on
        	hue_send = bri
        	hue_listen = bri
        	hue_transitionTime = 0.2
	       	[[[[dim]]]]
	    		type = list
	        	knx_dpt = 3
	        	knx_listen = 8/0/2
	        	hue_dim_max = 255
	        	hue_dim_step = 10
	        	hue_dim_time = 0.2
        [[[sat]]]
        	type = num
        	cache = on
        	hue_send = sat
        	hue_listen = sat
        [[[col_r]]]
        	type = num
        	cache = on
        	hue_send = col_r
        [[[col_g]]]
        	type = num
        	cache = on
        	hue_send = col_g
        [[[col_b]]]
        	type = num
        	cache = on
        	hue_send = col_b
        [[[hue]]]
        	type = num
        	cache = on
        	hue_send = hue
        	hue_listen = hue
        	hue_transitionTime = 0.2
	       	[[[[dim]]]]
	    		type = list
	        	knx_dpt = 3
	        	knx_listen = 8/0/12
	        	hue_dim_max = 65535
	        	hue_dim_step = 2000
	        	hue_dim_time = 0.2
        [[[effect]]]
        	type = str
        	hue_send = effect
        	hue_listen = effect
        [[[alert]]]
        	type = str
        	hue_send = alert
        	hue_listen = alert
         [[[modeltype]]]
        	type = str
        	hue_listen = type
         [[[name]]]
        	type = str
        	hue_listen = name
         [[[modelid]]]
        	type = str
        	hue_listen = modelid
         [[[swversion]]]
        	type = str
        	hue_listen = swversion
</pre>

Please not that knx_cache is wrong in the old example for [[[dim]]], the right setting is knx_listen

## logic.conf
No logic attributes.

# Methodes

## authorizeuser()
Authorizes the user configured by hue_user config property. You have to press the link button.

<pre>
sh.hue.authorizeuser()
</pre>
