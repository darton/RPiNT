from time import sleep

def ups_hat(context):
    from .INA219 import INA219
    ina219 = INA219(addr=0x43)
    V_FULL = 4.2
    V_EMPTY = 3.0
    while not context.stop_event.is_set():
        bus_voltage = ina219.getBusVoltage_V()
        power = ina219.getPower_W()
        charge_level = max(0, min(100, ((bus_voltage - V_EMPTY) / (V_FULL - V_EMPTY)) * 100))
        pipe = context.redis_db.pipeline()
        pipe.set('battery_power', round(charge_level))
        pipe.set('battery_voltage', round(bus_voltage, 2))
        pipe.set('battery_load', round(power, 2))
        pipe.execute()
        sleep(1)
