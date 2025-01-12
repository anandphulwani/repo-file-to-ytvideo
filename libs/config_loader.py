# lib/config_loader.py
import configparser
import math

def convert_to_appropriate_type(value):
    """Try converting strings to integers or floats when possible."""
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value  # Return as string if not an int or float


def load_config(filename):
    """Load and return configuration settings with type-inferred values."""
    config = configparser.ConfigParser()
    config.read(filename)
    
    config_items = config.items('DEFAULT')

    config_dict = {}
    for key, value in config_items:
        config_dict[key] = convert_to_appropriate_type(value)
    if 'margin' in config_dict and 'padding' in config_dict and 'frame_width' in config_dict and 'frame_height' in config_dict:
        config_dict['start_width'] = int(config_dict['margin']) + int(config_dict['padding'])
        config_dict['end_width'] = int(config_dict['frame_width']) - int(config_dict['margin']) - int(config_dict['padding'])

        config_dict['start_height'] = int(config_dict['margin']) + int(config_dict['padding'])
        config_dict['end_height'] = int(config_dict['frame_height']) - int(config_dict['margin']) - int(config_dict['padding'])

        config_dict['usable_width'] = ( config_dict['end_width'] - config_dict['start_width'] ) // 2
        config_dict['usable_height'] = ( config_dict['end_height'] - config_dict['start_height'] ) // 2

        config_dict['bits_per_frame'] = math.floor((config_dict['usable_width'] * config_dict['usable_height']) / 8) * 8
    return config_dict
