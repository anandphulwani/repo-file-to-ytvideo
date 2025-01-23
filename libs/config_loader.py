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
        if key in ['total_frames_repetition', 'pick_frame_to_read', 'data_box_size_step']:
            # Parse the list from JSON format
            config_dict[key] = parse_list(value)
            # Ensure all elements are integers
            if not all(isinstance(item, int) for item in config_dict[key]):
                raise ValueError(f"All elements in '{key}' must be integers.")
        elif key == 'allow_byte_to_be_split_between_frames':
            # Parse and validate boolean value
            lower_value = value.lower().strip()
            if lower_value in ['true', 'yes', '1']:
                config_dict[key] = True
            elif lower_value in ['false', 'no', '0']:
                config_dict[key] = False
            else:
                raise ValueError(f"Invalid boolean value for '{key}': {value}")
        else:
            config_dict[key] = convert_to_appropriate_type(value)

    # Ensure 'allow_byte_to_be_split_between_frames' has a default value
    if 'allow_byte_to_be_split_between_frames' not in config_dict:
        config_dict['allow_byte_to_be_split_between_frames'] = False

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

    # Validation Rule 1:
    if 'pick_frame_to_read' in config_dict and 'total_frames_repetition' in config_dict:
        pick = config_dict['pick_frame_to_read']
        total_frames_repetition = config_dict['total_frames_repetition']
        if len(pick) != len(total_frames_repetition):
            raise ValueError("Length of 'pick_frame_to_read' must match 'total_frames_repetition'.")

        for idx, (p, r) in enumerate(zip(pick, total_frames_repetition)):
            if p > r:
                raise ValueError(f"'pick_frame_to_read' at index {idx} ({p}) "
                                 f"cannot be greater than 'total_frames_repetition' ({r}).")

    # Validation Rule 2:
    if 'data_box_size_step' in config_dict:
        steps = config_dict['data_box_size_step']
        for idx, step in enumerate(steps):
            if not (1 <= step <= 50):
                raise ValueError(f"'data_box_size_step' at index {idx} ({step}) "
                                 f"must be between 1 and 50 (inclusive).")

    config_dict['usable_width'] = []
    config_dict['usable_height'] = []
    config_dict['usable_bits_in_frame'] = []
    config_dict['available_width'] = config_dict['end_width'] - config_dict['start_width']
    config_dict['available_height'] = config_dict['end_height'] - config_dict['start_height']

    for box_size in config_dict['data_box_size_step']:
        usable_width = (config_dict['available_width'] // box_size) * box_size
        usable_height = (config_dict['available_height'] // box_size) * box_size
        config_dict['usable_width'].append(usable_width)
        config_dict['usable_height'].append(usable_height)
        usable_bits_in_frame = (usable_width // box_size) * (usable_height // box_size)
        usable_bits_in_frame = usable_bits_in_frame if config_dict['allow_byte_to_be_split_between_frames'] else ((usable_bits_in_frame // 8) * 8)
        config_dict['usable_bits_in_frame'].append(usable_bits_in_frame)
    return config_dict
