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

import json
import subprocess
import pprint
import threading
import redis
import sys
import tomllib
from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.lcd.device import st7735
from PIL import ImageFont
from time import sleep
from systemd import journal
from gpiozero.pins.rpigpio import RPiGPIOFactory
from gpiozero import Button
from signal import pause
from subprocess import check_call


# --- Functions ---
def shutdown():
    check_call(['sudo', 'poweroff'])


def hset_init_values():
    redis_db.hset('LLDP', 'chassis', '--')
    redis_db.hset('LLDP', 'port', '--')
    redis_db.hset('LLDP', 'auto_negotiation', '--')
    redis_db.hset('LLDP', 'vlan_id', '--')
    redis_db.hset('LLDP', 'power_supported', '--')
    redis_db.hset('LLDP', 'power_enabled', '--')


def lldp():
  command = ('lldpcli show neighbors details -f json')
  p = subprocess.Popen(command, universal_newlines=True,
  shell=True, stdout=subprocess.PIPE,
  stderr=subprocess.PIPE)
  text = p.stdout.read()
  retcode = p.wait()
  lldp = json.loads(text)
  lldp_len = len(lldp['lldp'])
  #pprint.pprint(lldp)

  if lldp_len != 0:

    eth0_data = lldp.get("lldp", {}).get("interface", {}).get("eth0", {})

    # Retrieving the dynamic Chassis ID (first available key)
    chassis_key = next(iter(eth0_data.get("chassis", {})), "Unknown")
    chassis_data = eth0_data.get("chassis", {}).get(chassis_key, {})

    # Retrieving key data.
    chassis_id = chassis_data.get("id", {}).get("value", "N/A")
    system_name = chassis_data.get("descr", "N/A").split()[0]
    management_ip = ", ".join(chassis_data.get("mgmt-ip", ["N/A"])).split()[0]

    port_data = eth0_data.get("port", {})
    port_id = port_data.get("id", {}).get("value", "N/A")
    port_descr = port_data.get("descr", "N/A")
    auto_neg_current = port_data.get("auto-negotiation", {}).get("current", "N/A").split()[0]
    auto_supported = port_data.get("auto-negotiation", {}).get("supported", "N/A")
    auto_enabled = port_data.get("auto-negotiation", {}).get("enabled", "N/A")

    # Retrieving the list of available connection modes.
    #advertised_modes = port_data.get("auto-negotiation", {}).get("advertised", [])
    #available_modes = ", ".join([f"{mode.get('type', 'Unknown')} ({'HD' if mode.get('hd', False) else ''} {'FD' if mode.get('fd', False) else ''})".strip() for mode in advertised_modes])
    # Retrieving the list of available connection modes.
    advertised_modes = port_data.get("auto-negotiation", {}).get("advertised", [])
    # Checking whether advertised_modes is a list or a string.
    available_modes = []
    if isinstance(advertised_modes, list):  # If it's a list, we process it as before.
        for mode in advertised_modes:
            mode_type = mode.get("type", "Unknown")
            hd = "HD" if mode.get("hd", False) else ""
            fd = "FD" if mode.get("fd", False) else ""
            available_modes.append(f"{mode_type}/{hd}/{fd}".strip())
    elif isinstance(advertised_modes, str):  # If it's a string, we save it directly.
        available_modes.append(advertised_modes)
    # Conversion of a list to a string for storage in Redis.
    available_modes_str = ",".join(available_modes)

    vlan_id = eth0_data.get("vlan", {}).get("vlan-id", "N/A")
    power_supported = port_data.get("power", {}).get("supported", "N/A")
    power_enabled = port_data.get("power", {}).get("enabled", "N/A")
    lldp_med = eth0_data.get("lldp-med", {})
    device_type = lldp_med.get("device-type", "N/A")
    capability = lldp_med.get("capability", {}).get("available", "N/A")


    LLDP = {
        "chassis_id": chassis_id,
        "system_name": system_name,
        "management_ips": management_ip,
        "port_id": port_id,
        "port_descr": port_descr,
        "auto_neg_current": auto_neg_current,
        "auto_supported": str(auto_supported),
        "auto_enabled": str(auto_enabled),
        "available_modes_str": available_modes_str,
        "vlan_id": vlan_id,
        "power_supported": str(power_supported),
        "power_enabled": str(power_enabled),
        "lldp_med_device_type": device_type,
        "lldp_med_capability": str(capability)
    }

    redis_db.hset('LLDP', mapping=LLDP)
  else:
    hset_init_values()


# Buttons
button_up = Button(6)
button_down = Button(19)
button_left = Button(5)
button_right = Button(26)

# Initialization of the scrolling index"
scroll_index = 0
scroll_x = 0 #
max_lines = 3  # Number of lines visible on the screen
data_lines = []

# Function for handling vertical scrolling
def update_scrolly(button):
    global scroll_index, data_lines, max_lines
    if len(data_lines) > max_lines:  # Ensures that scrolling is possible only if there are additional lines.
        if button == button_up:
            scroll_index = max(0, scroll_index - 1)  # Scrolling up
        elif button == button_down:
            scroll_index = min(len(data_lines) - max_lines, scroll_index + 1)  # Scrolling down



# Function for handling horizontal scrolling
MAX_SCROLL_X = 1000
def update_scroll_x(button):
    global scroll_x
    if button == button_left:
        scroll_x = max(0, scroll_x - 20)  # Scrolling to the left.
    elif button == button_right:
        scroll_x = min(MAX_SCROLL_X, scroll_x + 20)  # Scrolling to the right.



# Przypisanie funkcji do przycisków
button_up.when_pressed = lambda: update_scrolly(button_up)
button_down.when_pressed = lambda: update_scrolly(button_down)
button_left.when_pressed = lambda: update_scroll_x(button_left)
button_right.when_pressed = lambda: update_scroll_x(button_right)


def serial_displays(**kwargs):
    global data_lines
    if kwargs['serial_display_type'] == 'lcd_st7735':
        width, height = 128, 128
        x = 0
        padding = 0
        top = padding
        display_rotate = 0

        serial = spi(device=0, port=0, bus_speed_hz=8000000, transfer_size=4096, gpio_DC=25, gpio_RST=27)
        device = st7735(serial)
        device = st7735(serial, width=128, height=128, h_offset=1, v_offset=2, bgr=True, persist=False, rotate=display_rotate)

        while True:
            lldp = redis_db.hgetall('LLDP')
            if config.get("show_chassis_id", False) is True:
                data_lines.append(f"Chassis Id: {lldp.get('chassis_id', '-')}")

            if config.get("show_name", False) is True:
                data_lines.append(f"System Name: {lldp.get('system_name', '-')}")

            if config.get("show_port_id", False) is True:
                data_lines.append(f"Port Id: {lldp.get('port_id', '-')}")

            if config.get("show_vlan_id", False) is True:
                data_lines.append(f"+ VLAN Id: {lldp.get('vlan_id', '-')}")

            if config.get("show_port_descr", False) is True:
                data_lines.append(f"Description: {lldp.get('port_descr', '-')}")

            if config.get("show_auto_neg_current", False) is True:
                data_lines.append(f"Current Mode: {lldp.get('auto_neg_current', '-')}")

            if config.get("show_auto_supported", False) is True:
                data_lines.append(f"Auto Support: {lldp.get('auto_supported', '-')}")

            if config.get("show_auto_enabled", False) is True:
                data_lines.append(f"Auto Enable: {lldp.get('auto_enabled', '-')}")

            if config.get("show_available_modes_str", False) is True:
                data_lines.append(f"Available Modes: {lldp.get('available_modes_str', '-')}")

            if config.get("show_power_supported", False) is True:
                data_lines.append(f"Power Support: {lldp.get('power_supported', '-')}")

            if config.get("show_power_enabled", False) is True:
                data_lines.append(f"Power Enabled: {lldp.get('power_enabled', '-')}")

            if config.get("show_device_type", False) is True:
                data_lines.append(f"Current Mode: {lldp.get('auto_neg_current', '-')}")


            visible_lines = data_lines[scroll_index:scroll_index + max_lines]

            with canvas(device) as draw:
                font_size = kwargs['font_size']
                font = ImageFont.truetype('/home/pi/scripts/RPiNT/FreePixel.ttf', font_size)
                y_offset = 25  # "Initial position on the screen.
                line_spacing = font_size + 1  # Line spacing.

                # "Static row for the battery power indicator.
                if bool(config.get('use_ups_hat', False)) is True:
                    battery_power = redis_db.get('battery_power')
                    draw.text((x+1, 0), f"Batt. Power {battery_power}%", font=font, fill="yellow")

                # Displaying scrolled data with horizontal offset.
                for i, line in enumerate(visible_lines, start=0):
                    label, value = line.split(": ")
                    x_position = x+1 - scroll_x
                    y_position = y_offset + ( line_spacing * 2 * i )
                    draw.text((x_position, y_position), label, font=font, fill="lime")  # Name
                    draw.text((x_position, y_position + line_spacing), value, font=font, fill="cyan")  # Value

            sleep(1/kwargs['serial_display_refresh_rate'])



def threading_function(function_name, **kwargs):
    t = threading.Thread(target=function_name, name=function_name, kwargs=kwargs)
    t.daemon = True
    t.start()


def db_connect(dbhost, dbnum):
    try:
        redis_db = redis.StrictRedis(host=dbhost, port=6379, db=str(dbnum), charset="utf-8", decode_responses=True)
        redis_db.ping()
        return redis_db
    except:
        error = f"Can't connect to RedisDB host: {dbhost}"
        journal.send(error)
        sys.exit(error)


def config_load(path_to_config):
    try:
        with open(path_to_config, "rb") as file:
            config_toml = tomllib.load(file)
        return config_toml
    except:
        error = f"Can't load RPiNT config file: {path_to_config}"
        journal.send(error)
        sys.exit(error)


def ups_hat():
    from INA219 import INA219
    ina219 = INA219(addr=0x43)

    while True:
        bus_voltage = ina219.getBusVoltage_V()             # voltage on V- (load side)
        shunt_voltage = ina219.getShuntVoltage_mV() / 1000 # voltage between V+ and V- across the shunt
        current = ina219.getCurrent_mA()                   # current in mA
        power = ina219.getPower_W()                        # power in W
        p = (bus_voltage - 3)/1.2*100
        if(p > 100):p = 100
        if(p < 0):p = 0
        redis_db.set('battery_power', round(p))


def lldpd():
  while True:
    lldp()
    sleep(2)


def main():
    factory = RPiGPIOFactory
    button = Button(21, hold_time=5)

    print('')
    print('# RPiNT is running #')
    print('')

    global redis_db
    redis_db = db_connect('localhost', 0)
    redis_db.flushdb()

    config_full = config_load('/home/pi/scripts/RPiNT/rpint.toml')
    global config
    config = config_full['setup']

    hset_init_values()

    if bool(config['use_ups_hat']) is True:
        threading_function(ups_hat)

    if bool(config['use_serial_display']) is True:
        threading_function(serial_displays, **config)

    if bool(config['auto_lldp_read']) is True:
        threading_function(lldpd)
    else:
        button.when_pressed = lldp

    button.when_held = shutdown
    pause()


# --- Main program ---
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('')
        print('RPiNT is stopped #')
    except Exception as err:
        print(f'Main Function Error: {err}')

