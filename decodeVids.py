from moviepy.editor import VideoFileClip
import numpy as np
import json
import time
import random
import math
import base64
import sys
import imageio
import subprocess
import cv2
from tqdm import tqdm
from pytube import YouTube
from statistics import mode, StatisticsError
# from multiprocessing import Pool, cpu_count
import multiprocessing
from queue import Queue
from threading import Thread
from collections import OrderedDict
import heapq

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

# def average_colors(color1, color2, color3, color4, color5, color6):
#     avg_red = (int(color1[0]) + int(color2[0]) + int(color3[0]) + int(color4[0]) + int(color5[0]) + int(color6[0])) // 6
#     avg_green = (int(color1[1]) + int(color2[1]) + int(color3[1]) + int(color4[1]) + int(color5[1]) + int(color6[1])) // 6
#     avg_blue = (int(color1[2]) + int(color2[2]) + int(color3[2]) + int(color4[2]) + int(color5[2]) + int(color6[2])) // 6
#     return (avg_red, avg_green, avg_blue)

def get_total_frames(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Error opening video file")
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return total_frames

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

def determine_color_key(frame, x, y, encoding_color_map): 
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
    return nearest_color_key    

num_elements = 0

def process_frame(frame_details):
    global num_elements
    frame, encoding_color_map, frame_index, num_elements, num_frames, shared_data = frame_details
    # print(f"frame_index: {frame_index}, num_elements: {num_elements}")
    
    used_data_index = 0
    init_data_index = 0
    
    # with shared_data.get_lock():
    init_data_index = shared_data['data_index']
    print(f"init_data_index: {init_data_index}")
    
    num_elements_binary = ''
    bit_buffer = ''
    
    output_data = []

    bits_used_in_frame = 0

    y = start_height
    while y < end_height:
        for x in range(start_width, end_width, 2):
            if bits_used_in_frame >= bits_per_frame or \
                (frame_index == (num_frames - 1) and num_elements != 0 and (init_data_index + used_data_index) >= num_elements):
                break
            nearest_color_key = determine_color_key(frame, x, y, encoding_color_map)
            if num_elements == 0:
                num_elements_binary += nearest_color_key
                if len(num_elements_binary) == 160:
                    num_elements = ''.join(chr(int(num_elements_binary[i:i+8], 2)) for i in range(0, len(num_elements_binary), 8))
                    num_elements = int(num_elements)
                    # print(num_elements)
            else:
                bit_buffer += nearest_color_key
                # if reference_data[used_data_index:used_data_index+1] != nearest_color_key:
                #     print(f"Mismatch found y:{y}, x:{x} at index {used_data_index}: expected '{reference_data[used_data_index:used_data_index+1]}', got '{nearest_color_key}'")
                #     print(f"colorX1Y1: {tuple(frame[y, x])}")
                #     print(f"colorX1Y2: {tuple(frame[y + 1, x])}")
                #     print(f"colorX2Y1: {tuple(frame[y, x + 1])}")
                #     print(f"colorX2Y2: {tuple(frame[y + 1, x + 1])}")
                if len(bit_buffer) == 8:
                    output_data.append(int(bit_buffer, 2).to_bytes(1, byteorder='big'))
                    bit_buffer = ''
                used_data_index += 1
            bits_used_in_frame += 1
        y += 2
        if bits_used_in_frame >= bits_per_frame or \
            (frame_index == (num_frames - 1) and num_elements != 0 and (init_data_index + used_data_index) >= num_elements):
            break
    # with shared_data.get_lock():
    shared_data['data_index'] += used_data_index
    # print(f"End frame_index: {frame_index}")
    return frame_index, output_data

def process_images(video_path, encoding_map_path):
    global num_elements
    with open(encoding_map_path, 'r') as file:
        encoding_color_map = json.load(file)

    # with open('vlc.exe_stream.txt', 'r') as file:
    #     reference_data = file.read()
    
    manager = multiprocessing.Manager()
    shared_data = manager.dict()
    shared_data['data_index'] = 0 
    
    vid = imageio.get_reader(video_path, 'ffmpeg')
    num_frames = vid.count_frames() # get_total_frames(video_path)
    
    results = []
    heap = []
    next_frame_to_write = 0

    pbar = tqdm(total=num_frames, desc="Processing Frames")
    
    for index, frame in enumerate(vid):
        if index == 0:
            frame_result = process_frame((frame, encoding_color_map, 0, 0, num_frames, shared_data))
            results.append(frame_result)
            next_frame_to_write = 1
            pbar.update(1)
            break

    # Create a multiprocessing pool to process the remaining frames except the last one
    with multiprocessing.Pool(multiprocessing.cpu_count()) as pool:
        frame_iterator = ((frame, encoding_color_map, index, num_elements, num_frames, shared_data) for index, frame in enumerate(vid) if index >= 1 and index <= 2) # num_frames - 2
        result_iterator = pool.imap_unordered(process_frame, frame_iterator)
        heap = [] # Process results as they become available
        for result in result_iterator:
            heapq.heappush(heap, result)
            while heap and heap[0][0] == next_frame_to_write:
                ready_to_write = heapq.heappop(heap)
                results.append(ready_to_write)
                next_frame_to_write += 1
                pbar.update(1)

    for index, frame in enumerate(vid):
        if index == num_frames - 1:
            frame_result = process_frame((frame, encoding_color_map, num_frames - 1, num_elements, num_frames, shared_data))
            results.append(frame_result)
            next_frame_to_write += 1
            pbar.update(1)
            break

    # results = []
    # for index, frame in enumerate(vid):
    #     processed_frame = process_frame((frame, encoding_color_map, index, num_frames), reference_data)
    #     results.append(processed_frame)
    #     pbar.update(1)
    
    pbar.close()
    with open("file_rev.exe", 'wb') as binary_output_file:
        for _, frame_data in sorted(results):
            for data in frame_data:
                binary_output_file.write(data)

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

    # process_images(ExtractFrames('video_downloaded.mp4'), encoding_map_path)
    process_images('video_downloaded.mkv', encoding_map_path)
    
    # process_images(ExtractFrames('video_downloaded.mp4'), 'encoding_color_map.json')
    
    # Write the decoded bytes to the output file
    # with open(f"", "w") as file:
    #     file.write(encoded_data)
    
    # if encoded_data:
    #     pass
    #     # print("Video successfully decoded to data.")
    #     # encodeddata_to_file(encoded_data, "fdm_rev.exe", encoding_map_path)
    # else:
    #     print("No data was decoded from the video.")
