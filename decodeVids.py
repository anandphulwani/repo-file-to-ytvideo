import cv2
import os
import json
import math
import imageio
import heapq
import sys
import hashlib
from tqdm import tqdm
from multiprocessing import Pool, cpu_count, Manager
from libs.config_loader import load_config
from libs.content_type import ContentType
from libs.downloadFromYT import downloadFromYT
from libs.get_available_filename_to_decode import get_available_filename_to_decode
from libs.count_frames import count_frames
from libs.writer_process import writer_process
from libs.process_frame import process_frame
from libs.get_file_metadata import get_file_metadata

config = load_config('config.ini')


def process_images(video_path, encoding_map_path, debug=False):
    with open(encoding_map_path, 'r') as file:
        encoding_color_map = json.load(file)

    vid = imageio.get_reader(video_path, 'ffmpeg')
    num_frames = count_frames(video_path)
    print(f"Number of frames: {num_frames}")

    sha1 = hashlib.sha1()

    manager = Manager()
    write_queue = manager.Queue()
    heap = []

    metadata_frames, file_metadata = get_file_metadata(config, vid, encoding_color_map, num_frames)

    frame_start = metadata_frames + config['pick_frame_to_read'][ContentType.DATACONTENT.value]
    frame_step = config['total_frames_repetition'][ContentType.DATACONTENT.value]

    pbar = tqdm(total=math.floor((num_frames - metadata_frames) / frame_step), desc="Processing Frames")

    stream_encoded_file = open(f"{file_metadata.metadata['filename']}_encoded_stream.txt", "r") if debug else None
    stream_decoded_file = open(f"{file_metadata.metadata['filename']}_decoded_stream.txt", "w") if debug else None

    next_frame_to_write = frame_start

    heap = []  # Process results as they become available

    # Create a multiprocessing pool to process the remaining frames except the first and last one
    writer_pool = Pool(1)
    available_filename = get_available_filename_to_decode(config, file_metadata.metadata["filename"])
    writer_pool.apply_async(writer_process, (write_queue, available_filename))
    with Pool(cpu_count()) as pool:
        frame_iterator = ((config, vid.get_data(index), encoding_color_map, index, frame_step, file_metadata.metadata["total_binary_length"],
                           num_frames, metadata_frames) for index in range(frame_start, num_frames, frame_step))
        result_iterator = pool.imap_unordered(process_frame, frame_iterator)

        for result in result_iterator:
            heapq.heappush(heap, result)
            while heap and heap[0][0] == next_frame_to_write:
                return_value = heapq.heappop(heap)
                frame_index, output_data = return_value
                for data_bytes in output_data:
                    sha1.update(data_bytes)

                    # Verify the data read from the stream_encoded_file
                    if stream_encoded_file:
                        # Read the corresponding bytes from the stream_encoded_file
                        data_binary_string = ''.join(f"{byte:08b}" for byte in data_bytes)
                        stream_decoded_file and stream_decoded_file.write(data_binary_string)
                        expected_binary_string = stream_encoded_file.read(len(data_binary_string))
                        if data_binary_string != expected_binary_string:
                            print(f"Mismatch at frame {frame_index}: expected:\n{expected_binary_string}\n, got:\n{data_binary_string}\n")
                            sys.exit(1)

                write_queue.put(return_value)
                next_frame_to_write += frame_step
                pbar.update(1)
        pool.close()
        pool.join()

    write_queue.put(None)
    writer_pool.close()
    writer_pool.join()

    pbar.close()

    stream_encoded_file and stream_encoded_file.close()

    if sha1.hexdigest() == file_metadata.metadata["sha1_checksum"]:
        print("Files decoded successfully, SHA1 matched: " + available_filename)
    else:
        print("Files decoded was unsuccessfull, SHA1 mismatched, deleting file if debug is false: " + available_filename)
        if not debug:
            os.remove(available_filename)


if __name__ == "__main__":
    video_url = input("Please enter the URL to the video file: ")
    downloadFromYT(video_url)
    process_images(os.path.join("storage", "output", "Test03.iso.mp4"), config['encoding_map_path'])
