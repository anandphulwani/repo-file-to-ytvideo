import math
import sys
import numpy as np
import numba
from .content_type import ContentType
from .determine_color_key import determine_color_key
from .config_loader import load_config

# The thresholds for black/white quick detection (like your old code).
BLACK_THRESHOLD = 50
WHITE_THRESHOLD = 200


####################################################
# 2) NUMBA-ACCELERATED BIT EXTRACTION
####################################################
@numba.njit
def extract_bits_numba(start_height, start_width, box_step, usable_w, usable_h, bits_per_frame, frame: np.ndarray, frame_index: int,
                       total_baseN_length: int, data_index_start: int, is_last_frame: bool):
    """
    Extract bits from `frame` (BGR, shape=(H,W,3)) according to 
    your black/white fallback logic, scanning from (start_width, start_height)
    to (start_width+usable_w, start_height+usable_h) in steps of box_step.

    - bits_per_frame = maximum bits per frame to extract
    - If is_last_frame==True, we stop after total_baseN_length bits
      (so we don't over-extract).
    """
    output_bytes = []
    bit_buffer = np.empty(8, dtype=np.uint8)  # hold up to 8 bits before we flush to a byte
    buffer_fill = 0

    bits_used = 0
    data_index = data_index_start

    # We'll read BGR from frame[y, x] => (b, g, r).
    for y in range(start_height, start_height + usable_h, box_step):
        for x in range(start_width, start_width + usable_w, box_step):
            if bits_used >= bits_per_frame:
                break
            if is_last_frame and data_index >= total_baseN_length:
                break

            b = frame[y, x, 0]
            g = frame[y, x, 1]
            r = frame[y, x, 2]

            # Quick black/white detection:
            if b <= BLACK_THRESHOLD and g <= BLACK_THRESHOLD and r <= BLACK_THRESHOLD:
                bit_val = 0
            elif b >= WHITE_THRESHOLD and g >= WHITE_THRESHOLD and r >= WHITE_THRESHOLD:
                bit_val = 1
            else:
                # Fallback logic if you want more advanced average color,
                # or looking at neighboring pixels, etc.
                # For demonstration, we do a naive approach: treat anything else as 0
                # or replicate your `determine_color_key(...)`.
                bit_val = 0

            bit_buffer[buffer_fill] = bit_val
            buffer_fill += 1

            if buffer_fill == 8:
                # Convert the 8 bits to one byte
                byte_val = 0
                for i in range(8):
                    byte_val = (byte_val << 1) | bit_buffer[i]
                output_bytes.append(byte_val)
                buffer_fill = 0

            if is_last_frame:
                data_index += 1
            bits_used += 1

        if bits_used >= bits_per_frame:
            break
        if is_last_frame and data_index >= total_baseN_length:
            break

    # If not fully empty, that means the frame ended with partial bits
    if buffer_fill != 0:
        raise ValueError("bit_buffer not empty at end of frame. (Numba)")

    return output_bytes


def process_frame_optimized(args):
    """
    Multiprocessing worker function that 
    1) runs Numba-based extraction, 
    2) returns (frame_index, list_of_1-byte chunks).
    """
    # (frame_index, frame_bgr, total_baseN_length, data_index_start, is_last_frame) = args
    # config, frame, encoding_color_map, frame_index, frame_step, total_baseN_length, num_frames, metadata_frames = args
    config_params, frame_bgr, encoding_color_map, frame_index, frame_step, total_baseN_length, num_frames, metadata_frames = args

    start_height = config_params["start_height"]
    start_width = config_params["start_width"]
    box_step = config_params["box_step"]
    usable_w = config_params["usable_w"]
    usable_h = config_params["usable_h"]
    bits_per_frame = config_params["bits_per_frame"]

    frames_so_far = (frame_index - metadata_frames) // frame_step
    data_index_start = frames_so_far * bits_per_frame
    is_last_frame = (frame_index >= (num_frames - frame_step + 1))

    # Ensure dtype=uint8
    if frame_bgr.dtype != np.uint8:
        frame_bgr = frame_bgr.astype(np.uint8)

    out_ints = extract_bits_numba(start_height,
                                  start_width,
                                  box_step,
                                  usable_w,
                                  usable_h,
                                  bits_per_frame,
                                  frame=frame_bgr,
                                  frame_index=frame_index,
                                  total_baseN_length=total_baseN_length,
                                  data_index_start=data_index_start,
                                  is_last_frame=is_last_frame)
    # Convert each int to a single-byte object for writing
    output_data = [val.to_bytes(1, byteorder='big') for val in out_ints]
    return (frame_index, output_data)
