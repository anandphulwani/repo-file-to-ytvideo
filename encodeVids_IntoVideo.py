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
import heapq
from multiprocessing import Pool, cpu_count
from libs.config_loader import load_config
from libs.file_codec import file_to_encodeddata

config = load_config('config.ini')

def generate_frame_args(cap, config, frame_data_iter, total_frames, total_binary_length, encoding_color_map):
    frame_index = 0
    while True:
        if frame_index >= total_frames:
            break
        ret, frame = cap.read()
        if not ret:
            break
        frame_data = next(frame_data_iter, None)
        yield (frame, config, encoding_color_map, frame_data, frame_index, total_frames, total_binary_length)
        frame_index += 1

def encode_frame(args):
    frame, config, encoding_color_map, frame_data, frame_index, total_frames, total_binary_length = args
    if frame_data is None:
        print(f'frame_index: {frame_index}, frame_data: `{frame_data}` does not have any data.')
        sys.exit(1)
        # return (frame_index, None)
    
    frame[0 + config['padding'] : config['frame_height'] - config['padding'], 0 + config['padding'] : config['frame_width'] - config['padding']] = (255, 255, 255)
    if frame_index == (total_frames - 1):
        data_index = config['bits_per_frame'] * frame_index
    
    bits_used_in_frame = 0
    for y in range(config['start_height'], config['end_height'], 2):
        for x in range(config['start_width'], config['end_width'], 2):
            if bits_used_in_frame >= config['bits_per_frame'] or (frame_index == (total_frames - 1) and data_index >= total_binary_length):
                break
            char = frame_data[bits_used_in_frame] # char = encoded_data[data_index]
            if char in encoding_color_map:
                color = tuple(int(encoding_color_map[char][i:i+2], 16) for i in (1, 3, 5))[::-1]
            else:
                raise ValueError(f"Unknown character: {char} found in encoded data stream")            
            frame[y:y+2, x:x+2] = color
            if frame_index == (total_frames - 1):
                data_index += 1
            bits_used_in_frame += 1
        if bits_used_in_frame >= config['bits_per_frame'] or (frame_index == (total_frames - 1) and data_index >= total_binary_length):
            break
    
    # print(f"\nconfig['frame_height']: {config['frame_height']}, config['padding']: {config['padding']}, config['buffer_padding']: {config['buffer_padding']}")
    # print(f"\ny: {y}, end_offset: {end_offset}")
    return (frame_index, frame)

def process_video_frames(file_path, config):
    with open(config['encoding_map_path'], 'r') as file:
        encoding_color_map = json.load(file)
    encoded_data = file_to_encodeddata(file_path, config['bits_per_frame'])
    print('Encoding done.')

    cap = cv2.VideoCapture(config['bgr_video_path'])
    if not cap.isOpened():
        raise IOError("Error opening video stream or file")
    
    if config['frame_width'] != int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or config['frame_height'] != int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)):
        print(f'Config\'s frame_width({config['frame_width']}) or Config\'s frame_height({config['frame_height']}) doesnot match `bgr_video_path` width({int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}) or height({int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}) respectively.')
        sys.exit(1)

    out = cv2.VideoWriter(config['output_video_path'], cv2.VideoWriter_fourcc(*'FFV1'), config['output_fps'], (config['frame_width'], config['frame_height'])) # *'mp4v'  ;   *'avc1'
    
    total_frames = len(encoded_data)
    total_binary_length = (config['bits_per_frame'] * (total_frames - 1)) + len(encoded_data[-1]) # 355362912
    # pbar = tqdm(total=total_binary_length, desc="Encoding data into video")

    next_frame_to_write = 0
    heap = []
    frame_index = 0
    frame_data_iter = iter(encoded_data)

    with Pool(cpu_count()) as pool:
        result_iterator = pool.imap_unordered(
            encode_frame, 
            generate_frame_args(cap, config, frame_data_iter, total_frames, total_binary_length, encoding_color_map)
        )
        pbar = tqdm(total=len(encoded_data), desc="Encoding data into video")
        
        for result in result_iterator:
            heapq.heappush(heap, result)
            while heap and heap[0][0] == next_frame_to_write:
                _, frame_to_write = heapq.heappop(heap)
                for _ in range(config['repeat_same_frame']):
                    out.write(frame_to_write)
                next_frame_to_write += 1
                pbar.update(1)

    sys.exit(1)
    
    # frame_data_iter = iter(encoded_data)
    # frame_args = []
    # frame_index = 0
    # while True:
    #     ret, frame = cap.read()
    #     if not ret:
    #         break
    #     frame_data = next(frame_data_iter, None)
    #     frame_args.append((frame, config, encoding_color_map, frame_data, frame_index))
    #     frame_index += 1

    # with Pool(cpu_count()) as pool:
    #     # imap_unordered allows processing results to be yielded as soon as they are ready, without waiting for previous ones to complete
    #     result_iterator = pool.imap_unordered(encode_frame, frame_args)
    #     heap = []
    #     next_frame_to_write = 0
    #     pbar = tqdm.tqdm(total=len(frame_args), desc="Encoding data into video")
        
    #     for result in result_iterator:
    #         heapq.heappush(heap, result)
    #         # As long as the smallest-indexed frame is the next one to write, pop from heap and write to video
    #         while heap and heap[0][0] == next_frame_to_write:
    #             _, frame_to_write = heapq.heappop(heap)
    #             out.write(frame_to_write)
    #             next_frame_to_write += 1
    #             pbar.update(1)
                
    # 
    # frame_args = []
    # frame_index = 0
    # while True:
    #     ret, frame = cap.read()
    #     if not ret:
    #         break
        
    #     frame_data = next(frame_data_iter, None)
    #     frame_args.append((frame, config, encoding_color_map, frame_data, frame_index))
    #     frame_index += 1

    # with Pool(cpu_count()) as pool:
    #     results = pool.map(encode_frame, frame_args)
    
    # # Sort results by frame index to ensure correct order
    # results.sort(key=lambda x: x[0])

    # pbar = tqdm.tqdm(total=len(results), desc="Encoding data into video")
    # for _, frame in results:
    #     out.write(frame)
    #     pbar.update(1)

    # Release everything if the job is finished
    pbar.close()
    cap.release()
    out.release()
    print(f"Modification is done, frame_index: {frame_index}")

# def inject_frames_to_outvideo(file_path='vlc.exe'):
#     data_index = 0
#     while True:
#         pbar.update(1)
#         # if frame_counter == (8 * 22):
#         #     cv2.imwrite('output_image.png', frame)
#         out.write(frame)
#         if data_index >= total_binary_length:
#             break 

    

# try:
#     inject_frames(config['bgr_video_path'], config['output_video_path'], frames)
#     print("Video processing completed.")
# except IOError as e:
#     print(str(e))

if __name__ == "__main__":
    # Ask the user for the path to the file they wish to encode
    # file_path = input("Please enter the file path to encode: ")

    # Encode the file
    # try:
    # inject_frames_to_outvideo()
    process_video_frames('vlc.exe', config)
    
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
