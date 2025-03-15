import json
import sys
import cv2
import datetime
import numpy as np
from os import path
from .config_loader import load_config

config = load_config('config.ini')


def build_bgr_map():
    """
    Convert encoding_color_map's #RRGGBB strings into BGR tuples for direct OpenCV usage.
    """
    with open(config['encoding_map_path'], 'r') as file:
        encoding_color_map = json.load(file)

    bgr_map = {}
    for c, hex_str in encoding_color_map.items():
        b = int(hex_str[5:7], 16)
        g = int(hex_str[3:5], 16)
        r = int(hex_str[1:3], 16)
        bgr_map[c] = (b, g, r)
    return bgr_map


bgr_map = build_bgr_map()


def encode_frame(args):
    frames_batch, config, encoding_color_map, frame_data, frame_index, content_type, debug = args

    # Early-return or raise instead of sys.exit
    if not frame_data:
        print(f'frame_indexes: {frame_index}, frame_data is empty.')
        raise ValueError("No frame data!")

    data_box_size_step = config['data_box_size_step'][content_type.value]
    usable_width = config['usable_width'][content_type.value]
    usable_height = config['usable_height'][content_type.value]
    margin = config['margin']

    # Coordinates for the inner data region
    start_y, start_x = config['start_height'], config['start_width']
    y_end, x_end = start_y + usable_height, start_x + usable_width

    # Frame size
    frame_height = config['frame_height']
    frame_width = config['frame_width']

    # Compute the number of blocks that fit in the data region
    n_y = usable_height // data_box_size_step
    n_x = usable_width // data_box_size_step
    total_blocks = n_y * n_x
    num_blocks_to_fill = min(total_blocks, len(frame_data))

    # ------------------------------------------------------
    # Create the color array for actual data
    # ------------------------------------------------------
    colors_arr = np.array([bgr_map.get(c, (0, 0, 0)) for c in frame_data[:num_blocks_to_fill]], dtype=np.uint8)

    # ------------------------------------------------------
    # Build a 2D block grid of shape (n_y, n_x, 3)
    # ------------------------------------------------------
    block_grid = np.full((n_y, n_x, 3), 255, dtype=np.uint8)
    block_grid = block_grid.reshape(-1, 3)
    block_grid[:num_blocks_to_fill] = colors_arr
    block_grid = block_grid.reshape(n_y, n_x, 3)

    # ------------------------------------------------------
    # Scale up with nearest-neighbor to fill the data region
    # ------------------------------------------------------
    block_roi = cv2.resize(block_grid, (usable_width, usable_height), interpolation=cv2.INTER_NEAREST)

    # ------------------------------------------------------
    # Apply block_roi and paint only the "padding" region in white
    # ------------------------------------------------------
    modified_frames = []

    for frame in frames_batch:
        # 1) Paint the "padding" area in white on all four sides
        frame[margin:start_y, margin:frame_width - margin] = 255
        frame[y_end:frame_height - margin, margin:frame_width - margin] = 255
        frame[margin:frame_height - margin, margin:start_x] = 255
        frame[margin:frame_height - margin, x_end:frame_width - margin] = 255

        # 2) Overwrite the inner data region
        frame[start_y:y_end, start_x:x_end] = block_roi

        cv2.imwrite(path.join("storage", "output", f"frame_{content_type}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"),
                    frame) if debug and not modified_frames else None

        modified_frames.append(frame)

    return modified_frames
