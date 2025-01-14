# lib/config_loader.py
import configparser
import math
import os
import json


def convert_to_appropriate_type(value):
    """Try converting strings to integers or floats when possible."""
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value  # Return as string if not an int or float


def parse_list(value):
    """
    Parse a string representation of a list into an actual Python list.
    Assumes the list is in JSON format (e.g., "[1, 2, 3]").
    """
    value = value.split('#')[0].strip()
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
        else:
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise ValueError(f"Invalid list format: {value}")


def load_config(filename):
    """Load and return configuration settings with type-inferred values and validations."""
    config = configparser.ConfigParser()
    config.read(filename)

    config_items = config.items('DEFAULT')

    config_dict = {}
    for key, value in config_items:
        if key in ['repeat_same_frame', 'pick_frame_to_read', 'data_box_size_step']:
            # Parse the list from JSON format
            config_dict[key] = parse_list(value)
            # Ensure all elements are integers
            if not all(isinstance(item, int) for item in config_dict[key]):
                raise ValueError(f"All elements in '{key}' must be integers.")
        else:
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

    # Validation Rule 1:
    if 'pick_frame_to_read' in config_dict and 'repeat_same_frame' in config_dict:
        pick = config_dict['pick_frame_to_read']
        repeat = config_dict['repeat_same_frame']
        if len(pick) != len(repeat):
            raise ValueError("Length of 'pick_frame_to_read' must match 'repeat_same_frame'.")

        for idx, (p, r) in enumerate(zip(pick, repeat)):
            if p > r:
                raise ValueError(f"'pick_frame_to_read' at index {idx} ({p}) "
                                 f"cannot be greater than 'repeat_same_frame' ({r}).")

    # Validation Rule 2:
    if 'data_box_size_step' in config_dict:
        steps = config_dict['data_box_size_step']
        for idx, step in enumerate(steps):
            if not (1 <= step <= 50):
                raise ValueError(f"'data_box_size_step' at index {idx} ({step}) "
                                 f"must be between 1 and 50 (inclusive).")

    return config_dict
