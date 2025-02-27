import gc
import sys
import cv2
import datetime
import numpy as np
from os import path


def encode_frame(args):
    frame, config, encoding_color_map, frame_data, frame_index, content_type, debug = args
    data_box_size_step = config['data_box_size_step'][content_type.value]
    usable_width = config['usable_width'][content_type.value]
    usable_height = config['usable_height'][content_type.value]

    if frame_data is None:
        print(f'frame_index: {frame_index}, frame_data: `{frame_data}` does not have any data.')
        sys.exit(1)

    # Set the inner area (excluding margins) to white
    margin = config['margin']
    frame[margin:config['frame_height'] - margin, margin:config['frame_width'] - margin] = (255, 255, 255)

    # Define the region of interest (ROI) where blocks will be drawn
    start_y = config['start_height']
    start_x = config['start_width']
    y_end = start_y + usable_height
    x_end = start_x + usable_width
    roi = frame[start_y:y_end, start_x:x_end]
    roi_height, roi_width, _ = roi.shape

    # Determine how many full blocks fit into the ROI
    n_y = roi_height // data_box_size_step
    n_x = roi_width // data_box_size_step
    total_blocks = n_y * n_x

    # Use only as many blocks as there is data in frame_data
    num_blocks_to_fill = min(total_blocks, len(frame_data))

    # Precompute the colors from frame_data for the blocks to fill.
    colors_arr = np.zeros((num_blocks_to_fill, 3), dtype=np.uint8)

    for i, c in enumerate(frame_data[:num_blocks_to_fill]):
        if c in encoding_color_map:
            hex_str = encoding_color_map[c]
            r = int(hex_str[1:3], 16)
            g = int(hex_str[3:5], 16)
            b = int(hex_str[5:7], 16)
            colors_arr[i] = (b, g, r)
        else:
            raise ValueError(f"Unknown character: {c} found in encoded data stream")

    # Explicitly set the colors in the ROI
    data_idx = 0
    for y in range(0, n_y * data_box_size_step, data_box_size_step):
        for x in range(0, n_x * data_box_size_step, data_box_size_step):
            if data_idx >= num_blocks_to_fill:
                break
            roi[y:y + data_box_size_step, x:x + data_box_size_step] = colors_arr[data_idx]
            data_idx += 1
        if data_idx >= num_blocks_to_fill:
            break

    cv2.imwrite(path.join("storage", "output", f"frame_{content_type}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"),
                frame) if debug else None
    return (frame_index, frame, content_type)
