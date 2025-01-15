from tqdm import tqdm
import os
import sys
import math
import hashlib
from .detect_base_from_json import detect_base_from_json


def file_to_encodeddata(config, file_path, debug=False):
    """
    A single-pass generator that reads the file once, computing SHA1 hash
    and total bit-length on the fly, and yields the final metadata bits
    at the end.
    """
    bits_per_frame = config['bits_per_frame']

    sha1 = hashlib.sha1()
    stream_file = open(f"{file_path}_stream.txt", "w") if debug else None

    base, format_string = detect_base_from_json(config)
    print(f"Base is {base}")

    if not os.path.exists(file_path):
        print("The specified file does not exist.")
        sys.exit(1)

    file_size = os.path.getsize(file_path)  # Get the total size of the file
    buffer = ''  # Initialize an empty buffer to store leftover bits
    total_binary_length = 0  # Initialize total binary length counter

    with open(file_path, "rb") as file:
        # Setup tqdm progress bar
        with tqdm(total=file_size, desc="Processing File", unit="B", unit_scale=True) as pbar:
            while True:
                # Determine how many bytes to read:
                needed_bits = bits_per_frame - len(buffer)
                bytes_to_read = math.ceil(needed_bits / 8)
                file_chunk = file.read(bytes_to_read)

                if not file_chunk:
                    if buffer:
                        yield buffer  # Yield any remaining data in the buffer at EOF
                        total_binary_length += len(buffer)
                        stream_file and stream_file.write(buffer)
                    break

                # Update the progress bar with the number of bytes read
                pbar.update(len(file_chunk))
                sha1.update(file_chunk)

                # Convert file bytes to a binary string
                chunk_bits = "".join(f"{byte:{format_string}}" for byte in file_chunk)

                # Add new bits to buffer
                buffer += chunk_bits

                # Yield data in exactly `bits_per_frame` length chunks
                while len(buffer) >= bits_per_frame:
                    data_to_yield = buffer[:bits_per_frame]
                    yield data_to_yield
                    total_binary_length += len(data_to_yield)
                    buffer = buffer[bits_per_frame:]  # Remove the yielded part from buffer
                    stream_file and stream_file.write(data_to_yield)

    stream_file and stream_file.close()

    # ------------------------------------------
    # STEP 1: Build the metadata WITHOUT length
    # ------------------------------------------
    temp_metadata = (f"|::-::|FILE METADATA"
                     f"|:-:|{os.path.basename(file_path)}"
                     f"|:-:|{file_size}"
                     f"|:-:|{total_binary_length}"
                     f"|:-:|{sha1.hexdigest()}"
                     f"|::-::||")

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

    # --------------------------------------------------------
    # STEP 4: Convert final_metadata to binary to get its length
    # --------------------------------------------------------
    final_metadata_binary = "".join(format(ord(char), format_string) for char in final_metadata)
    metadata_length_in_bits = len(final_metadata_binary)

    # --------------------------------------------------------
    # STEP 5: Prepend that length to the metadata
    # --------------------------------------------------------
    metadata_with_length = (f"|::-::|{metadata_length_in_bits}|::-::|"
                            f"{final_metadata}")

    # -------------------------------------------------
    # STEP 6: Convert metadata_with_length to binary & yield
    # -------------------------------------------------
    metadata_with_length_binary = "".join(
        format(ord(char), format_string) for char in metadata_with_length)

    for i in range(0, len(metadata_with_length_binary), bits_per_frame):
        print(f"Metadata chunk starting at bit: {i}")
        yield metadata_with_length_binary[i:i + bits_per_frame]
