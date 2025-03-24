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
from .process_frame_optimized import process_frame_optimized


def read_frames(cap,
                config_params,
                content_type,
                start_frame_index,
                num_frames,
                total_baseN_length=None,
                convert_return_output_data=None,
                debug=False):
    """Reads frames and extracts encoded data as per the encoding map's base."""

    baseN_data_buffer = ''
    output_data = ''
    data_current_length = 0

    frame_step = config_params['total_frames_repetition']
    print("read_frames: Init: Reading frame_index: ", (start_frame_index + config_params['pick_frame_to_read'] - 1)) if debug else None

    # Iterate over frames, starting at the designated frame index.
    for frame_index in range(start_frame_index + config_params['pick_frame_to_read'] - 1, num_frames, frame_step):
        print(
            f"read_frames: Loop: Reading frame {frame_index}, frame_step: {frame_step}, start_frame_index: {start_frame_index}, content_type: {content_type}"
        ) if debug else None
        # Set the video position to the desired frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        # Read the frame
        _, frame_to_decode = cap.read()
        args = (config_params, content_type, frame_to_decode, frame_index, frame_step, total_baseN_length, num_frames, 0, convert_return_output_data)
        (_, output_data, total_baseN_length, data_current_length) = process_frame_optimized(args)

        total_frames_consumed = frame_index + 1 - config_params['pick_frame_to_read'] + frame_step - start_frame_index
        # Break out of the loop once the full metadata has been read.
        if total_baseN_length and data_current_length >= total_baseN_length:
            break

    print(f"read_frames: Total frames consumed: {total_frames_consumed}") if debug else None
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


def read_metadata(cap, config_params_metadata, pm_obj, num_frames, debug=False):
    # 1st pass
    """
    MODE: Normal metadata
    """
    frames_consumed = pm_obj.premetadata_frame_count
    print(f"read_metadata: Init: Frames consumed before metadata: {frames_consumed}") if debug else None

    metadata_normal, metadata_normal_frames_consumed = read_frames(cap, config_params_metadata, ContentType.METADATA, frames_consumed, num_frames,
                                                                   pm_obj.sections["normal"]["data_size"], "string", debug)

    metadata_normal = metadata_normal.encode()
    triplet_length = len(metadata_normal) // 3

    print("read_metadata: Read metadata_normal: ", metadata_normal) if debug else None

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
    metadata_base64, metadata_base64_frames_consumed = read_frames(cap, config_params_metadata, ContentType.METADATA, frames_consumed, num_frames,
                                                                   pm_obj.sections["base64"]["data_size"], "string", debug)
    metadata_base64 = base64.b64decode(metadata_base64).decode()

    is_metadata_valid, metadata_or_errormesg = check_metadata_valid_using_checksum(metadata_base64)

    if is_metadata_valid:
        return metadata_or_errormesg

    # 3rd Pass
    """
    MODE: Rot13 metadata
    """
    frames_consumed += metadata_base64_frames_consumed
    metadata_rot13, metadata_rot13_frames_consumed = read_frames(cap, config_params_metadata, ContentType.METADATA, frames_consumed, num_frames,
                                                                 pm_obj.sections["rot13"]["data_size"], "string", debug)
    metadata_rot13 = rot13_rot5(metadata_rot13)

    is_metadata_valid, metadata_or_errormesg = check_metadata_valid_using_checksum(metadata_rot13)

    if is_metadata_valid:
        return metadata_or_errormesg

    # 4th Pass
    """
    MODE: Reed-Solomon metadata
    """
    frames_consumed += metadata_rot13_frames_consumed
    metadata_reed_solomon, metadata_reed_solomon_frames_consumed = read_frames(cap, config_params_metadata, ContentType.METADATA, frames_consumed,
                                                                               num_frames, pm_obj.sections["reed_solomon"]["data_size"], "bytearray",
                                                                               debug)

    # Decode using Reed-Solomon
    metadata_reed_solomon = base64.b64decode(metadata_reed_solomon)
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
    metadata_zfec, metadata_zfec_frames_consumed = read_frames(cap, config_params_metadata, ContentType.METADATA, frames_consumed, num_frames,
                                                               pm_obj.sections["zfec"]["data_size"], "string", debug)

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


def get_file_metadata(cap, config_params_premetadata, config_params_metadata, num_frames, debug):
    # PREMETADATA
    pre_metadata, pre_metadata_frame_count = read_frames(cap, config_params_premetadata, ContentType.PREMETADATA, 0, num_frames, None, "string",
                                                         debug)
    chars_to_strip_from_pre_metadata = (len(config_params_premetadata['premetadata_metadata_main_delimiter']) *
                                        2) + config_params_premetadata['length_of_digits_to_represent_size']
    pre_metadata = pre_metadata[chars_to_strip_from_pre_metadata:]

    pm_obj = PreMetadata()
    pm_obj.parse(pre_metadata, pre_metadata_frame_count)
    print("# ------------------------------------------") if debug else None
    print("# ------------------------------------------") if debug else None
    print("# ------------PRE METADATA------------------") if debug else None
    print("# ------------------------------------------") if debug else None
    print(pm_obj) if debug else None
    print("# ------------------------------------------") if debug else None

    # METADATA
    metadata = read_metadata(cap, config_params_metadata, pm_obj, num_frames, debug)
    m_obj = Metadata()
    m_obj.parse(metadata)
    print("# ------------------------------------------") if debug else None
    print("# ------------------------------------------") if debug else None
    print("# ---------------METADATA-------------------") if debug else None
    print("# ------------------------------------------") if debug else None
    print(m_obj) if debug else None
    print("# ------------------------------------------") if debug else None

    return pm_obj.premetadata_and_metadata_frame_count, m_obj
