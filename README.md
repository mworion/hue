# Phillips HUE

###New development of Hue plugin for use in smarthome (C) Michael Würtenberger 2014, 2015
version 0.9 develop

# rgb is included !!! please read carefully !
until submodules are realized the converter is included to the hue plugin directory
# Requirements

Needs httplib, rgb_cie from https://github.com/benknight/hue-python-rgb-converter

## Supported Hardware

Philips hue bridge

# Configuration

## plugin.conf

Typical configuration
<pre>
[HUE]
   class_name = HUE
   class_path = plugins.hue
   hue_user = 38f625a739562a8bd261ab9c7f5e62c8
</pre>

### hue_user
A user name for the hue bridge. Usually this is a hash value of 32 hexadecimal digits.

If the user/hash is not yet authorized, you can use sh.hue.authorizeuser() (via interactive shell or via logic)
to authorize it. The link button must be pressed before.

### hue_ip
IP or host name of the hue bridge. Per default this is "Philips-hue", so that you normally don't have to
specify a value here.

### hue_port
Port number of the hue bridge. Default 80. Normally there is no need to change that.

### cycle
Cycle in seconds to how often update the state of the lights in smarthome.

Note: The hue bridge has no notification feature. Therefore changes can only be detected via polling.

## items.conf

### hue_id

Specify the lamp id. Via this parameter the hue connection is established. 

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
Please refer to the specs of the API of the hue lamps. 

### hue_listen
Specifies the attribute which is updated on a scheduled timer from the lamp.
Available attributes currently are: 'on', 'bri', 'sat', 'hue', 'alert', 'effect', 'reachable', 'type', 'name', 'modelid', 'swversion'

### hue_transitionTime
This parameter specifies the time, which the lamp take to reach the a newly set value. This is done by interpolation of the values inside the lamp. This parameter is optional. If not set the time default is 0.1 second. 

### Using DPT3 dimming
If you use a DPT3 dimmer, you have to specify a subitem to the dimmed hue item. To this subitem you link the knx DPT3 part. You can control the dimming via some parameters, which have to be specified in this subitem.
If you are using the DPT3 dimmer, please take into account that there is a lower limit of timing. A lower value than 0.2 seconds should be avoided, regarding the performance of the overall system. 
Nevertheless to get nice and smooth results of dimming, please set the parameters of hue_transitionTime and hue_dim_time equally. In that case, the lamp interpolates the transition as quick as the steps of the dimmer function happen.
If the lamp is set to off (e.g. attribute 'on' = False), changes could be not written to the lamp. Warnings in the log will appear. The lamp doesn't support this behaviour. In case of starting dimming the brigthness of the lamp, the
plugin automatically sets the lamp on and starts dimming with the last value.     

### hue_dim_max
Parameter which determines the maximum of the dimmer range.

### hue_dim_step
Parameter which determines the step size.

### hue_dim_time
Parameter which determines the time, the dimmer takes for making on step.

## Example
# items/test.conf
<pre>
[keller]
	[[hue]]
    	[[[power]]]
        	type = bool
        	hue_id = 1
        	hue_send = on
        	hue_listen = on
            knx_dpt = 1
            knx_cache = 8/0/1
    	[[[reachable]]]
        	type = bool
        	hue_id = 1
        	hue_listen = reachable
        [[[ct]]]
        	type = num
        	hue_id = 1
        	hue_send = ct
        	hue_listen = ct
        	enforce_updates = true
        [[[scene]]]
        	type = str
        	hue_id = 1
        	hue_send = scene
        	enforce_updates = true
        [[[bri]]]
        	type = num
        	cache = on
        	hue_id = 1
        	hue_send = bri
        	hue_listen = bri
        	hue_transitionTime = 0.5
	       	[[[[dim]]]]
	    		type = list
	        	knx_dpt = 3
	        	knx_listen = 8/0/2
	        	hue_dim_max = 255
	        	hue_dim_step = 5
	        	hue_dim_time = 0.5
        [[[sat]]]
        	type = num
        	cache = on
        	hue_id = 1
        	hue_send = sat
        	hue_listen = sat
        [[[col_r]]]
        	type = num
        	cache = on
        	hue_id = 1
        	hue_send = col_r
        [[[col_g]]]
        	type = num
        	cache = on
        	hue_id = 1
        	hue_send = col_g
        [[[col_b]]]
        	type = num
        	cache = on
        	hue_id = 1
        	hue_send = col_b
        [[[hue]]]
        	type = num
        	cache = on
        	hue_id = 1
        	hue_send = hue
        	hue_listen = hue
        	hue_transitionTime = 0.5
	       	[[[[dim]]]]
	    		type = list
	        	knx_dpt = 3
	        	knx_listen = 8/0/12
	        	hue_dim_max = 65535
	        	hue_dim_step = 1000
	        	hue_dim_time = 0.5
        [[[effect]]]
        	type = str
        	hue_id = 1
        	hue_send = effect
        	hue_listen = effect
        [[[alert]]]
        	type = str
        	hue_id = 1
        	hue_send = alert
        	hue_listen = alert
         [[[type]]]
        	type = str
        	hue_id = 1
        	hue_listen = type
         [[[name]]]
        	type = str
        	hue_id = 1
        	hue_listen = name
         [[[modelid]]]
        	type = str
        	hue_id = 1
        	hue_listen = modelid
         [[[swversion]]]
        	type = str
        	hue_id = 1
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
