import gc
import sys
import json
from tqdm import tqdm
import cv2
import heapq
import ffmpeg
from multiprocessing import Pool, cpu_count
from libs.config_loader import load_config
from libs.file_codec import file_to_encodeddata

config = load_config('config.ini')

def generate_frame_args(cap, config, frame_data_iter, encoding_color_map):
    frame_index = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_data = next(frame_data_iter, None)
        if frame_data == None:
            break
        yield (frame, config, encoding_color_map, frame_data, frame_index)
        frame_index += 1

def encode_frame(args):
    frame, config, encoding_color_map, frame_data, frame_index = args
    if frame_data is None:
        print(f'frame_index: {frame_index}, frame_data: `{frame_data}` does not have any data.')
        sys.exit(1)
    
    frame[0 + config['padding'] : config['frame_height'] - config['padding'], 0 + config['padding'] : config['frame_width'] - config['padding']] = (255, 255, 255)
    
    bits_used_in_frame = 0
    for y in range(config['start_height'], config['end_height'], 2):
        for x in range(config['start_width'], config['end_width'], 2):
            if bits_used_in_frame >= len(frame_data):
                break
            char = frame_data[bits_used_in_frame] # char = encoded_data[data_index]
            if char in encoding_color_map:
                color = tuple(int(encoding_color_map[char][i:i+2], 16) for i in (1, 3, 5))[::-1]
            else:
                raise ValueError(f"Unknown character: {char} found in encoded data stream")            
            frame[y:y+2, x:x+2] = color
            bits_used_in_frame += 1
        if bits_used_in_frame >= len(frame_data):
            break
    return (frame_index, frame)

def check_video_file(config, cap):
    if not cap.isOpened():
        raise IOError("Error opening video stream or file")
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if config['frame_width'] != frame_width or config['frame_height'] != frame_height:
        print(f"Config's frame dimensions ({config['frame_width']}x{config['frame_height']}) do not match video dimensions ({frame_width}x{frame_height}).")
        sys.exit(1)

def process_video_frames(file_path, config):
    with open(config['encoding_map_path'], 'r') as file:
        encoding_color_map = json.load(file)

    encoded_data = file_to_encodeddata(config, file_path)
    print('Encoding done.')

    cap = cv2.VideoCapture(config['bgr_video_path'])
    check_video_file(config, cap)
    
    ffmpeg_process = (
        ffmpeg
        .input('pipe:', framerate=config['output_fps'], format='rawvideo', pix_fmt='bgr24', 
               s=f'{config["frame_width"]}x{config["frame_height"]}')
        .output(file_path + config['output_video_suffix'], vcodec='libx264', pix_fmt='yuv420p', 
                **{'b:v': '2000k', 'crf': 23, 'bufsize': '1024k'})
        .overwrite_output()
        .run_async(pipe_stdin=True)
    )
    
    next_frame_to_write = 0
    heap = []
    frame_data_iter = iter(encoded_data)

    with Pool(cpu_count()) as pool:
        result_iterator = pool.imap_unordered(
            encode_frame, 
            generate_frame_args(cap, config, frame_data_iter, encoding_color_map)
        )
        
        for result in result_iterator:
            heapq.heappush(heap, result)
            while heap and heap[0][0] == next_frame_to_write:
                _, frame_to_write = heapq.heappop(heap)
                for _ in range(config['repeat_same_frame']):
                    ffmpeg_process.stdin.write(frame_to_write)
                ffmpeg_process.stdin.flush()
                next_frame_to_write += 1
                if len(heap) % 10 == 0:
                    gc.collect()
        gc.collect()

    # Release everything if the job is finished
    cap.release()
    ffmpeg_process.stdin.close()
    ffmpeg_process.wait()
    print(f"Modification is done.")

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
