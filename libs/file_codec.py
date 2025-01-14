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

    # Construct the final data string with total_binary_length, file size, and file name
    final_data = f"|::-::|FILE METADATA|:-:|{os.path.basename(file_path)}|:-:|{file_size}|:-:|{total_binary_length}|:-:|{sha1.hexdigest()}|::-::||"  # Extra pipe in the end, otherwise the previous pipe is not recognized properly and is recognized as `}` as probably it continues binary reading.

    # Convert final data string to binary string
    final_data_binary = "".join(format(ord(char), format_string) for char in final_data)

    # Yield final data in chunks of bits_per_frame
    for i in range(0, len(final_data_binary), bits_per_frame):
        print(f"Metadata:{i}")
        yield final_data_binary[i:i + bits_per_frame]
