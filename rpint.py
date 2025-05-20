#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
#  Author : Dariusz Kowalczyk
#  GPL v2

import os
import json
import signal
import subprocess
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

# --- Helpers & Data Classes ---
class AppContext:
    """Stores context and shared resources."""
    def __init__(self, config, font_path, redis_db, stop_event):
        self.config = config
        self.font_path = font_path
        self.redis_db = redis_db
        self.stop_event = stop_event

def hset_init_values():
    return {
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

def lldp(command_runner=subprocess.run):
    command = ['lldpcli', 'show', 'neighbors', 'details', '-f', 'json']
    try:
        result = command_runner(command, text=True, capture_output=True, check=True)
        lldp = json.loads(result.stdout)
        lldp_len = len(lldp['lldp'])
    except subprocess.CalledProcessError as e:
        journal.send(f"LLDP command failed: {e}")
        return None
    except json.JSONDecodeError as e:
        journal.send(f"Failed to parse LLDP JSON: {e}")
        return None

    if lldp_len == 0:
        return None

    eth0_data = lldp.get("lldp", {}).get("interface", {}).get("eth0", {})
    chassis_key = next(iter(eth0_data.get("chassis", {})), "Unknown")
    chassis_data = eth0_data.get("chassis", {}).get(chassis_key, {})
    chassis_id = chassis_data.get("value", "N/A")
    chassis_description = eth0_data.get("chassis", {}).get("descr", "N/A")
    management_ip = ", ".join(chassis_data.get("mgmt-ip", ["N/A"]))
    port_data = eth0_data.get("port", {})
    port_id = port_data.get("id", {}).get("value", "N/A")
    port_descr = port_data.get("descr", "N/A")
    auto_neg_current = port_data.get("auto-negotiation", {}).get("current", "N/A")
    auto_supported = port_data.get("auto-negotiation", {}).get("supported", "N/A")
    auto_enabled = port_data.get("auto-negotiation", {}).get("enabled", "N/A")
    advertised_modes = port_data.get("auto-negotiation", {}).get("advertised", [])
    available_modes = []
    if isinstance(advertised_modes, list):
        for mode in advertised_modes:
            mode_type = mode.get("type", "Unknown")
            hd = "HD" if mode.get("hd", False) else ""
            fd = "FD" if mode.get("fd", False) else ""
            available_modes.append(f"{mode_type}/{hd}/{fd}".strip())
    elif isinstance(advertised_modes, str):
        available_modes.append(advertised_modes)
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
    return LLDP

def save_lldp_to_redis(lldp_data, redis_db):
    if lldp_data is None:
        lldp_data = hset_init_values()
    redis_db.hset('LLDP', mapping=lldp_data)

def get_max_content_width(data_lines, font_path, font_size, serial_display_width):
    font = ImageFont.truetype(font_path, font_size)
    max_width = 0
    for line in data_lines:
        try:
            label, value = line.split(": ", 1)
        except ValueError:
            value = line
        width = font.getlength(value)
        if width > max_width:
            max_width = width
    return max_width

def update_max_scroll_x(data_lines, font_path, font_size, serial_display_width):
    max_content_width = get_max_content_width(data_lines, font_path, font_size, serial_display_width)
    return max(0, int(max_content_width - serial_display_width + 10))

def shutdown():
    check_call(['sudo', 'poweroff'])

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

# --- Display logic class ---
class DisplayController:
    def __init__(self, context: AppContext, button_up, button_down, button_left, button_right):
        self.context = context
        self.scroll_x = 0
        self.scroll_index = 0
        self.max_lines = 3
        self.data_lines = []
        self.button_up = button_up
        self.button_down = button_down
        self.button_left = button_left
        self.button_right = button_right

        # Attach callbacks
        self.button_up.when_pressed = self.update_scroll_y_up
        self.button_down.when_pressed = self.update_scroll_y_down
        self.button_left.when_pressed = self.update_scroll_x_left
        self.button_right.when_pressed = self.update_scroll_x_right

    def update_scroll_x_left(self):
        self.scroll_x = max(0, self.scroll_x - 20)

    def update_scroll_x_right(self):
        max_scroll_x = update_max_scroll_x(
            self.data_lines, self.context.font_path, self.context.config['font_size'],
            self.context.config.get('serial_display_width', 128)
        )
        self.scroll_x = min(max_scroll_x, self.scroll_x + 20)

    def update_scroll_y_up(self):
        if len(self.data_lines) > self.max_lines:
            self.scroll_index = max(0, self.scroll_index - 1)

    def update_scroll_y_down(self):
        if len(self.data_lines) > self.max_lines:
            self.scroll_index = min(len(self.data_lines) - self.max_lines, self.scroll_index + 1)

    def serial_displays(self):
        c = self.context
        if c.config['serial_display_type'] == 'lcd_st7735':
            DISPLAY_WIDTH = c.config.get('serial_display_width', 128)
            DISPLAY_HEIGHT = c.config.get('serial_display_height', 128)
            DISPLAY_ROTATE = c.config.get('serial_display_rotate', 0)
            DISPLAY_HORIZONTAL_OFFSET = c.config.get('serial_display_horizontal_offset', 1)
            DISPLAY_VERTICAL_OFFSET = c.config.get('serial_display_vertical_offset', 2)
            DISPLAY_BACKGROUND = str(c.config.get('serial_display_background', True))
            x = 0

            serial = spi(device=0, port=0, bus_speed_hz=8000000, transfer_size=4096, gpio_DC=25, gpio_RST=27)
            device = st7735(serial, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT,
                            h_offset=DISPLAY_HORIZONTAL_OFFSET, v_offset=DISPLAY_VERTICAL_OFFSET,
                            bgr=DISPLAY_BACKGROUND, persist=False, rotate=DISPLAY_ROTATE)
            while not c.stop_event.is_set():
                lldp = c.redis_db.hgetall('LLDP')
                self.data_lines = []
                if c.config.get("show_chassis_id", False): self.data_lines.append(f"CHASSIS ID: {lldp.get('chassis_id', '-')}")
                if c.config.get("show_chassis_description", False): self.data_lines.append(f"CHASSIS DESCRIPTION: {lldp.get('chassis_description', '-')}")
                if c.config.get("show_port_id", False): self.data_lines.append(f"PORT ID: {lldp.get('port_id', '-')}")
                if c.config.get("show_vlan_id", False): self.data_lines.append(f"VLAN ID: {lldp.get('vlan_id', '-')}")
                if c.config.get("show_port_descr", False): self.data_lines.append(f"PORT DESCRIPTION: {lldp.get('port_descr', '-')}")
                if c.config.get("show_auto_neg_current", False): self.data_lines.append(f"CURRENT MODE: {lldp.get('auto_neg_current', '-')}")
                if c.config.get("show_auto_supported", False): self.data_lines.append(f"AUTO SUPPORT: {lldp.get('auto_supported', '-')}")
                if c.config.get("show_auto_enabled", False): self.data_lines.append(f"AUTO ENABLE: {lldp.get('auto_enabled', '-')}")
                if c.config.get("show_available_modes_str", False): self.data_lines.append(f"AVAILABLE MODES: {lldp.get('available_modes_str', '-')}")
                if c.config.get("show_power_supported", False): self.data_lines.append(f"POWER SUPPORT: {lldp.get('power_supported', '-')}")
                if c.config.get("show_power_enabled", False): self.data_lines.append(f"POWER ENABLED: {lldp.get('power_enabled', '-')}")
                if c.config.get("show_device_type", False): self.data_lines.append(f"DEVICE TYPE: {lldp.get('lldp_med_device_type', '-')}")
                visible_lines = self.data_lines[self.scroll_index:self.scroll_index + self.max_lines]

                with canvas(device) as draw:
                    font = ImageFont.truetype(c.font_path, c.config['font_size'])
                    y_offset = 25
                    line_spacing = c.config['font_size'] + 1
                    if c.config.get('use_ups_hat', False):
                        battery_power = c.redis_db.get('battery_power')
                        draw.text((x+1, 0), f"Battery Power {battery_power}%", font=font, fill="yellow")

                    for i, line in enumerate(visible_lines, start=0):
                        try:
                            label, value = line.split(": ")
                        except ValueError:
                            label, value = line, ""
                        x_position = x+1 - self.scroll_x
                        y_position = y_offset + (line_spacing * 2 * i)
                        draw.text((x_position, y_position), label, font=font, fill="lime")
                        draw.text((x_position, y_position + line_spacing), f"{value}", font=font, fill="cyan")
                sleep(1 / c.config['serial_display_refresh_rate'])

# --- Other thread functions ---

def ups_hat(context: AppContext):
    from INA219 import INA219
    ina219 = INA219(addr=0x43)
    V_FULL = 4.2
    V_EMPTY = 3.0

    while not context.stop_event.is_set():
        bus_voltage = ina219.getBusVoltage_V()
        shunt_voltage = ina219.getShuntVoltage_mV() / 1000
        current = ina219.getCurrent_mA()
        power = ina219.getPower_W()
        charge_level = max(0, min(100, ((bus_voltage - V_EMPTY) / (V_FULL - V_EMPTY)) * 100))
        pipe = context.redis_db.pipeline()
        pipe.set('battery_power', round(charge_level))
        pipe.set('battery_voltage', round(bus_voltage, 2))
        pipe.set('battery_load', round(power, 2))
        pipe.execute()
        sleep(1)

def lldp_worker(context: AppContext):
    while not context.stop_event.is_set():
        lldp_data = lldp()
        save_lldp_to_redis(lldp_data, context.redis_db)
        sleep(2)

def signal_handler(sig, frame, context: AppContext):
    error = f"Received termination signal, stopping threads..."
    journal.send(error)
    context.stop_event.set()
    journal.send(f"All threads have been signaled to stop.")
    sys.exit(error)

def threading_function(function_name: callable, args=(), kwargs=None, name=None):
    if kwargs is None:
        kwargs = {}
    try:
        thread_name = name or f"Thread-{function_name.__name__}"
        t = threading.Thread(target=function_name, name=thread_name, args=args, kwargs=kwargs)
        t.daemon = True
        t.start()
        journal.send(f"Thread '{thread_name}' started successfully.")
        return t
    except Exception as e:
        journal.send(f"Error starting thread for '{function_name.__name__}': {e}")
        raise RuntimeError(f"Failed to start thread '{thread_name}'") from e

# --- Main program ---
def main():
    print('\n# RPiNT is running #\n')
    CONFIG_PATH = os.getenv('RPINT_CONFIG_PATH', '/home/pi/scripts/RPiNT/rpint.toml')
    FONT_PATH = os.getenv('RPINT_FONT_PATH', '/home/pi/scripts/RPiNT/FreePixel.ttf')

    stop_threads = threading.Event()
    redis_db = db_connect('localhost', 0)
    redis_db.flushdb()
    config_full = config_load(CONFIG_PATH)
    config = config_full['setup']

    # Context with all resources
    context = AppContext(config, FONT_PATH, redis_db, stop_threads)

    # Buttons
    button_up = Button(6)
    button_down = Button(19)
    button_left = Button(5)
    button_right = Button(26)
    button = Button(21, hold_time=5)

    # Shutdown
    button.when_held = shutdown

    # Display
    display_controller = DisplayController(context, button_up, button_down, button_left, button_right)

    # Signal handling
    signal.signal(signal.SIGTERM, lambda sig, frame: signal_handler(sig, frame, context))
    signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, context))

    # Threads
    if bool(config.get('use_ups_hat')): threading_function(ups_hat, args=(context,))
    if bool(config.get('use_serial_display')): threading_function(display_controller.serial_displays)
    if bool(config.get('auto_lldp_read')): threading_function(lldp_worker, args=(context,))
    else:
        button.when_pressed = lambda: lldp()

    pause()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        error = f"RPiNT is stopped from keyboard"
        journal.send(error)
        sys.exit(error)
    except Exception as err:
        error = f"Main Function Error: {err}"
        journal.send(error)
        sys.exit(error)
