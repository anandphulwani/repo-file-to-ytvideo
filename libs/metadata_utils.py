import base64
import os
import zfec
from .rot13_rot5 import rot13_rot5
from reedsolo import RSCodec


def get_metadata(config, file_path, file_size, total_baseN_length, sha1hex):
    """
    Returns the metadata.
    """
    main_delim = config["premetadata_metadata_main_delimiter"]
    sub_delim = config["premetadata_metadata_sub_delimiter"]

    metadata_items = {}
    # ------------------------------------------
    # STEP 1: Build the metadata WITHOUT length
    # ------------------------------------------
    temp_metadata = (f"{main_delim}METADATA"
                     f"{sub_delim}{os.path.basename(file_path)}"
                     f"{sub_delim}{file_size}"
                     f"{sub_delim}{total_baseN_length}"
                     f"{sub_delim}{sha1hex}"
                     f"{main_delim}")

    # ------------------------------------------------
    # STEP 2: Simple checksum (e.g. sum of ASCII % 256)
    # ------------------------------------------------
    checksum_value = sum(ord(c) for c in temp_metadata) % 256
    # Append checksum for clarity
    metadata_with_checksum = f"{temp_metadata}|CHECKSUM:{checksum_value}|"

    # --------------------------------------------
    # STEP 3: Tripling results for redundancy
    # --------------------------------------------
    # Repeat metadata_with_checksum 3 times
    final_metadata = metadata_with_checksum * 3
    metadata_items["normal"] = final_metadata

    # -----------------------------------------
    # STEP 4: Apply Base64 encoding
    # -----------------------------------------
    base64_encoded = base64.b64encode(metadata_with_checksum.encode()).decode()
    metadata_items["base64"] = base64_encoded

    # -----------------------------------------
    # STEP 5: Apply ROT13 cipher
    # -----------------------------------------
    rot13_encoded = rot13_rot5(metadata_with_checksum)
    metadata_items["rot13"] = rot13_encoded

    # -------------------------------------------------
    # STEP 6: Convert to Reed-Solomon error correction
    # -------------------------------------------------
    metadata_rscodec_value = min(len(metadata_with_checksum), 255)
    reed_solomon_encoded = RSCodec(metadata_rscodec_value).encode(metadata_with_checksum.encode())
    reed_solomon_encoded = base64.b64encode(reed_solomon_encoded).decode('utf-8')
    metadata_items["reed_solomon"] = reed_solomon_encoded

    # -----------------------------
    # STEP 7: Apply Erasure Coding
    # -----------------------------
    zfec_k, zfec_m = 3, 5
    zfec_encoder = zfec.Encoder(zfec_k, zfec_m)
    block_size = -(-len(metadata_with_checksum.encode()) // zfec_k)  # Ceiling division
    blocks = [metadata_with_checksum.encode()[i * block_size:(i + 1) * block_size].ljust(block_size, b' ') for i in range(zfec_k)]
    zfec_encoded_text = zfec_encoder.encode(blocks)
    zfec_encoded_hex = "".join(fragment.hex() for fragment in zfec_encoded_text)
    metadata_items["zfec"] = zfec_encoded_hex

    return metadata_items, metadata_rscodec_value


def get_pre_metadata(config, metadata_frames_and_details):
    """
    Returns the pre_metadata.
    """

    pre_metadata = ''
    main_delim = config["premetadata_metadata_main_delimiter"]
    sub_delim = config["premetadata_metadata_sub_delimiter"]
    length_of_digits_to_represent_size = config["length_of_digits_to_represent_size"]

    for key, value in metadata_frames_and_details.items():
        pre_metadata += f"{sub_delim}{key}" + f"{sub_delim}{value[0]}" + (f"{sub_delim}{value[2]}"
                                                                          if key == "reed_solomon" else "") + f"{sub_delim}{value[1]}"

    pre_metadata = main_delim + 'PREMETADATA' + pre_metadata + main_delim
    pre_metadata_len = len(main_delim) + length_of_digits_to_represent_size + len(main_delim) + len(pre_metadata)
    if len(str(pre_metadata_len)) > length_of_digits_to_represent_size:
        raise ValueError(
            f"Pre-metadata length ({len(str(pre_metadata_len))}) exceeds the maximum allowed size ({config['length_of_digits_to_represent_size']})")

    pre_metadata_with_length = main_delim + str(pre_metadata_len).zfill(length_of_digits_to_represent_size) + main_delim + pre_metadata

    return pre_metadata_with_length
