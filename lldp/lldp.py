import subprocess
import json
import sys
from systemd import journal

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
    chassis = eth0_data.get("chassis", {})
    chassis_subkey = next(iter(chassis), None) if any(isinstance(v, dict) for v in chassis.values()) else None
    chassis_data = chassis.get(chassis_subkey, chassis)

    if chassis_subkey == "id":
        chassis_id = chassis_data.get("value", "N/A")
    else:
        chassis_id = chassis_data.get("id").get("value", "N/A")

    chassis_description = chassis_data.get("descr", "N/A")
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
        "management_ip": management_ip,
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
