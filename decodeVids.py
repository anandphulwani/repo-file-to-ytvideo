import cv2
import os
import json
import math
import heapq
import sys
import hashlib
from tqdm import tqdm
from multiprocessing import Pool, cpu_count, Manager
from libs.config_loader import load_config
from libs.check_video_file import check_video_file
from libs.generate_frame_args import generate_frame_args
from libs.content_type import ContentType
from libs.downloadFromYT import downloadFromYT
from libs.get_available_filename_to_decode import get_available_filename_to_decode
from libs.count_frames import count_frames
from libs.writer_process import writer_process
from libs.process_frame_optimized import process_frame_optimized
from libs.get_file_metadata import get_file_metadata

config = load_config('config.ini')


def frame_data_iter(start_index, end_index, frame_step):
    for i in range(start_index, end_index + 1, frame_step):
        yield (ContentType.DATACONTENT, i)


def process_images(video_path, encoding_map_path, debug=False):
    with open(encoding_map_path, 'r') as file:
        encoding_color_map = json.load(file)

    cap = cv2.VideoCapture(video_path)
    check_video_file(config, cap)
    num_frames = count_frames(video_path)
    print(f"Number of frames: {num_frames}")

    sha1 = hashlib.sha1()

    manager = Manager()
    write_queue = manager.Queue()
    heap = []

    metadata_frames, file_metadata = get_file_metadata(config, cap, encoding_color_map, num_frames, debug)
    cap.release()  # Close video file
    cv2.destroyAllWindows()

    frame_start = metadata_frames + config['pick_frame_to_read'][ContentType.DATACONTENT.value]
    frame_step = config['total_frames_repetition'][ContentType.DATACONTENT.value]

    pbar = tqdm(total=math.floor((num_frames - metadata_frames) / frame_step), desc="Processing Frames")

    stream_encoded_file = open(f"{file_metadata.metadata['filename']}_encoded_stream.txt", "r") if debug else None
    stream_decoded_file = open(f"{file_metadata.metadata['filename']}_decoded_stream.txt", "w") if debug else None

    next_frame_to_write = frame_start

    heap = []  # Process results as they become available

    # 2) Prepare parameters
    frame_start = metadata_frames + config['pick_frame_to_read'][ContentType.DATACONTENT.value]
    frame_step = config['total_frames_repetition'][ContentType.DATACONTENT.value]
    end_index = num_frames - 1
    total_baseN_length = file_metadata.metadata["total_baseN_length"]
    databoxes_per_frame = config["usable_databoxes_in_frame"][ContentType.DATACONTENT.value]

    config_params = {
        "start_height": config["start_height"],
        "start_width": config["start_width"],
        "box_step": config["data_box_size_step"][ContentType.DATACONTENT.value],
        "usable_w": config["usable_width"][ContentType.DATACONTENT.value],
        "usable_h": config["usable_height"][ContentType.DATACONTENT.value],
        "databoxes_per_frame": config["usable_databoxes_in_frame"][ContentType.DATACONTENT.value]
    }

    cap = cv2.VideoCapture(video_path)
    check_video_file(config, cap)

    # A small generator that tells which frames we want to decode (and which we skip).
    frame_iter = frame_data_iter(start_index=frame_start, end_index=end_index, frame_step=frame_step)

    # Step B: Setup for DATACONTENT reading (the largest portion)
    # Create a multiprocessing pool to process the remaining frames except the first and last one
    writer_pool = Pool(1)
    available_filename = get_available_filename_to_decode(config, file_metadata.metadata["filename"])
    writer_pool.apply_async(writer_process, (write_queue, available_filename))
    with Pool(cpu_count()) as pool:
        result_iterator = pool.imap_unordered(
            process_frame_optimized,
            (
                (
                    config_params,
                    frame,  # BGR frame
                    encoding_color_map,
                    frame_index,
                    frame_step,
                    total_baseN_length,
                    num_frames,
                    metadata_frames)
                for (frame, config, encoding_color_map, local_frame_index, frame_index, content_type, debug) in generate_frame_args(
                    cap=cap,
                    config=config,  # or config_params—depends on your code
                    frame_data_iter=frame_iter,
                    encoding_color_map=None,  # if you need it, or pass a real map
                    debug=debug,
                    start_index=frame_start,
                    frame_step=frame_step)))

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
