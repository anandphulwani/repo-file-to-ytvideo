import sys
import cv2
import datetime
import numpy as np
from os import path


def encode_frame(args):
    config, encoding_color_map, frame_data, frame_index, content_type, debug = args

    margin = config['margin']
    padding = config['padding']
    data_box_size_step = config['data_box_size_step'][content_type.value]
    usable_width = config['usable_width'][content_type.value]
    usable_height = config['usable_height'][content_type.value]

    # Create a white frame (note: we assume margins on both sides)
    frame = np.full((config["frame_height"] - 2 * margin, config["frame_width"] - 2 * margin, 3), 255, dtype=np.uint8)
    if frame_data is None:
        print(f'frame_index: {frame_index}, frame_data: `{frame_data}` does not have any data.')
        sys.exit(1)

    # Define ROI where blocks will be drawn
    start_y, start_x = padding, padding
    y_end, x_end = usable_height + padding, usable_width + padding
    roi = frame[start_y:y_end, start_x:x_end]
    roi_height, roi_width, _ = roi.shape

    # Determine how many full blocks fit into the ROI
    n_y = roi_height // data_box_size_step
    n_x = roi_width // data_box_size_step
    total_blocks = n_y * n_x

    # Use only as many blocks as there is data in frame_data
    num_blocks_to_fill = min(total_blocks, len(frame_data))

    # --- Precompute Color Conversion ---
    # Build a cache for the color conversion
    unique_chars = set(frame_data[:num_blocks_to_fill])
    precomputed = {
        c:
        np.array(
            [
                int(encoding_color_map[c][5:7], 16),  # blue
                int(encoding_color_map[c][3:5], 16),  # green
                int(encoding_color_map[c][1:3], 16)  # red
            ],
            dtype=np.uint8)
        for c in unique_chars if c in encoding_color_map
    }
    # Raise error if any character is unknown
    for c in frame_data[:num_blocks_to_fill]:
        if c not in precomputed:
            raise ValueError(f"Unknown character: {c} found in encoded data stream")
    # Build the colors array using the precomputed mapping
    colors_arr = np.array([precomputed[c] for c in frame_data[:num_blocks_to_fill]], dtype=np.uint8)

    # --- Vectorized Block Assignment ---
    # Create a grid for block colors; default is white
    block_grid = np.full((n_y, n_x, 3), 255, dtype=np.uint8)
    flat_grid = block_grid.reshape(-1, 3)
    # Fill only as many blocks as needed
    flat_grid[:num_blocks_to_fill] = colors_arr

    # Expand the block grid to full ROI size using np.repeat
    colored_roi = np.repeat(np.repeat(block_grid, data_box_size_step, axis=0), data_box_size_step, axis=1)
    # Make sure we do not exceed the ROI dimensions
    roi[:colored_roi.shape[0], :colored_roi.shape[1]] = colored_roi


    cv2.imwrite(path.join("storage", "output", f"frame_{content_type}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"),
                frame) if debug else None
    return (frame_index, frame, content_type)
