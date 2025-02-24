import base64
import sys
import cv2
import zfec
from reedsolo import RSCodec
from .content_type import ContentType
from .PreMetadata import PreMetadata
from .Metadata import Metadata
from .rot13_rot5 import rot13_rot5
from .determine_color_key import determine_color_key
from .detect_base_from_json import get_length_in_base


def read_frames_and_get_data_in_format(cap,
                                       config,
                                       content_type,
                                       encoding_color_map,
                                       start_frame_index,
                                       num_frames,
                                       data_expected_length=None,
                                       convert_to=None):
    frame_data_str, total_frames_consumed = read_frames(cap, config, content_type, encoding_color_map, start_frame_index, num_frames,
                                                        data_expected_length)
    base = config["encoding_base"]

    if convert_to is None:
        return frame_data_str, total_frames_consumed

    int_value = int(frame_data_str, base)
    byte_data = int_value.to_bytes((int_value.bit_length() + 7) // 8, byteorder='big')
    if convert_to == "string":
        return byte_data.decode('utf-8', errors='ignore'), total_frames_consumed
    elif convert_to == "bytearray":
        return byte_data, total_frames_consumed


def process_frame(frame, config, content_type, encoding_color_map, data_expected_length, data_current_length, output_data, baseN_data_buffer):
    """Processes a frame and extracts encoded data according to the encoding map's base."""

    base = config["encoding_base"]
    encoding_keys = list(encoding_color_map.keys())  # Retrieve keys (like '0', '1', 'A', etc.)

    main_delim = config['premetadata_metadata_main_delimiter']
    usable_width = config['usable_width'][content_type.value]
    usable_height = config['usable_height'][content_type.value]

    # Begin processing at the starting y-coordinate
    y = config['start_height']

    # Get base-specific parameters from detect_base_from_json
    chunk_size = config["encoding_chunk_size"]
    decode_func = config["decoding_function"]

    while y < config['start_height'] + usable_height:
        for x in range(config['start_width'], config['start_width'] + usable_width, config['data_box_size_step'][content_type.value]):
            # Look for the delimiter to determine the length
            if data_expected_length is None:
                if len(output_data) > len(main_delim) and output_data.endswith(main_delim):
                    output_data = output_data.replace(main_delim, "")
                    data_expected_length = get_length_in_base(int(output_data), config["encoding_bits_per_value"])
                    output_data = ''

            # Find the nearest encoding key from the frame
            nearest_color_key = determine_color_key(frame, x, y, config['data_box_size_step'][content_type.value], config["encoding_color_map_keys"],
                                                    config["encoding_color_map_values"], config["encoding_color_map_values_lower_bounds"],
                                                    config["encoding_color_map_values_upper_bounds"])

            # Store detected value in baseN data buffer
            if str(chr(nearest_color_key)) in encoding_keys:
                baseN_data_buffer += str(chr(nearest_color_key))

            if data_expected_length is not None:
                data_current_length += 1

            # Process buffer when it reaches required chunk size
            if len(baseN_data_buffer) >= chunk_size:
                try:
                    if data_expected_length is None:
                        output_data += decode_func(baseN_data_buffer[:chunk_size]).decode('utf-8')  # Decode only chunk_size length
                    else:
                        output_data += baseN_data_buffer[:chunk_size]
                except Exception as e:
                    print(f"Error decoding: {baseN_data_buffer[:chunk_size]} | {e}")
                baseN_data_buffer = baseN_data_buffer[chunk_size:]  # Remove processed bits

            # Check if we've received enough data based on data_expected_length
            if data_expected_length and data_current_length >= data_expected_length:
                # Break out of the inner loops once metadata is fully read
                break
        else:
            # This else clause executes if the inner for-loop wasn’t broken:
            y += config['data_box_size_step'][content_type.value]
            continue  # Continue the while-loop with the updated y
        break  # Break out of the while-loop if the for-loop was broken

    return data_expected_length, data_current_length, output_data, baseN_data_buffer


def read_frames(cap, config, content_type, encoding_color_map, start_frame_index, num_frames, data_expected_length=None):
    """Reads frames and extracts encoded data as per the encoding map's base."""

    baseN_data_buffer = ''
    output_data = ''
    data_current_length = 0

    frame_step = config['total_frames_repetition'][content_type.value]

    # Iterate over frames, starting at the designated frame index.
    for frame_index in range(start_frame_index + config['pick_frame_to_read'][content_type.value] - 1, num_frames, frame_step):
        # Set the video position to the desired frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        # Read the frame
        _, frame = cap.read()
        (data_expected_length, data_current_length, output_data, baseN_data_buffer) = process_frame(frame, config, content_type, encoding_color_map,
                                                                                                    data_expected_length, data_current_length,
                                                                                                    output_data, baseN_data_buffer)

        total_frames_consumed = frame_index - config['pick_frame_to_read'][content_type.value] + frame_step - start_frame_index
        # Break out of the loop once the full metadata has been read.
        if data_expected_length and data_current_length >= data_expected_length:
            break

    return output_data, total_frames_consumed


def check_metadata_valid_using_checksum(metadata_str):
    # Extract checksum
    checksum_prefix = '|CHECKSUM:'
    checksum_start = metadata_str.find(checksum_prefix)
    if checksum_start == -1:
        print("Checksum not found in metadata.")
        return False, "Checksum not found in metadata."

    checksum_end = metadata_str.find('|', checksum_start + len(checksum_prefix))
    if checksum_end == -1:
        print("Invalid checksum format.")
        return False, "Invalid checksum format."

    checksum_value_str = metadata_str[checksum_start + len(checksum_prefix):checksum_end]
    try:
        checksum_value = int(checksum_value_str)
    except ValueError:
        print("Invalid checksum value.")
        return False, "Invalid checksum value."

    # Extract the actual metadata without checksum
    actual_metadata = metadata_str[:checksum_start]

    # Verify checksum
    calculated_checksum = sum(ord(c) for c in actual_metadata) % 256
    if calculated_checksum != checksum_value:
        print("Checksum verification failed.")
        return False, "Checksum verification failed."

    return True, actual_metadata


def read_metadata(cap, config, encoding_color_map, pm_obj, num_frames):
    # 1st pass
    """
    MODE: Normal metadata
    """
    frames_consumed = pm_obj.premetadata_frame_count
    metadata_normal, metadata_normal_frames_consumed = read_frames_and_get_data_in_format(cap, config, ContentType.METADATA, encoding_color_map,
                                                                                          frames_consumed, num_frames,
                                                                                          get_length_in_base(pm_obj.sections["normal"]["data_size"], config["encoding_bits_per_value"]), "string")
    metadata_normal = metadata_normal.encode()
    triplet_length = len(metadata_normal) // 3

    # Extract the three copies.
    metadata_normal_copy1 = metadata_normal[:triplet_length]
    metadata_normal_copy2 = metadata_normal[triplet_length:2 * triplet_length]
    metadata_normal_copy3 = metadata_normal[2 * triplet_length:3 * triplet_length]

    # Create a bytearray to hold the majority vote result.
    majority_data = bytearray(triplet_length)

    # For each byte position, compute the majority using the bitwise formula:
    # majority_byte = (byte1 & byte2) | (byte1 & byte3) | (byte2 & byte3)
    for i in range(triplet_length):
        majority_data[i] = (metadata_normal_copy1[i] & metadata_normal_copy2[i]) | (metadata_normal_copy1[i] & metadata_normal_copy3[i]) | (
            metadata_normal_copy2[i] & metadata_normal_copy3[i])

    # The final metadata with checksum (majority-corrected) is:
    metadata_with_checksum = bytes(majority_data).decode()

    is_metadata_valid, metadata_or_errormesg = check_metadata_valid_using_checksum(metadata_with_checksum)

    if is_metadata_valid:
        return metadata_or_errormesg

    # 2nd Pass
    """
    MODE: Base64 metadata
    """
    frames_consumed += metadata_normal_frames_consumed
    metadata_base64, metadata_base64_frames_consumed = read_frames_and_get_data_in_format(cap, config, ContentType.METADATA, encoding_color_map,
                                                                                          frames_consumed, num_frames,
                                                                                          get_length_in_base(pm_obj.sections["base64"]["data_size"], config["encoding_bits_per_value"]), "string")
    metadata_base64 = base64.b64decode(metadata_base64).decode()

    is_metadata_valid, metadata_or_errormesg = check_metadata_valid_using_checksum(metadata_base64)

    if is_metadata_valid:
        return metadata_or_errormesg

    # 3rd Pass
    """
    MODE: Rot13 metadata
    """
    frames_consumed += metadata_base64_frames_consumed
    metadata_rot13, metadata_rot13_frames_consumed = read_frames_and_get_data_in_format(cap, config, ContentType.METADATA, encoding_color_map,
                                                                                        frames_consumed, num_frames,
                                                                                        get_length_in_base(pm_obj.sections["rot13"]["data_size"], config["encoding_bits_per_value"]), "string")
    metadata_rot13 = rot13_rot5(metadata_rot13)

    is_metadata_valid, metadata_or_errormesg = check_metadata_valid_using_checksum(metadata_rot13)

    if is_metadata_valid:
        return metadata_or_errormesg

    # 4th Pass
    """
    MODE: Reed-Solomon metadata
    """
    frames_consumed += metadata_rot13_frames_consumed
    metadata_reed_solomon, metadata_reed_solomon_frames_consumed = read_frames_and_get_data_in_format(cap, config, ContentType.METADATA,
                                                                                                      encoding_color_map, frames_consumed, num_frames,
                                                                                                      get_length_in_base(pm_obj.sections["reed_solomon"]["data_size"], config["encoding_bits_per_value"]),
                                                                                                      "bytearray")
    # Decode using Reed-Solomon
    metadata_reed_solomon = RSCodec(int(pm_obj.sections["reed_solomon"]["rscodec_value"])).decode(metadata_reed_solomon)
    metadata_reed_solomon = metadata_reed_solomon[0] if isinstance(metadata_reed_solomon, tuple) else metadata_reed_solomon
    metadata_reed_solomon = metadata_reed_solomon.decode('utf-8', errors='ignore')

    is_metadata_valid, metadata_or_errormesg = check_metadata_valid_using_checksum(metadata_reed_solomon)

    if is_metadata_valid:
        return metadata_or_errormesg

    # 5th Pass
    """
    MODE: Zfec metadata
    """
    frames_consumed += metadata_reed_solomon_frames_consumed
    metadata_zfec, metadata_zfec_frames_consumed = read_frames_and_get_data_in_format(cap, config, ContentType.METADATA, encoding_color_map,
                                                                                      frames_consumed, num_frames,
                                                                                      get_length_in_base(pm_obj.sections["zfec"]["data_size"], config["encoding_bits_per_value"]), "string")
    # Decode using Zfec
    zfec_k, zfec_m = 3, 5  # Same values used for encoding
    zfec_decoder = zfec.Decoder(zfec_k, zfec_m)
    metadata_zfec = bytes.fromhex(metadata_zfec)
    fragment_size = len(metadata_zfec) // zfec_m
    metadata_zfec_fragments = [metadata_zfec[i * fragment_size:(i + 1) * fragment_size] for i in range(zfec_m)]
    metadata_zfec = zfec_decoder.decode(metadata_zfec_fragments[:zfec_k], range(zfec_k))
    metadata_zfec = b"".join(metadata_zfec).rstrip(b' ').decode()
    is_metadata_valid, metadata_or_errormesg = check_metadata_valid_using_checksum(metadata_zfec)

    if is_metadata_valid:
        return metadata_or_errormesg
    else:
        raise ValueError("Invalid metadata found in all metadata types.")


def get_file_metadata(config, cap, encoding_color_map, num_frames, debug):
    # PREMETADATA
    pre_metadata, pre_metadata_frame_count = read_frames_and_get_data_in_format(cap, config, ContentType.PREMETADATA, encoding_color_map, 0,
                                                                                num_frames, None, "string")
    pm_obj = PreMetadata()
    pm_obj.parse(pre_metadata, pre_metadata_frame_count)
    print("# ------------------------------------------") if debug else None
    print("# ------------------------------------------") if debug else None
    print("# ------------PRE METADATA------------------") if debug else None
    print("# ------------------------------------------") if debug else None
    print(pm_obj) if debug else None
    print("# ------------------------------------------") if debug else None

    # METADATA
    metadata = read_metadata(cap, config, encoding_color_map, pm_obj, num_frames)
    m_obj = Metadata()
    m_obj.parse(metadata)
    print("# ------------------------------------------") if debug else None
    print("# ------------------------------------------") if debug else None
    print("# ---------------METADATA-------------------") if debug else None
    print("# ------------------------------------------") if debug else None
    print(m_obj) if debug else None
    print("# ------------------------------------------") if debug else None

    return pm_obj.premetadata_and_metadata_frame_count, m_obj
