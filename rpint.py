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

import os
import json
import signal
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
    default_values = {
        'chassis_id': '--',
        'chassis_description': '--',
        'management_ip': '--',
        'port_id': '--',
        'port_descr': '--',
        'auto_neg_current': '--',
        'auto_supported': '--',
        'auto_enabled': '--',
        'available_modes_str': '--',
        'vlan_id': '--',
        'power_supported': '--',
        'power_enabled': '--',
        'lldp_med_device_type': '--',
        'lldp_med_capability': '--',
    }
    redis_db.hset('LLDP', mapping=default_values)



def lldp(command_runner=subprocess.run):
  command = ['lldpcli', 'show', 'neighbors', 'details', '-f', 'json']
  try:
      result = command_runner(command, text=True, capture_output=True, check=True)
      lldp = json.loads(result.stdout)
      lldp_len = len(lldp['lldp'])
  except subprocess.CalledProcessError as e:
      journal.send(f"LLDP command failed: {e}")
      hset_init_values()
      return
  except json.JSONDecodeError as e:
      journal.send(f"Failed to parse LLDP JSON: {e}")
      hset_init_values()
      return

  if lldp_len != 0:

    eth0_data = lldp.get("lldp", {}).get("interface", {}).get("eth0", {})

    # Retrieving the dynamic Chassis ID (first available key)
    chassis_key = next(iter(eth0_data.get("chassis", {})), "Unknown")
    chassis_data = eth0_data.get("chassis", {}).get(chassis_key, {})
    # Retrieving key data
    chassis_id = chassis_data.get("value", "N/A")
    chassis_description = eth0_data.get("chassis", {}).get("descr", "N/A")
    management_ip = ", ".join(chassis_data.get("mgmt-ip", ["N/A"]))

    port_data = eth0_data.get("port", {})
    port_id = port_data.get("id", {}).get("value", "N/A")
    port_descr = port_data.get("descr", "N/A")
    auto_neg_current = port_data.get("auto-negotiation", {}).get("current", "N/A")
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
        "chassis_description": chassis_description,
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



# Initialization of the scrolling index
scroll_index = 0
max_lines = 3  # Number of lines visible on the screen
# Function for handling vertical scrolling
def update_scroll_y(button):
    global scroll_index, data_lines, max_lines
    if len(data_lines) > max_lines:  # Ensures that scrolling is possible only if there are additional lines.
        if button == button_up:
            scroll_index = max(0, scroll_index - 1)  # Scrolling up
        elif button == button_down:
            scroll_index = min(len(data_lines) - max_lines, scroll_index + 1)  # Scrolling down


scroll_x = 0
# Function for handling horizontal scrolling
def update_scroll_x(button):
    MAX_SCROLL_X = 256
    global scroll_x
    if button == button_left:
        scroll_x = max(0, scroll_x - 20)  # Scrolling to the left.
    elif button == button_right:
        scroll_x = min(MAX_SCROLL_X, scroll_x + 20)  # Scrolling to the right.



def serial_displays(**config):
    global data_lines

    if config['serial_display_type'] == 'lcd_st7735':
        width, height = 128, 128
        x = 0
        display_rotate = 0

        serial = spi(device=0, port=0, bus_speed_hz=8000000, transfer_size=4096, gpio_DC=25, gpio_RST=27)
        device = st7735(serial)
        device = st7735(serial, width=128, height=128, h_offset=1, v_offset=2, bgr=True, persist=False, rotate=display_rotate)

        while not stop_threads.is_set():
            lldp = redis_db.hgetall('LLDP')
            data_lines = []
            if config.get("show_chassis_id", False) is True:
                data_lines.append(f"CHASSIS ID: {lldp.get('chassis_id', '-')}")

            if config.get("show_chassis_description", False) is True:
                data_lines.append(f"CHASSIS DESCRIPTION: {lldp.get('chassis_description', '-')}")

            if config.get("show_port_id", False) is True:
                data_lines.append(f"PORT ID: {lldp.get('port_id', '-')}")

            if config.get("show_vlan_id", False) is True:
                data_lines.append(f"VLAN ID: {lldp.get('vlan_id', '-')}")

            if config.get("show_port_descr", False) is True:
                data_lines.append(f"PORT DESCRIPTION: {lldp.get('port_descr', '-')}")

            if config.get("show_auto_neg_current", False) is True:
                data_lines.append(f"CURRENT MODE: {lldp.get('auto_neg_current', '-')}")

            if config.get("show_auto_supported", False) is True:
                data_lines.append(f"AUTO SUPPORT: {lldp.get('auto_supported', '-')}")

            if config.get("show_auto_enabled", False) is True:
                data_lines.append(f"AUTO ENABLE: {lldp.get('auto_enabled', '-')}")

            if config.get("show_available_modes_str", False) is True:
                data_lines.append(f"AVAILABLE MODES: {lldp.get('available_modes_str', '-')}")

            if config.get("show_power_supported", False) is True:
                data_lines.append(f"POWER SUPPORT: {lldp.get('power_supported', '-')}")

            if config.get("show_power_enabled", False) is True:
                data_lines.append(f"POWER ENABLED: {lldp.get('power_enabled', '-')}")

            if config.get("show_device_type", False) is True:
                data_lines.append(f"DEVICE TYPE: {lldp.get('lldp_med_device_type', '-')}")


            visible_lines = data_lines[scroll_index:scroll_index + max_lines]

            with canvas(device) as draw:
                font_size = config['font_size']
                font = ImageFont.truetype(FONT_PATH, font_size)
                y_offset = 25  # "Initial position on the screen.
                line_spacing = font_size + 1  # Line spacing.

                # "Static row for the battery power indicator.
                if bool(config.get('use_ups_hat', False)) is True:
                    battery_power = redis_db.get('battery_power')
                    draw.text((x+1, 0), f"Battery Power {battery_power}%", font=font, fill="yellow")

                # Displaying scrolled data with horizontal offset.
                for i, line in enumerate(visible_lines, start=0):
                    label, value = line.split(": ")
                    x_position = x+1 - scroll_x
                    y_position = y_offset + ( line_spacing * 2 * i )
                    draw.text((x_position, y_position), label, font=font, fill="lime")  # Name
                    draw.text((x_position, y_position + line_spacing), f"{value}", font=font, fill="cyan")  # Value

            sleep(1/config['serial_display_refresh_rate'])



def threading_function(function_name: callable, **kwargs) -> threading.Thread:
    """
    Starts a daemon thread to run the specified function with the given keyword arguments.

    :param function_name: The function to be executed in the thread.
    :param kwargs: Keyword arguments to be passed to the function.
    :return: The created and started Thread object.
    """
    try:
        # Use the function name for the thread's name (or fallback to a default name)
        thread_name = f"Thread-{function_name.__name__}" if callable(function_name) else "Unnamed-Thread"

        # Create and start the thread
        t = threading.Thread(target=function_name, name=thread_name, kwargs=kwargs)
        t.daemon = True  # Ensure the thread exits when the main program exits
        t.start()
        # Log thread creation (optional)
        journal.send(f"Thread '{thread_name}' started successfully.")
        return t  # Return the thread object for further management if needed
    except Exception as e:
        # Log the error and re-raise it
        journal.send(f"Error starting thread for '{function_name.__name__}': {e}")
        raise RuntimeError(f"Failed to start thread '{thread_name}'") from e


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
    except FileNotFoundError:
        error = f"Can't load RPiNT config file: {path_to_config}"
        journal.send(error)
        sys.exit(error)
    except tomllib.TOMLDecodeError:
        error = f"Invalid TOML syntax in config file: {path_to_config}"
        journal.send(error)
        sys.exit(error)


def ups_hat():
    from INA219 import INA219
    ina219 = INA219(addr=0x43)
    # Voltage thresholds for a Li-Ion battery
    V_FULL = 4.2  # Fully charged battery voltage
    V_EMPTY = 3.0  # Fully discharged battery voltage

    while not stop_threads.is_set():
        bus_voltage = ina219.getBusVoltage_V()             # voltage on V- (load side)
        shunt_voltage = ina219.getShuntVoltage_mV() / 1000 # voltage between V+ and V- across the shunt
        current = ina219.getCurrent_mA()                   # current in mA
        power = ina219.getPower_W()                        # power in W
        charge_level = max(0, min(100, ((bus_voltage - V_EMPTY) / (V_FULL - V_EMPTY)) * 100))
        pipe = redis_db.pipeline()
        pipe.set('battery_power', round(charge_level))
        pipe.set('battery_voltage', round(bus_voltage, 2))
        pipe.set('battery_load', round(power, 2))
        pipe.execute()
        sleep(1)



def lldpd():
    while not stop_threads.is_set():
        lldp()
        sleep(2)



def signal_handler(sig, frame):
    print("Received termination signal, stopping threads...")
    stop_threads.set()
    for t in threads:
        t.join()  # Ensure all threads finish execution
    sys.exit(0)



# --- Main program ---
if __name__ == '__main__':
    # Register SIGTERM signal handler for systemd shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler) # Handle Ctrl+C for local testing

    print('')
    print('# RPiNT is running #')
    print('')

    CONFIG_PATH = os.getenv('RPINT_CONFIG_PATH', '/home/pi/scripts/RPiNT/rpint.toml')
    FONT_PATH = os.getenv('RPINT_FONT_PATH', '/home/pi/scripts/RPiNT/FreePixel.ttf')

    factory = RPiGPIOFactory

    button = Button(21, hold_time=5)
    button_up = Button(6)
    button_down = Button(19)
    button_left = Button(5)
    button_right = Button(26)

    button_up.when_pressed = lambda: update_scroll_y(button_up)
    button_down.when_pressed = lambda: update_scroll_y(button_down)
    button_left.when_pressed = lambda: update_scroll_x(button_left)
    button_right.when_pressed = lambda: update_scroll_x(button_right)

    try:
        redis_db = db_connect('localhost', 0)
        redis_db.flushdb()

        config_full = config_load(CONFIG_PATH)
        config = config_full['setup']

        hset_init_values()

        stop_threads = threading.Event()

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
    except KeyboardInterrupt:
        stop_threads.set()
        print('')
        print('RPiNT is stopped #')
    except Exception as err:
        stop_threads.set()
        print(f'Main Function Error: {err}')

