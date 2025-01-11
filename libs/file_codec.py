from tqdm import tqdm
import base64
import os
import sys
import math
import hashlib
from .detect_base_from_json import detect_base_from_json

def encodeddata_to_file(encoded_data, video_path, encoding_map_path='encoding_color_map.json'):
    base = detect_base_from_json(encoding_map_path)
    if base == 64:
        binary_data = base64.b64decode(encoded_data)
    else:
        base_functions = {
            2: lambda x: int(x, 2),
            8: lambda x: int(x, 8),
            10: lambda x: int(x, 10),
            16: lambda x: int(x, 16),
        }
        
        # Determine the size of each segment based on the base, because the encoded data length for each byte can vary with base
        segment_length = {
            2: 8,  # 1 byte = 8 bits
            8: 3,  # 1 byte = up to 3 octal digits
            10: 3, # This is more complex as it doesn't align neatly; likely needs special handling
            16: 2,  # 1 byte = 2 hexadecimal digits
        }

        if base == 10: # Special handling for base 10 (variable length encoding)
            # Assuming decimal encoded data is separated by a non-numeric character, e.g., ","
            # This is a simplification; real implementation might need to consider how data was encoded
            segments = encoded_data.split(',')
            binary_data = bytes(int(segment) for segment in segments)
        else:
            binary_data = bytes(base_functions[base](encoded_data[i:i+segment_length[base]]) for i in range(0, len(encoded_data), segment_length[base]))

    # Write binary data to output file
    with open(f"file_reverse.exe", "wb") as f:
        with tqdm(total=len(binary_data), unit='B', unit_scale=True, desc=f"Writing binary data to {video_path}_reverse.rev") as pbar:
            for chunk in range(0, len(binary_data), 1024):
                f.write(binary_data[chunk:chunk+1024])
                pbar.update(min(1024, len(binary_data) - chunk))

    print(f"Encoded data converted back to {video_path}_reverse.rev")
     
def file_to_encodeddata(config, file_path, debug = False):
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
    final_data = f"|::-::|FILE METADATA|:-:|{os.path.basename(file_path)}|:-:|{file_size}|:-:|{total_binary_length}|:-:|{sha1.hexdigest()}|::-::||" # Extra pipe in the end, otherwise the previous pipe is not recognized properly and is recognized as `}` as probably it continues binary reading.
    
    # Convert final data string to binary string
    final_data_binary = "".join(format(ord(char), format_string) for char in final_data)

    # Yield final data in chunks of bits_per_frame
    for i in range(0, len(final_data_binary), bits_per_frame):
        print(f"Metadata:{i}")
        yield final_data_binary[i:i+bits_per_frame]
