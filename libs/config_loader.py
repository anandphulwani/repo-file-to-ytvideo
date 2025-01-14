# lib/config_loader.py
import configparser
import math
import os


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

    # Adjust encoding_map_path based on the OS
    if 'encoding_map_path' in config_dict:
        if os.name == 'nt':  # Windows
            config_dict['encoding_map_path'] = config_dict['encoding_map_path'].replace('/', '\\')
        else:  # Linux/Unix
            config_dict['encoding_map_path'] = config_dict['encoding_map_path'].replace('\\', '/')

    # Calculate derived configuration values
    required_keys = ['margin', 'padding', 'frame_width', 'frame_height']
    if all(key in config_dict for key in required_keys):
        margin = int(config_dict['margin'])
        padding = int(config_dict['padding'])
        frame_width = int(config_dict['frame_width'])
        frame_height = int(config_dict['frame_height'])

        config_dict['start_width'] = margin + padding
        config_dict['end_width'] = frame_width - margin - padding

        config_dict['start_height'] = margin + padding
        config_dict['end_height'] = frame_height - margin - padding

        config_dict['usable_width'] = (config_dict['end_width'] - config_dict['start_width']) // 2
        config_dict['usable_height'] = (config_dict['end_height'] -
                                        config_dict['start_height']) // 2

        config_dict['bits_per_frame'] = math.floor(
            (config_dict['usable_width'] * config_dict['usable_height']) / 8) * 8
    return config_dict
