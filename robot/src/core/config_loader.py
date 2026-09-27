import os
import json
import logging

logger = logging.getLogger("config_loader")

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
_config_cache = None

def load_config(force_reload=False):
    global _config_cache
    if _config_cache is not None and not force_reload:
        return _config_cache

    if not os.path.exists(CONFIG_PATH):
        logger.error(f"Configuration file not found at {CONFIG_PATH}")
        raise FileNotFoundError(f"Configuration file not found at {CONFIG_PATH}")

    try:
        with open(CONFIG_PATH, "r") as f:
            _config_cache = json.load(f)
        logger.info("Configuration loaded successfully.")
        return _config_cache
    except Exception as e:
        logger.exception("Failed to load config.json")
        raise e

def save_config(config_data=None):
    global _config_cache
    if config_data is not None:
        _config_cache = config_data
    elif _config_cache is None:
        return

    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(_config_cache, f, indent=2)
        logger.info("Configuration saved successfully to disk.")
    except Exception as e:
        logger.exception("Failed to save config.json")
        raise e

def update_offset(joint: str, offset_val: float):
    config = load_config()
    if "robot" not in config:
        config["robot"] = {}
    if "offsets" not in config["robot"]:
        config["robot"]["offsets"] = {}
    config["robot"]["offsets"][joint.upper()] = float(offset_val)
    save_config(config)
