import sys
import numpy as np
import numba
from .determine_color_key import determine_color_key
from .content_type import ContentType

# Global dictionary to carry over partial chunks across frames
carry_over_chunk = {}


def get_chunks(data, size):
    for i in range(0, len(data), size):
        yield data[i:i + size], i


@numba.njit
def extract_baseN_data_numba(start_height: int, start_width: int, box_step: int, usable_w: int, usable_h: int, databoxes_per_frame: int,
                             frame_to_decode: np.ndarray, encoding_color_map_keys: np.ndarray, encoding_color_map_values: np.ndarray,
                             encoding_color_map_values_lower_bounds: np.ndarray, encoding_color_map_values_upper_bounds: np.ndarray,
                             total_baseN_length: int, data_index: int, is_last_frame: bool):
    """
    Extract baseN data from `frame_to_decode` (BGR, shape=(H,W,3)) according to 
    your black/white fallback logic, scanning from (start_width, start_height)
    to (start_width+usable_w, start_height+usable_h) in steps of box_step.

    - databoxes_per_frame = maximum baseN data per frame to extract
    - If is_last_frame==True, we stop after total_baseN_length baseN data
      (so we don't over-extract).
    """
    baseN_data_buffer = np.empty(databoxes_per_frame, dtype=np.uint8)

    databoxes_used = 0

    # We'll read BGR from frame_to_decode[y, x] => (b, g, r).
    for y in range(start_height, start_height + usable_h, box_step):
        for x in range(start_width, start_width + usable_w, box_step):
            if databoxes_used >= databoxes_per_frame:
                break
            if is_last_frame and total_baseN_length is not None and data_index >= total_baseN_length:
                break

            nearest_key = determine_color_key(frame_to_decode, x, y, box_step, encoding_color_map_keys, encoding_color_map_values,
                                              encoding_color_map_values_lower_bounds, encoding_color_map_values_upper_bounds)

            baseN_data_buffer[databoxes_used] = nearest_key

            if is_last_frame:
                data_index += 1
            databoxes_used += 1

        if databoxes_used >= databoxes_per_frame:
            break
        if is_last_frame and total_baseN_length is not None and data_index >= total_baseN_length:
            break

    # If not fully empty, that means the frame ended with partial baseN data
    # if buffer_fill != 0:
    #     raise ValueError("baseN_data_buffer not empty at end of frame. (Numba)")

    return baseN_data_buffer[:databoxes_used]


def process_frame_optimized(args):
    """
    Optimized frame processing with correct chunk carry-over handling.
    """
    global carry_over_chunk

    config_params, content_type, frame_to_decode, frame_index, frame_step, total_baseN_length, num_frames, frames_traversed, convert_return_output_data = args

    start_height = config_params["start_height"]
    start_width = config_params["start_width"]
    box_step = config_params["box_step"]
    usable_w = config_params["usable_w"]
    usable_h = config_params["usable_h"]
    databoxes_per_frame = config_params["databoxes_per_frame"]
    encoding_chunk_size = config_params["encoding_chunk_size"]
    decoding_function = config_params["decoding_function"]
    encoding_color_map_keys = config_params["encoding_color_map_keys"]
    encoding_color_map_values = config_params["encoding_color_map_values"]
    encoding_color_map_values_lower_bounds = config_params["encoding_color_map_values_lower_bounds"]
    encoding_color_map_values_upper_bounds = config_params["encoding_color_map_values_upper_bounds"]
    premetadata_metadata_main_delimiter = config_params["premetadata_metadata_main_delimiter"]
    premetadata_metadata_sub_delimiter = config_params["premetadata_metadata_sub_delimiter"]
    length_of_digits_to_represent_size = config_params["length_of_digits_to_represent_size"]

    is_last_frame = (frame_index + 1 >= (num_frames - frame_step + 1))
    frames_consumed = ((frame_index - 1 - frames_traversed) // frame_step) if is_last_frame else 0
    data_index = frames_consumed * databoxes_per_frame if is_last_frame else 0

    extracted_baseN_ascii = extract_baseN_data_numba(start_height, start_width, box_step, usable_w, usable_h, databoxes_per_frame, frame_to_decode,
                                                     encoding_color_map_keys, encoding_color_map_values, encoding_color_map_values_lower_bounds,
                                                     encoding_color_map_values_upper_bounds, total_baseN_length, data_index, is_last_frame)

    # Convert all ASCII codes to character values first
    extracted_baseN_values = extracted_baseN_ascii.tobytes().decode('ascii')

    # Use `extracted_baseN_values` instead of `extracted_baseN_ascii`
    output_data = []
    extracted_baseN_values_len = len(extracted_baseN_values)

    # Carry over partial chunk from the previous frame as bytes
    previous_chunk = carry_over_chunk.get(frame_index - 1, "")

    baseN_data_counter = 0

    for chunk_slice, index in get_chunks(extracted_baseN_values, encoding_chunk_size):
        # If last chunk is incomplete, carry it over
        if index + encoding_chunk_size > extracted_baseN_values_len:
            carry_over_chunk[frame_index] = extracted_baseN_values[index:]
            break

        if previous_chunk:
            chunk_slice = previous_chunk + chunk_slice
            previous_chunk = ""

        try:
            # decoding_function expects a string
            decoded_value = decoding_function(chunk_slice)  # Now passing string directly
            output_data.append(decoded_value)

            if content_type in [ContentType.PREMETADATA, ContentType.METADATA] and total_baseN_length is None:
                if len(output_data
                       ) == len(premetadata_metadata_main_delimiter) + length_of_digits_to_represent_size + len(premetadata_metadata_main_delimiter):
                    output_data_string = ''.join(b.decode('utf-8') for b in output_data)
                    if output_data_string.startswith(premetadata_metadata_main_delimiter) and output_data_string.endswith(
                            premetadata_metadata_main_delimiter):
                        parts = output_data_string.split(premetadata_metadata_main_delimiter, 2)
                        if len(parts) == 3:
                            try:
                                total_baseN_length = int(parts[1])
                            except ValueError:
                                pass
                    if total_baseN_length is None:
                        print(f"Error extracting length for content type {content_type} from frame {frame_index}")
                        sys.exit(1)
        except Exception as e:
            print(f"Decoding error: chunk_slice={chunk_slice} | {e}")
            sys.exit(1)

        baseN_data_counter += 1
        if total_baseN_length is not None and baseN_data_counter == total_baseN_length:
            break

    if convert_return_output_data == "string":
        output_data = b"".join(output_data).decode("utf-8")
    elif convert_return_output_data == "bytearray":
        output_data = bytearray(b''.join(output_data))
    return (frame_index, output_data, total_baseN_length, len(output_data))
