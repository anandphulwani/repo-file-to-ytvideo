import base64
import sys
import zfec
from reedsolo import RSCodec
from .content_type import ContentType
from .PreMetadata import PreMetadata
from .Metadata import Metadata
from .rot13_rot5 import rot13_rot5
from .determine_color_key import determine_color_key


def read_frames_and_get_data_in_format(vid,
                                       config,
                                       content_type,
                                       encoding_color_map,
                                       start_frame_index,
                                       num_frames,
                                       data_expected_length=None,
                                       convert_to=None):
    frame_data_binary, total_frames_consumed = read_frames(vid, config, content_type, encoding_color_map, start_frame_index, num_frames,
                                                           data_expected_length)

    if convert_to is None:
        return frame_data_binary, total_frames_consumed

    int_value = int(frame_data_binary, 2)
    byte_data = int_value.to_bytes((len(frame_data_binary) + 7) // 8, byteorder='big')
    if convert_to == "string":
        return byte_data.decode('utf-8', errors='ignore'), total_frames_consumed
    elif convert_to == "bytearray":
        return byte_data, total_frames_consumed


def process_frame(frame, config, content_type, encoding_color_map, data_expected_length, data_current_length, output_data, baseN_data_buffer):
    main_delim = config['premetadata_metadata_main_delimiter']
    usable_width = config['usable_width'][content_type.value]
    usable_height = config['usable_height'][content_type.value]

    # Begin processing at the starting y-coordinate
    y = config['start_height']

    while y < config['start_height'] + usable_height:
        for x in range(config['start_width'], config['start_width'] + usable_width, config['data_box_size_step'][content_type.value]):
            # Look for the delimiter to determine the length
            if data_expected_length is None:
                if len(output_data) > len(main_delim) and output_data.endswith(main_delim):
                    output_data = output_data.replace(main_delim, "")
                    data_expected_length = int(output_data)
                    output_data = ''

            nearest_color_key = determine_color_key(frame, x, y, encoding_color_map)
            baseN_data_buffer += nearest_color_key

            if data_expected_length is not None:
                data_current_length += 1

            if len(baseN_data_buffer) == 8:
                if data_expected_length is None:
                    decoded_char = int(baseN_data_buffer, 2).to_bytes(1, byteorder='big')
                    # Decode and ignore errors if any
                    output_data += decoded_char.decode('utf-8', errors='ignore')
                else:
                    output_data += baseN_data_buffer
                baseN_data_buffer = ''

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


def read_frames(vid, config, content_type, encoding_color_map, start_frame_index, num_frames, data_expected_length=None):
    baseN_data_buffer = ''
    output_data = ''
    data_current_length = 0

    frame_step = config['total_frames_repetition'][content_type.value]

    # Iterate over frames, starting at the designated frame index.
    for frame_index in range(start_frame_index + config['pick_frame_to_read'][content_type.value], num_frames, frame_step):
        frame = vid.get_data(frame_index)
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


def read_metadata(vid, config, encoding_color_map, pm_obj, num_frames):
    # 1st pass
    """
    MODE: Normal metadata
    """
    frames_consumed = pm_obj.premetadata_frame_count
    metadata_normal, metadata_normal_frames_consumed = read_frames_and_get_data_in_format(vid, config, ContentType.METADATA, encoding_color_map,
                                                                                          frames_consumed, num_frames,
                                                                                          pm_obj.sections["normal"]["data_size"], "string")
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
    metadata_base64, metadata_base64_frames_consumed = read_frames_and_get_data_in_format(vid, config, ContentType.METADATA, encoding_color_map,
                                                                                          frames_consumed, num_frames,
                                                                                          pm_obj.sections["base64"]["data_size"], "string")
    metadata_base64 = base64.b64decode(metadata_base64).decode()

    is_metadata_valid, metadata_or_errormesg = check_metadata_valid_using_checksum(metadata_base64)

    if is_metadata_valid:
        return metadata_or_errormesg

    # 3rd Pass
    """
    MODE: Rot13 metadata
    """
    frames_consumed += metadata_base64_frames_consumed
    metadata_rot13, metadata_rot13_frames_consumed = read_frames_and_get_data_in_format(vid, config, ContentType.METADATA, encoding_color_map,
                                                                                        frames_consumed, num_frames,
                                                                                        pm_obj.sections["rot13"]["data_size"], "string")
    metadata_rot13 = rot13_rot5(metadata_rot13)

    is_metadata_valid, metadata_or_errormesg = check_metadata_valid_using_checksum(metadata_rot13)

    if is_metadata_valid:
        return metadata_or_errormesg

    # 4th Pass
    """
    MODE: Reed-Solomon metadata
    """
    frames_consumed += metadata_rot13_frames_consumed
    metadata_reed_solomon, metadata_reed_solomon_frames_consumed = read_frames_and_get_data_in_format(vid, config, ContentType.METADATA,
                                                                                                      encoding_color_map, frames_consumed, num_frames,
                                                                                                      pm_obj.sections["reed_solomon"]["data_size"],
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
    metadata_zfec, metadata_zfec_frames_consumed = read_frames_and_get_data_in_format(vid, config, ContentType.METADATA, encoding_color_map,
                                                                                      frames_consumed, num_frames,
                                                                                      pm_obj.sections["zfec"]["data_size"], "string")
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


def get_file_metadata(config, vid, encoding_color_map, num_frames):
    # PREMETADATA
    pre_metadata, pre_metadata_frame_count = read_frames_and_get_data_in_format(vid, config, ContentType.PREMETADATA, encoding_color_map, 0,
                                                                                num_frames, None, "string")
    pm_obj = PreMetadata()
    pm_obj.parse(pre_metadata, pre_metadata_frame_count)

    # METADATA
    metadata = read_metadata(vid, config, encoding_color_map, pm_obj, num_frames)
    m_obj = Metadata()
    m_obj.parse(metadata)

    return pm_obj.premetadata_and_metadata_frame_count, m_obj
