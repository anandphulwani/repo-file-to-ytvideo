from moviepy.editor import VideoFileClip
import numpy as np
import json
import base64
import sys
import imageio
import subprocess
import cv2
from tqdm import tqdm
from pytube import YouTube
from statistics import mode, StatisticsError
from multiprocessing import Pool, cpu_count

# def average_colors(color1, color2, color3, color4, color5, color6):
#     avg_red = (int(color1[0]) + int(color2[0]) + int(color3[0]) + int(color4[0]) + int(color5[0]) + int(color6[0])) // 6
#     avg_green = (int(color1[1]) + int(color2[1]) + int(color3[1]) + int(color4[1]) + int(color5[1]) + int(color6[1])) // 6
#     avg_blue = (int(color1[2]) + int(color2[2]) + int(color3[2]) + int(color4[2]) + int(color5[2]) + int(color6[2])) // 6
#     return (avg_red, avg_green, avg_blue)

def average_colors(color1, color2, color3, color4):
    avg_red = (int(color1[0]) + int(color2[0]) + int(color3[0]) + int(color4[0])) // 4
    avg_green = (int(color1[1]) + int(color2[1]) + int(color3[1]) + int(color4[1])) // 4
    avg_blue = (int(color1[2]) + int(color2[2]) + int(color3[2]) + int(color4[2])) // 4
    return (avg_red, avg_green, avg_blue)

def find_nearest_tuple(color_tuples):
    transformed = [0 if t[0] < 103 else 1 for t in color_tuples if t[0] < 103 or t[0] > 153]
    try:
        dominant_category = mode(transformed)
    except StatisticsError:
        print(f"color_tuples: {color_tuples}")
        sys.exit(1)
    return (0, 0, 0) if dominant_category == 0 else (255, 255, 255)

def detect_base_from_json(encoding_map_path):
    # Identical function from your encoder script
    # Load and check the JSON encoding map
    with open(encoding_map_path, 'r') as file:
        encoding_map = json.load(file)
    base = len(encoding_map)
    return base

def find_nearest_color(pixel_color, encoding_color_map):
    color_map_rgb = {key: tuple(int(encoding_color_map[key][i:i+2], 16) for i in (1, 3, 5)) for key in encoding_color_map}
    min_distance = float('inf')
    nearest_color_key = None
    for key, value in color_map_rgb.items():
        distance = np.linalg.norm(np.array(pixel_color) - np.array(value))
        if distance < min_distance:
            min_distance = distance
            nearest_color_key = key
    return nearest_color_key

def process_images(frames, encoding_map_path, frame_width = 1920, frame_height = 1080):
    with open(encoding_map_path, 'r') as file:
        encoding_color_map = json.load(file)

    padding = 80
    buffer_padding = 20

    num_elements = 0
    num_elements_binary = ''
    
    bit_buffer = ''

    # with open("vlc.exe_stream.txt", 'r') as original_stream, open("vlc.exe_reverse_stream.txt", 'w') as output_file, open("file_rev.exe", 'wb') as binary_output_file:
    # with open("vlc.exe_stream.txt", 'r') as original_stream, open("file_rev.exe", 'wb') as binary_output_file:
    with open("file_rev.exe", 'wb') as binary_output_file:
        data_index = 0  # To keep track of the position in the original stream
        for frame_index, frame in enumerate(tqdm(frames, desc="Processing frames")):
                # if frame_index == 350:
                #     print("Written here")
                #     cv2.imwrite('output_image.png', frame)
                
                y = padding + buffer_padding
                end_offset = frame_height - 1 - padding - buffer_padding
                # print(f"y: {y}, end_offset: {end_offset}")
                
                while  y < end_offset:    
                    for x in range(0 + padding + buffer_padding, frame_width - padding - buffer_padding, 2):
                        if num_elements != 0 and data_index >= num_elements + 160:
                            print("I am breaking here now")
                            break
                        
                        nearest_color_key = ''
                        colorX1Y1 = tuple(frame[y, x])
                        colorX1Y2 = ''
                        colorX2Y1 = ''
                        colorX2Y2 = ''
                        if colorX1Y1[0] <= 50 and colorX1Y1[1] <= 50 and colorX1Y1[2] <= 50:
                            nearest_color_key = "0"
                        elif colorX1Y1[0] >= 200 and colorX1Y1[1] >= 200 and colorX1Y1[2] >= 200:
                            nearest_color_key = "1"
                        else:
                            colorX1Y2 = tuple(frame[y + 1, x])
                            if colorX1Y2[0] <= 50 and colorX1Y2[1] <= 50 and colorX1Y2[2] <= 50:
                                nearest_color_key = "0"
                            elif colorX1Y2[0] >= 200 and colorX1Y2[1] >= 200 and colorX1Y2[2] >= 200:
                                nearest_color_key = "1"
                            else:
                                colorX2Y1 = tuple(frame[y, x + 1])
                                if colorX2Y1[0] <= 50 and colorX2Y1[1] <= 50 and colorX2Y1[2] <= 50:
                                    nearest_color_key = "0"
                                elif colorX2Y1[0] >= 200 and colorX2Y1[1] >= 200 and colorX2Y1[2] >= 200:
                                    nearest_color_key = "1"
                                else:
                                    colorX2Y2 = tuple(frame[y + 1, x + 1])
                                    if colorX2Y2[0] <= 50 and colorX2Y2[1] <= 50 and colorX2Y2[2] <= 50:
                                        nearest_color_key = "0"
                                    elif colorX2Y2[0] >= 200 and colorX2Y2[1] >= 200 and colorX2Y2[2] >= 200:
                                        nearest_color_key = "1"
                                    else:
                                        color = average_colors(colorX1Y1, colorX1Y2, colorX2Y1, colorX2Y2)
                                        nearest_color_key = find_nearest_color(color, encoding_color_map)
                        
                        if num_elements == 0:
                            num_elements_binary += nearest_color_key
                            if len(num_elements_binary) == 160:
                                num_elements = ''.join(chr(int(num_elements_binary[i:i+8], 2)) for i in range(0, len(num_elements_binary), 8))
                                num_elements = int(num_elements)
                                print(num_elements)
                        else:
                            bit_buffer += nearest_color_key
                            if len(bit_buffer) == 8:
                                binary_output_file.write(int(bit_buffer, 2).to_bytes(1, byteorder='big'))
                                bit_buffer = ''        
                        
                            # original_char = original_stream.read(1)
                            # if not original_char:
                            #     print("End of original stream reached.")
                            #     sys.exit(1)
                                
                            # output_file.write(nearest_color_key)

                            # if nearest_color_key != original_char:
                            #     cv2.imwrite('img_error.png', frame)
                            #     print(f"Mismatch found y:{y}, x:{x} at index {data_index}: expected '{original_char}', got '{nearest_color_key}'")
                            #     print(f"colorX1Y1: {colorX1Y1}, {tuple(frame[y, x])}")
                            #     print(f"colorX1Y2: {colorX1Y2}, {tuple(frame[y + 1, x])}")
                            #     print(f"colorX2Y1: {colorX2Y1}, {tuple(frame[y, x + 1])}")
                            #     print(f"colorX2Y2: {colorX2Y2}, {tuple(frame[y + 1, x + 1])}")
                            #     # print(f"colorX3Y1: {colorX2Y1}, {tuple(frame[y, x + 2])}")
                            #     # print(f"colorX3Y2: {colorX2Y2}, {tuple(frame[y + 1, x + 2])}")
                            #     sys.exit(1)
                        data_index += 1
                    y += 2
            
def ExtractFrames(video_path):
    am = []
    vid = imageio.get_reader(video_path, 'ffmpeg')
    # fps = vid.get_meta_data()['fps']
    num_frames = vid.get_length()
    with tqdm(total=num_frames) as pbar:
        for i, frame in enumerate(vid):
            # # if i == 360 * 6:
            # #     break
            # # if i % 6 == 5:
            # if i % 2 == 1:
            #     am.append(frame)
            am.append(frame)
            pbar.update(1)
    return am

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

def get_resolution(s):
    return int(s.resolution[:-1])

def downloadFromYT(url, format_code = '270'):
    command = ['yt-dlp', '-F', url]
    try:
        output = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print(output.stdout.decode())
    except subprocess.CalledProcessError as e:
        print("Error listing formats:", e.stderr.decode())
        return None
    
    command = [
        'yt-dlp',
        '-f', format_code,
        '--merge-output-format', 'mp4',
        '-o', 'video_downloaded.mp4',
        url
    ]

    try:
        subprocess.run(command, check=True)
        print(f"Downloaded video in format {format_code}.")
    except subprocess.CalledProcessError as e:
        print(f"Error downloading the video in format {format_code}:", e.stderr.decode())

if __name__ == "__main__":                        
    video_url = input("Please enter the URL to the video file: ")
    downloadFromYT(video_url)
    
    # encoding_map_path = input("Please enter the path to the encoding color map JSON file (press enter to use default): ")
    encoding_map_path = ""
    if not encoding_map_path.strip():
        print("in here")
        encoding_map_path = 'encoding_color_map.json'  # Default path

    process_images(ExtractFrames('video_downloaded.mp4'), encoding_map_path)
    
    # frames = ExtractFrames('video_downloaded.mp4')
    # process_images(frames, 'encoding_color_map.json')
    
    # Write the decoded bytes to the output file
    # with open(f"", "w") as file:
    #     file.write(encoded_data)
    
    # if encoded_data:
    #     pass
    #     # print("Video successfully decoded to data.")
    #     # encodeddata_to_file(encoded_data, "fdm_rev.exe", encoding_map_path)
    # else:
    #     print("No data was decoded from the video.")
