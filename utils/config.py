import tomllib
import sys
from systemd import journal

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
