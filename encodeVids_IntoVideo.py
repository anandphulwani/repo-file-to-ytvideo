from PIL import Image
import math
import os
import base64
import sys
import json
from moviepy.editor import ImageSequenceClip
import numpy as np
from PIL import Image
from tqdm import tqdm
import cv2

padding = 80
buffer_padding = 20
frame_width = 1920
frame_height = 1080

skip_seconds = 0

start_width = padding + buffer_padding
end_width = frame_width - padding - buffer_padding

start_height = padding + buffer_padding
end_height = frame_height - 1 - padding - buffer_padding

usable_width = ( end_width - start_width ) // 2
usable_height = ( end_height - start_height ) // 2

bits_per_frame = math.floor((usable_width * usable_height) / 8) * 8


def detect_base_from_json(encoding_map_path):
    # Load and check the JSON encoding map
    with open(encoding_map_path, 'r') as file:
        encoding_map = json.load(file)
    base = len(encoding_map)

    # Map the base to its corresponding function
    base_functions = {
        2: bin,
        8: oct,
        10: lambda x: str(x),
        16: hex,
        64: lambda x: base64.b64encode(x).decode('utf-8')
    }

    if base in base_functions:
        return base, base_functions[base]
    else:
        print("Unsupported base detected in JSON encoding map.")
        sys.exit(1)

def file_to_encodeddata(file_path, encoding_map_path='encoding_color_map.json'):
    base, base_function = detect_base_from_json(encoding_map_path)

    print(f"Base is {base}")

    # Check if the file exists
    if not os.path.exists(file_path):
        print("The specified file does not exist.")
        sys.exit(1)

    # Read the file content
    with open(file_path, "rb") as file:
        file_content = file.read()

    # Convert the file content based on the detected base
    if base == 64:  # Directly encode for base64
        encoded_data = base_function(file_content)
    else:
        # For other bases, encode each byte individually
        encoded_data = "".join(f"{byte:08b}" for byte in file_content)
        # encoded_data = "".join(base_function(byte)[2:] for byte in file_content)

    return encoded_data

def inject_frames_to_outvideo(video_path="disco_lights.mp4", output_path="video_downloaded.mkv", encoding_map_path='encoding_color_map.json', file_path='vlc.exe'):
    new_fps=30
    encoded_data = file_to_encodeddata(file_path, encoding_map_path)
    
    with open(f"{file_path}_stream.txt", "w") as file:
        file.write(encoded_data)
    
    base, base_function = detect_base_from_json(encoding_map_path)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError("Error opening video stream or file")

    # frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    # frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'FFV1'), new_fps, (frame_width, frame_height)) # *'mp4v'  ;   *'avc1'

    with open(encoding_map_path, 'r') as file:
        encoding_color_map = json.load(file)

    data_index = 0
    num_elements = len(encoded_data)
    
    paddedleft20_num_elements = str(num_elements).zfill(20)
    paddedleft20_num_elements_binary = ''.join(format(ord(char), '08b') for char in paddedleft20_num_elements)
    encoded_data =  "".join([paddedleft20_num_elements_binary, encoded_data])
    num_elements = len(encoded_data)
    
    pbar = tqdm(total=num_elements, desc="Encoding data into video")
    
    frame_counter = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_counter += 1

        frame[0 + padding : frame_height - padding, 0 +  padding : frame_width - padding] = (255, 255, 255)

        # print(f"\nframe_height: {frame_height}, padding: {padding}, buffer_padding: {buffer_padding}")
        # print(f"\ny: {y}, end_offset: {end_offset}")
        
        bits_used_in_frame = 0

        y = start_height
        while y < end_height:
            for x in range(start_width, end_width, 2):
                if bits_used_in_frame >= bits_per_frame or data_index >= num_elements:
                    break
                char = encoded_data[data_index]
                if char in encoding_color_map:
                    color = tuple(int(encoding_color_map[char][i:i+2], 16) for i in (1, 3, 5))[::-1]
                else:
                    raise ValueError(f"Unknown character: {char} found in encoded data stream")

                frame[y:y+2, x:x+2] = color
                data_index += 1
                bits_used_in_frame += 1
                pbar.update(1) 
            y += 2
            if bits_used_in_frame >= bits_per_frame or data_index >= num_elements:
                break
                

        # if frame_counter == (8 * 22):
        #     cv2.imwrite('output_image.png', frame)
        out.write(frame)
        if data_index >= num_elements:
            break 

    # Release everything if the job is finished
    pbar.close()
    cap.release()
    out.release()
    print(f"Modification is done, frame_counter: {frame_counter}")

# try:
#     inject_frames(video_path, output_path, frames)
#     print("Video processing completed.")
# except IOError as e:
#     print(str(e))

if __name__ == "__main__":
    # Ask the user for the path to the file they wish to encode
    # file_path = input("Please enter the file path to encode: ")

    # Optional: Ask for the path to the encoding color map JSON file
    # This step can be skipped if you always use a default path for the encoding map
    
    # encoding_map_path = input("Please enter the path to the encoding color map JSON file (press enter to use default): ")
    # if not encoding_map_path.strip():
    encoding_map_path = 'encoding_color_map.json'  # Default path

    # Encode the file
    # try:
    inject_frames_to_outvideo()
    
    # encoded_data = file_to_encodeddata(file_path, encoding_map_path)
    # if encoded_data:
    #     print("File successfully encoded.")
    #     inject_frames_to_outvideo()
    #     encodeddata_to_video(encoded_data, file_path)
    # else:
    #     print("No encoded data was returned.")
    
    #except FileNotFoundError:
    #    print(f"File not found: {file_path}")
    #    sys.exit(1)
    #except Exception as e:
    #    print(f"An error occurred: {e}")
    #    sys.exit(1)
