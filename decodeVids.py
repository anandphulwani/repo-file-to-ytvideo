import json
import math
import imageio
import heapq
from tqdm import tqdm
from multiprocessing import Pool, cpu_count, Manager
from libs.config_loader import load_config
from libs.downloadFromYT import downloadFromYT
from libs.determine_color_key import determine_color_key

config = load_config('config.ini')

def writer_process(write_queue, file_path):
    # count = 0
    with open(file_path, 'wb') as binary_output_file:
        while True:
            item = write_queue.get(True)  # This will block until an item is available
            if item is None:  # Check for the termination signal
                break
            frame_index, data = item
            try:
                for byte_data in data:
                    binary_output_file.write(byte_data)
            except Exception as e:
                print(f"Error writing data: {e} on frame_index: {frame_index}")
                break  # Exit on error

total_binary_length = 0

def process_frame(frame_details):
    global total_binary_length
    frame, encoding_color_map, frame_index, frame_step, total_binary_length, num_frames = frame_details
    # print (f'frame_index: {frame_index}, num_frames: {num_frames}')
    
    if frame_index >= (num_frames - frame_step):
        data_index = config['bits_per_frame'] * math.floor(frame_index / frame_step)
    
    total_binary_length_binary = ''
    bit_buffer = ''
    output_data = []
    bits_used_in_frame = 0

    y = config['start_height']
    while y < config['end_height']:
        for x in range(config['start_width'], config['end_width'], 2):
            if bits_used_in_frame >= config['bits_per_frame'] or \
                (frame_index >= (num_frames - frame_step) and total_binary_length != 0 and data_index >= total_binary_length):
                break
            nearest_color_key = determine_color_key(frame, x, y, encoding_color_map)
            if total_binary_length == 0:
                total_binary_length_binary += nearest_color_key
                if len(total_binary_length_binary) == 160:
                    total_binary_length = ''.join(chr(int(total_binary_length_binary[i:i+8], 2)) for i in range(0, len(total_binary_length_binary), 8))
                    total_binary_length = int(total_binary_length) + 160
                    # print(total_binary_length)
            else:
                bit_buffer += nearest_color_key
                if len(bit_buffer) == 8:
                    output_data.append(int(bit_buffer, 2).to_bytes(1, byteorder='big'))
                    bit_buffer = ''
                if frame_index >= (num_frames - frame_step):
                    data_index += 1
            bits_used_in_frame += 1
        y += 2
        if bits_used_in_frame >= config['bits_per_frame'] or \
            (frame_index >= (num_frames - frame_step) and total_binary_length != 0 and data_index >= total_binary_length):
            break
    return frame_index, output_data

def process_images(video_path, encoding_map_path):
    global total_binary_length
    with open(encoding_map_path, 'r') as file:
        encoding_color_map = json.load(file)

    vid = imageio.get_reader(video_path, 'ffmpeg')
    num_frames = vid.count_frames() # get_total_frames(video_path)
    
    metadata = vid.get_meta_data()
    fps = int(metadata['fps'])
    frame_step = config['repeat_same_frame']
    frame_start = math.ceil(frame_step / 2) + 1 if frame_step > 1 else 0
    
    manager = Manager()
    write_queue = manager.Queue()
    heap = []
    
    pbar = tqdm(total=int(num_frames / frame_step), desc="Processing Frames")
    
    # First frame processing
    return_value = process_frame((vid.get_data(frame_start), encoding_color_map, 0, frame_step, 0, num_frames))
    write_queue.put(return_value)
    pbar.update(1)
    
    frame_start += frame_step
    next_frame_to_write = frame_start

    heap = [] # Process results as they become available
    
    # Create a multiprocessing pool to process the remaining frames except the first and last one
    writer_pool = Pool(1)
    writer_pool.apply_async(writer_process, (write_queue, "file_rev.exe"))
    with Pool(cpu_count()) as pool:
        frame_iterator = ((vid.get_data(index), encoding_color_map, index, frame_step, total_binary_length, num_frames) for index in range(frame_start, num_frames - frame_step, frame_step))
        result_iterator = pool.imap_unordered(process_frame, frame_iterator)
        
        for result in result_iterator:
            heapq.heappush(heap, result)
            while heap and heap[0][0] == next_frame_to_write:
                return_value = heapq.heappop(heap)
                write_queue.put(return_value)
                next_frame_to_write += frame_step
                pbar.update(1)
        pool.close()
        pool.join()

    # Last frame processing
    return_value = process_frame((vid.get_data(num_frames - 1), encoding_color_map, num_frames - 1, frame_step, total_binary_length, num_frames))
    write_queue.put(return_value)
    pbar.update(1)

    write_queue.put(None)
    writer_pool.close()
    writer_pool.join()
    
    pbar.close()

if __name__ == "__main__":                        
    video_url = input("Please enter the URL to the video file: ")
    downloadFromYT(video_url)
    process_images('video_downloaded.mp4', config['encoding_map_path'])
