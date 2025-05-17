import os
import signal
from gpiozero.pins.rpigpio import RPiGPIOFactory
from gpiozero import Button
from signal import pause
import threading
import sys
from systemd import journal

from app_context import AppContext
from utils.config import config_load
from utils.redis_utils import db_connect
from utils.threading_utils import threading_function
from lldp.lldp import lldp, save_lldp_to_redis
from display.controller import DisplayController
from power.ups_hat import ups_hat

def shutdown():
    from subprocess import check_call
    check_call(['sudo', 'poweroff'])

def lldp_worker(context: AppContext):
    from time import sleep
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

def main():
    print('\n# RPiNT is running #\n')
    CONFIG_PATH = os.getenv('RPINT_CONFIG_PATH', '/home/pi/scripts/RPiNT/rpint.toml')
    FONT_PATH = os.getenv('RPINT_FONT_PATH', '/home/pi/scripts/RPiNT/fonts/FreePixel.ttf')
    stop_threads = threading.Event()
    redis_db = db_connect('localhost', 0)
    redis_db.flushdb()
    config_full = config_load(CONFIG_PATH)
    config = config_full['setup']
    context = AppContext(config, FONT_PATH, redis_db, stop_threads)
    button_up = Button(6)
    button_down = Button(19)
    button_left = Button(5)
    button_right = Button(26)
    button = Button(21, hold_time=5)
    button.when_held = shutdown
    display_controller = DisplayController(context, button_up, button_down, button_left, button_right)
    signal.signal(signal.SIGTERM, lambda sig, frame: signal_handler(sig, frame, context))
    signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, context))
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
