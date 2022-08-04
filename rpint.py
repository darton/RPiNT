#!/usr/bin/env python3

# -*- coding:utf-8 -*-
#
#  Author : Dariusz Kowalczyk
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License Version 2 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.

# --- Functions ---

def shutdown():
    from subprocess import check_call
    check_call(['sudo', 'poweroff'])

def lldp():
  import json
  import subprocess
  from gpiozero import Button
  from time import sleep

  command = ('lldpcli show neighbors details -f json')

  p = subprocess.Popen(command, universal_newlines=True,
  shell=True, stdout=subprocess.PIPE,
  stderr=subprocess.PIPE)
  text = p.stdout.read()
  retcode = p.wait()
  lldp = json.loads(text)
  lldp_len = len(lldp['lldp'])
  if lldp_len != 0:
    chassis = list(lldp['lldp']['interface']['eth0']['chassis'])[0]
    descr = lldp['lldp']['interface']['eth0']['chassis'][chassis]['descr'].split()
    mac = lldp['lldp']['interface']['eth0']['chassis'][chassis]['id']['value']
    port = lldp['lldp']['interface']['eth0']['port']['id']['value']
    auto_negotiation = lldp['lldp']['interface']['eth0']['port']['auto-negotiation']['current'].split()
    vlan_id = lldp['lldp']['interface']['eth0']['vlan']['vlan-id']
    power_supported = lldp['lldp']['interface']['eth0']['port']['power']['supported']
    power_enabled = lldp['lldp']['interface']['eth0']['port']['power']['enabled']
    redis_db.hset('LLDP', 'chassis', chassis)
    redis_db.hset('LLDP', 'descr', str(descr[0]))
    redis_db.hset('LLDP', 'mac', mac)
    redis_db.hset('LLDP', 'port', port)
    redis_db.hset('LLDP', 'auto_negotiation', str(auto_negotiation[0]))
    redis_db.hset('LLDP', 'vlan_id', vlan_id)
    redis_db.hset('LLDP', 'power_supported', str(power_supported))
    redis_db.hset('LLDP', 'power_enabled', str(power_enabled))
    redis_db.hset('LLDP', 'power_enabled', str(power_enabled))
  else:
    redis_db.hset('LLDP', 'chassis', '--')
    redis_db.hset('LLDP', 'descr', '--')
    redis_db.hset('LLDP', 'mac', '--')
    redis_db.hset('LLDP', 'port', '--')
    redis_db.hset('LLDP', 'auto_negotiation', '--')
    redis_db.hset('LLDP', 'vlan_id', '--')
    redis_db.hset('LLDP', 'power_supported', '--')
    redis_db.hset('LLDP', 'power_enabled', '--')
    redis_db.hset('LLDP', 'power_enabled', '--')

def serial_displays(**kwargs):
    if kwargs['serial_display_type'] == 'lcd_st7735':
        from luma.core.interface.serial import spi
        from luma.core.render import canvas
        from luma.lcd.device import st7735
        from PIL import ImageFont
        from time import time, sleep
        import datetime
        #import logging
        import redis
    # Load default font.
        #font = ImageFont.load_default()
        font = ImageFont.truetype('/home/pi/scripts/RPiNT/FreePixel.ttf', 15)
    # Display width/height
        width = 128
        height = 128
    # First define some constants to allow easy resizing of shapes.
        padding = 0
        top = padding
        # bottom = height-padding
    # Move left to right keeping track of the current x position for drawing shapes.
        x = 0
        display_rotate = 0
        serial = spi(device=0, port=0, bus_speed_hz=8000000, transfer_size=4096, gpio_DC=25, gpio_RST=27)

        try:
            device = st7735(serial)
            device = st7735(serial, width=128, height=128, h_offset=1, v_offset=2, bgr=True, persist=False, rotate=display_rotate)

            while True:
                # get data from redis db
                lldp = redis_db.hgetall('LLDP')
                chassis = lldp['chassis']
                descr = lldp['descr']
                mac = lldp['mac']
                port = lldp['port']
                auto_negotiation = lldp['auto_negotiation']
                vlan_id = lldp['vlan_id']
                power_supported = lldp['power_supported']
                power_enabled = lldp['power_enabled']
                battery_power = redis_db.get('battery_power')

                # Draw
                with canvas(device) as draw:
                    draw.text((x+38, top), str(descr) , font=font, fill="yellow")
                    draw.text((x+1, top+15), 'Name', font=font, fill="lime")
                    draw.text((x+40, top+15), str(chassis), font=font, fill="cyan")

                    draw.text((x+1, top+30), 'Port',  font=font, fill="lime")
                    draw.text((x+40, top+30), str(port),  font=font, fill="cyan")

                    draw.text((x+1, top+45), 'VLANid',  font=font, fill="lime")
                    draw.text((x+56, top+45), str(vlan_id),  font=font, fill="cyan")

                    draw.text((x+1, top+60), 'PowerSup',  font=font, fill="lime")
                    draw.text((x+72, top+60), str(power_supported),  font=font, fill="cyan")

                    draw.text((x+1, top+75), 'PowerEn',  font=font, fill="lime")
                    draw.text((x+64, top+75), str(power_enabled),  font=font, fill="cyan")

                    draw.text((x+1, top+90), 'mode',  font=font, fill="lime")
                    draw.text((x+40, top+90), str(auto_negotiation),  font=font, fill="cyan")

                    draw.text((x+1, top+115), 'Power', font=font, fill="lime")
                    draw.text((x+42, top+115), str(battery_power)+'%',  font=font, fill="cyan")
                sleep(1/kwargs['serial_display_refresh_rate'])
        except Exception as err:
            print(err)


def threading_function(function_name, **kwargs):
    import threading
    t = threading.Thread(target=function_name, name=function_name, kwargs=kwargs)
    t.daemon = True
    t.start()


def db_connect(dbhost, dbnum):
    import redis
    import sys
    from systemd import journal

    try:
        redis_db = redis.StrictRedis(host=dbhost, port=6379, db=str(dbnum), charset="utf-8", decode_responses=True)
        redis_db.ping()
        return redis_db
    except:
        error = f"Can't connect to RedisDB host: {dbhost}"
        journal.send(error)
        sys.exit(error)


def config_load(path_to_config):
    import sys
    from systemd import journal

    try:
        import yaml
        with open(path_to_config, mode='r') as file:
            config_yaml = yaml.full_load(file)
        return config_yaml
    except:
        error = f"Can't load RPiNT config file: {path_to_config}"
        journal.send(error)
        sys.exit(error)


def ups_hat():
    from INA219 import INA219
    ina219 = INA219(addr=0x42)

    while True:
        bus_voltage = ina219.getBusVoltage_V()             # voltage on V- (load side)
        shunt_voltage = ina219.getShuntVoltage_mV() / 1000 # voltage between V+ and V- across the shunt
        current = ina219.getCurrent_mA()                   # current in mA
        power = ina219.getPower_W()                        # power in W
        p = (bus_voltage - 3)/1.2*100
        if(p > 100):p = 100
        if(p < 0):p = 0
        redis_db.set('battery_power', round(p))

def main():
    from gpiozero import Button
    from signal import pause
    import sys

    print('')
    print('# RPiNT is running #')
    print('')

    global redis_db
    redis_db = db_connect('localhost', 0)
    redis_db.flushdb()

    config_yaml = config_load('/home/pi/scripts/RPiNT/rpint.yaml')
    config = config_yaml['setup']

    lldp()

    if bool(config['use_ups_hat']) is True:
        threading_function(ups_hat)

    if bool(config['use_serial_display']) is True:
        threading_function(serial_displays, **config)

    button = Button(21, hold_time=5)
    button.when_pressed = lldp
    button.when_held = shutdown
    pause()


# --- Main program ---
if __name__ == '__main__':
    import pid
    try:
        with pid.PidFile('/home/pi/scripts/RPiNT/rpint.pid'):
            main()
    except KeyboardInterrupt:
        print('')
        print('# RPiNT is stopped #')
    except pid.PidFileError:
        print('')
        print('Another instance of RPiNT is already running. RPiNT will now close.')
    except Exception as err:
        print(err)
