# lib/config_loader.py
import configparser
import math
import os
import json
import re
import numpy as np
from .detect_base_from_json import detect_base_from_json


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
        elif key.startswith('ram_threshold_'):
            config_dict[key] = eval(value, {}, {})
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
    config_dict['usable_databoxes_in_frame'] = []
    config_dict['available_width'] = config_dict['end_width'] - config_dict['start_width']
    config_dict['available_height'] = config_dict['end_height'] - config_dict['start_height']

    for box_size in config_dict['data_box_size_step']:
        usable_width = (config_dict['available_width'] // box_size) * box_size
        usable_height = (config_dict['available_height'] // box_size) * box_size
        config_dict['usable_width'].append(usable_width)
        config_dict['usable_height'].append(usable_height)
        usable_databoxes_in_frame = (usable_width // box_size) * (usable_height // box_size)
        usable_databoxes_in_frame = usable_databoxes_in_frame if config_dict['allow_byte_to_be_split_between_frames'] else (
            (usable_databoxes_in_frame // 8) * 8)
        config_dict['usable_databoxes_in_frame'].append(usable_databoxes_in_frame)
    #
    #
    """
    Converts encoding_color_map from HEX to BGR NumPy arrays for Numba compatibility.
    Stores the result in a dictionary for easy use.
    """
    if 'encoding_map_path' in config_dict:
        with open(config_dict['encoding_map_path'], 'r') as file:
            config_dict['encoding_color_map'] = json.load(file)

        for char, color_code in config_dict['encoding_color_map'].items():
            if not isinstance(char, str) or len(char) != 1:
                raise ValueError(f"Invalid character: {char} found in encoding map.")
            if not isinstance(color_code, str) or not color_code.startswith("#") or len(color_code) != 7 or not re.fullmatch(
                    r"#[0-9A-Fa-f]{6}", color_code):
                raise ValueError(f"Invalid color code: {color_code} in encoding map.")

        config_dict["encoding_base"], config_dict["encoding_format_string"], config_dict["encoding_chunk_size"], config_dict[
            "encoding_function"], config_dict["decoding_function"] = detect_base_from_json(config_dict['encoding_color_map'])
        config_dict["encoding_bits_per_value"] = math.log2(config_dict["encoding_base"])

        color_bounds = {}
        color_rgb = {}

        # Read "color_threshold_percent" from config.ini (like 5 => 0.05)
        color_threshold = math.ceil(config_dict.get("color_threshold_percent") / 100.0 * 255)

        for key, hex_color in config_dict['encoding_color_map'].items():
            # Convert HEX (#RRGGBB) to BGR
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)

            color_rgb[key] = (r, g, b)

            # Compute the range using threshold
            r_range = (max(0, r - color_threshold), min(255, r + color_threshold))
            g_range = (max(0, g - color_threshold), min(255, g + color_threshold))
            b_range = (max(0, b - color_threshold), min(255, b + color_threshold))

            color_bounds[key] = (r_range, g_range, b_range)

        color_keys = list(color_bounds.keys())
        for i in range(len(color_keys)):
            for j in range(i + 1, len(color_keys)):
                key1, key2 = color_keys[i], color_keys[j]
                (r1_low, r1_high), (g1_low, g1_high), (b1_low, b1_high) = color_bounds[key1]
                (r2_low, r2_high), (g2_low, g2_high), (b2_low, b2_high) = color_bounds[key2]

                # Check if ranges have potential overlapping values
                r_overlap = (r1_low <= r2_high) and (r2_low <= r1_high)
                g_overlap = (g1_low <= g2_high) and (g2_low <= g1_high)
                b_overlap = (b1_low <= b2_high) and (b2_low <= b1_high)

                # If there's a valid color that fits in both ranges but not in all three channels
                if (r_overlap and g_overlap and b_overlap):
                    raise ValueError(f"Conflict detected between colors {key1} and {key2}")

        encoding_color_map_keys = np.array(list(color_bounds.keys()))
        encoding_color_map_keys = np.array([ord(k) for k in encoding_color_map_keys], dtype=np.uint8)
        encoding_color_map_values = np.array(list(color_rgb.values()))  # , dtype=np.uint8)
        encoding_color_map_values_lower_bounds = np.array([[c[0][0], c[1][0], c[2][0]] for c in color_bounds.values()], dtype=np.uint8)
        encoding_color_map_values_upper_bounds = np.array([[c[0][1], c[1][1], c[2][1]] for c in color_bounds.values()], dtype=np.uint8)

        # Put them back in config_dict
        config_dict["encoding_color_map_keys"] = encoding_color_map_keys
        config_dict["encoding_color_map_values"] = encoding_color_map_values
        config_dict["encoding_color_map_values_lower_bounds"] = encoding_color_map_values_lower_bounds
        config_dict["encoding_color_map_values_upper_bounds"] = encoding_color_map_values_upper_bounds

    return config_dict
