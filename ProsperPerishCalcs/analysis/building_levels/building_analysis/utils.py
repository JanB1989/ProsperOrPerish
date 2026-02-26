import json
import os

def load_config():
    """Loads the configuration from config.json."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)
    
    # Resolve relative paths relative to base_dir
    resolved_config = {}
    for key, value in config.items():
        if key.endswith("_dir") or key == "analysis_dir":
            if not os.path.isabs(value):
                resolved_config[key] = os.path.abspath(os.path.join(base_dir, value))
            else:
                resolved_config[key] = value
        else:
            resolved_config[key] = value
    return resolved_config

def get_path(key):
    """Returns a path from the configuration."""
    config = load_config()
    return config.get(key)
