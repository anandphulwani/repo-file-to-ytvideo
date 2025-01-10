from tqdm import tqdm
import base64
import os
import sys
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
    
    stream_file = open(f"{file_path}_stream.txt", "w") if debug else None
        
    base, format_string = detect_base_from_json(config)
    print(f"Base is {base}")

    if not os.path.exists(file_path):
        print("The specified file does not exist.")
        sys.exit(1)

    # Read the file content
    with open(file_path, "rb") as file:
        file_content = file.read()

    # Convert the file content based on the detected base
    if base == 64: # Directly encode for base64
        encoded_data = base64.b64encode(file_content).decode('utf-8')
    else:
        # For other bases, encode each byte individually
        encoded_data = "".join(f"{byte:{format_string}}" for byte in file_content)    
        # encoded_data = "".join(f"{byte:08b}" for byte in file_content)

    total_binary_length = len(encoded_data)
    
    paddedleft20_total_binary_length = str(total_binary_length).zfill(20)
    paddedleft20_total_binary_length_binary = ''.join(format(ord(char), '08b') for char in paddedleft20_total_binary_length)
    encoded_data =  "".join([paddedleft20_total_binary_length_binary, encoded_data])
    
    return [encoded_data[i:i + bits_per_frame] for i in range(0, len(encoded_data), bits_per_frame)]
