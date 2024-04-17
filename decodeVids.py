from moviepy.editor import VideoFileClip
import numpy as np
import json
import base64
import sys
import imageio
from PIL import Image
from tqdm import tqdm

def detect_base_from_json(encoding_map_path):
    # Identical function from your encoder script
    # Load and check the JSON encoding map
    with open(encoding_map_path, 'r') as file:
        encoding_map = json.load(file)
    base = len(encoding_map)
    return base

# def video_to_encodeddata(video_path, encoding_map_path='encoding_color_map.json'):
#     # Load the video
#     clip = VideoFileClip(video_path)
#     frames = [frame for frame in clip.iter_frames()]
    
#     # Load the encoding color map and create a reverse map
#     with open(encoding_map_path, 'r') as file:
#         encoding_color_map = json.load(file)
#     reverse_encoding_map = {str(tuple(int(encoding_color_map[char][k:k+2], 16) for k in (1, 3, 5))): char for char in encoding_color_map}
#     # Handle base64 padding character specifically
#     reverse_encoding_map[str((0, 0, 0))] = '='
    
#     encoded_data = ""
#     pixel_size = 4  # This should match the encoder

#     # Convert each frame back to encoded data
#     for frame in frames:
#         width, height, _ = frame.shape
#         for y in range(0, height, pixel_size):
#             for x in range(0, width, pixel_size):
#                 # Extract the color of the top-left pixel of each 'pixel block'
#                 color = tuple(frame[y, x])
#                 if str(color) in reverse_encoding_map:
#                     print("found color")
#                     encoded_data += reverse_encoding_map[str(color)]
#                 else:
#                     print(f"Unknown color {color} found in video frame at x:{x} and y:{y}.")
#                     sys.exit(1)
    
#     with open(f"{video_path}_decoded_stream.txt", "w") as file:
#         file.write(encoded_data)
#     return encoded_data

# def decode_data_to_file(encoded_data, output_file_path, encoding_map_path='encoding_color_map.json'):
#     base = detect_base_from_json(encoding_map_path)
    
#     # Decode the encoded data based on the base
#     if base == 64:
#         file_content = base64.b64decode(encoded_data)
#     else:
#         # For other bases, decode each encoded character sequence to bytes
#         # This part may need adjustment based on how encoding was implemented for other bases
#         # Assuming each character in encoded_data represents a byte value in the specified base
#         base_functions = {
#             2: lambda x: int(x, 2),
#             8: lambda x: int(x, 8),
#             10: lambda x: int(x, 10),
#             16: lambda x: int(x, 16),
#         }
#         bytes_list = [base_functions[base](char) for char in encoded_data]
#         file_content = bytes(bytes_list)
    
#     # Write the decoded bytes to the output file
#     with open(output_file_path, "wb") as file:
#         file.write(file_content)
    
#     print(f"File {output_file_path} successfully reconstructed.")

def find_nearest_color(pixel_color, encoding_color_map):
    # Convert encoding map values to RGB tuples
    color_map_rgb = {key: tuple(int(encoding_color_map[key][i:i+2], 16) for i in (1, 3, 5)) for key in encoding_color_map}
    
    # Initialize minimum distance and corresponding color key
    min_distance = float('inf')
    nearest_color_key = None

    # Calculate Euclidean distance to each color in the map
    for key, value in color_map_rgb.items():
        distance = np.linalg.norm(np.array(pixel_color) - np.array(value))
        if distance < min_distance:
            min_distance = distance
            nearest_color_key = key
    
    return nearest_color_key

def process_images(frames, encoding_map_path):
    # Load the encoding color map
    with open(encoding_map_path, 'r') as file:
        encoding_color_map = json.load(file)
        
    encoded_data = ''

    for frame in tqdm(frames, desc="Processing frames"):
        # Assuming frame is already in the desired color format, otherwise convert it
        pixel_size = 4  # Hardcode the pixel size to 4

        for y in range(0, frame.shape[0], pixel_size):
            for x in range(0, frame.shape[1], pixel_size):
                # Get the color of the current pixel
                color = frame[y, x]
                # Find the nearest color in the encoding map and append its key to the encoded data
                nearest_color_key = find_nearest_color(color, encoding_color_map)
                encoded_data += nearest_color_key
                
    return encoded_data

def ExtractFrames(video_path):
    am = []
    
    # Open the video file
    vid = imageio.get_reader(video_path, 'ffmpeg')

    # Get the fps of the video
    fps = vid.get_meta_data()['fps']

    # Get the total number of frames in the video
    num_frames = vid.get_length()

    # Use tqdm to create a progress bar
    with tqdm(total=num_frames) as pbar:
        # Iterate over every frame of the video
        for i, frame in enumerate(vid):
            # Append the frame to the list
            am.append(frame)
            # Update the progress bar
            pbar.update(1)

    # Return the list of frames
    return am

def encodeddata_to_file(encoded_data, video_path, encoding_map_path='encoding_color_map.json'):
    base = detect_base_from_json(encoding_map_path)

    if base == 64:
        # For base64, directly decode the entire string
        binary_data = base64.b64decode(encoded_data)
    else:
        # For other bases, convert each segment of the encoded data back to bytes
        base_functions = {
            2: lambda x: int(x, 2),
            8: lambda x: int(x, 8),
            10: lambda x: int(x, 10),
            16: lambda x: int(x, 16),
        }
        
        # Determine the size of each segment based on the base
        # This is necessary because the encoded data length for each byte can vary with base
        segment_length = {
            2: 8,  # 1 byte = 8 bits
            8: 3,  # 1 byte = up to 3 octal digits
            10: 3, # This is more complex as it doesn't align neatly; likely needs special handling
            16: 2,  # 1 byte = 2 hexadecimal digits
        }

        # Special handling for base 10 (variable length encoding)
        if base == 10:
            # Assuming decimal encoded data is separated by a non-numeric character, e.g., ","
            # This is a simplification; real implementation might need to consider how data was encoded
            segments = encoded_data.split(',')
            binary_data = bytes(int(segment) for segment in segments)
        else:
            binary_data = bytes(base_functions[base](encoded_data[i:i+segment_length[base]]) for i in range(0, len(encoded_data), segment_length[base]))

    # Write binary data to output file
    with open(f"{video_path}_reverse.rev", "wb") as f:
        with tqdm(total=len(binary_data), unit='B', unit_scale=True, desc=f"Writing binary data to {video_path}_reverse.rev") as pbar:
            for chunk in range(0, len(binary_data), 1024):
                f.write(binary_data[chunk:chunk+1024])
                pbar.update(min(1024, len(binary_data) - chunk))

    print(f"Encoded data converted back to {video_path}_reverse.rev")
    
if __name__ == "__main__":
    video_path = input("Please enter the path to the video file: ")
    encoding_map_path = input("Please enter the path to the encoding color map JSON file (press enter to use default): ")
    if not encoding_map_path.strip():
        encoding_map_path = 'encoding_color_map.json'  # Default path

    # encoded_data = video_to_encodeddata(video_path, encoding_map_path)
    encoded_data = process_images(ExtractFrames(video_path), encoding_map_path)
    # Write the decoded bytes to the output file
    with open(f"{video_path}_reverse_stream", "w") as file:
        file.write(encoded_data)
    
    if encoded_data:
        print("Video successfully decoded to data.")
        encodeddata_to_file(encoded_data, video_path, encoding_map_path)
    else:
        print("No data was decoded from the video.")
