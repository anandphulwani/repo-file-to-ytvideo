import cv2
import os
import json
import heapq
import sys
import hashlib
import threading
from queue import Queue
from tqdm import tqdm
from multiprocessing import Pool, cpu_count, Manager
from libs.config_loader import load_config
from libs.check_video_file import check_video_file
from libs.content_type import ContentType
from libs.downloadFromYT import downloadFromYT
from libs.get_available_filename_to_decode import get_available_filename_to_decode
from libs.count_frames import count_frames
from libs.writer_process import writer_process
from libs.process_frame_optimized import process_frame_optimized
from libs.get_file_metadata import get_file_metadata
from libs.produce_tasks import produce_tasks
from libs.frame_reader_thread import frame_reader_thread

config = load_config('config.ini')


def process_images(video_path, encoding_map_path, debug=False):
    with open(encoding_map_path, 'r') as file:
        encoding_color_map = json.load(file)

    cap = cv2.VideoCapture(video_path)
    check_video_file(config, cap)
    num_frames = count_frames(video_path)
    print(f"Number of frames: {num_frames}")

    metadata_frames, file_metadata = get_file_metadata(config, cap, encoding_color_map, num_frames, debug)
    cap.release()  # Close video file
    cv2.destroyAllWindows()

    # 2) Prepare parameters
    frame_start = metadata_frames + config['pick_frame_to_read'][ContentType.DATACONTENT.value]
    frame_step = config['total_frames_repetition'][ContentType.DATACONTENT.value]
    end_index = num_frames - 1
    total_baseN_length = file_metadata.metadata["total_baseN_length"]

    config_params = {
        "start_height": config["start_height"],
        "start_width": config["start_width"],
        "box_step": config["data_box_size_step"][ContentType.DATACONTENT.value],
        "usable_w": config["usable_width"][ContentType.DATACONTENT.value],
        "usable_h": config["usable_height"][ContentType.DATACONTENT.value],
        "databoxes_per_frame": config["usable_databoxes_in_frame"][ContentType.DATACONTENT.value],
        "encoding_base": config["encoding_base"],
        "encoding_chunk_size": config["encoding_chunk_size"],
        "decoding_function": config["decoding_function"],
        "encoding_color_map_keys": config["encoding_color_map_keys"],
        "encoding_color_map_values": config["encoding_color_map_values"],
        "encoding_color_map_values_lower_bounds": config["encoding_color_map_values_lower_bounds"],
        "encoding_color_map_values_upper_bounds": config["encoding_color_map_values_upper_bounds"],
        "premetadata_metadata_main_delimiter": config['premetadata_metadata_main_delimiter'],
        "premetadata_metadata_sub_delimiter": config['premetadata_metadata_sub_delimiter'],
        "length_of_digits_to_represent_size": config['length_of_digits_to_represent_size']
    }

    #---------------------------------------------------------------------
    # B) PREP FOR WRITING & SHA1
    #---------------------------------------------------------------------
    manager = Manager()
    write_queue = manager.Queue()
    writer_pool = Pool(1)  # a single writer
    available_filename = get_available_filename_to_decode(config, file_metadata.metadata["filename"])
    writer_pool.apply_async(writer_process, (write_queue, available_filename))

    sha1 = hashlib.sha1()

    #---------------------------------------------------------------------
    # C) OPEN VIDEO & LAUNCH READER THREAD
    #---------------------------------------------------------------------
    cap = cv2.VideoCapture(video_path)
    check_video_file(config, cap)

    # This event allows us to signal the thread to stop if needed
    stop_event = threading.Event()

    # Create a queue to hold frames
    frame_queue = Queue(maxsize=32)  # buffer up to N frames

    # Start the dedicated reading thread
    t_reader = threading.Thread(target=frame_reader_thread, args=(cap, frame_queue, stop_event, frame_start, end_index, frame_step), daemon=True)
    t_reader.start()

    #---------------------------------------------------------------------
    # D) MULTIPROCESSING POOL & IMAP
    #---------------------------------------------------------------------
    # We'll feed tasks from produce_tasks(...) to process_frame_optimized(...)
    pool = Pool(cpu_count())

    # If you keep a debug text check:
    stream_encoded_file = open(f"{file_metadata.metadata['filename']}_encoded_stream.txt", "r") if debug else None
    stream_decoded_file = open(f"{file_metadata.metadata['filename']}_decoded_stream.txt", "w") if debug else None

    # We'll track results in a min-heap so we can output in ascending order
    heap = []
    next_frame_to_write = frame_start

    # We expect this many frames for DATACONTENT
    count_main_frames = max(0, (end_index - frame_start) // frame_step + 1)
    pbar = tqdm(total=count_main_frames, desc="Decoding DATACONTENT")

    # Fire off the parallel tasks
    result_iterator = pool.imap_unordered(
        process_frame_optimized,
        produce_tasks(frame_queue=frame_queue,
                      stop_event=stop_event,
                      config_params=config_params,
                      content_type=ContentType.DATACONTENT,
                      frame_step=frame_step,
                      total_baseN_length=total_baseN_length,
                      num_frames=num_frames,
                      metadata_frames=metadata_frames,
                      convert_return_output_data=None))

    # E) COLLECT RESULTS
    for result in result_iterator:
        # result is (frame_index, output_data)
        heapq.heappush(heap, result)
        # flush from the heap in ascending order
        while heap and heap[0][0] == next_frame_to_write:
            frame_index, output_data = heapq.heappop(heap)

            # Update SHA1 & debug checks
            for data_bytes in output_data:
                sha1.update(data_bytes)
                if stream_encoded_file:
                    data_binary_string = ''.join(f"{byte:08b}" for byte in data_bytes)
                    if stream_decoded_file:
                        stream_decoded_file.write(data_binary_string)
                    expected_binary_string = stream_encoded_file.read(len(data_binary_string))
                    if data_binary_string != expected_binary_string:
                        print(f"Mismatch at frame {frame_index}: "
                              f"expected={expected_binary_string}, got={data_binary_string}")
                        sys.exit(1)

            # Pass data to writer
            write_queue.put((frame_index, output_data))

            next_frame_to_write += frame_step
            pbar.update(1)

    #---------------------------------------------------------------------
    # F) CLEANUP
    #---------------------------------------------------------------------
    # 1) Stop the thread & close the pool
    stop_event.set()
    frame_queue.put(None)  # to ensure produce_tasks stops
    pool.close()
    pool.join()

    t_reader.join(timeout=1.0)
    cap.release()
    pbar.close()

    # 2) Signal writer to finish
    write_queue.put(None)
    writer_pool.close()
    writer_pool.join()

    stream_encoded_file and stream_encoded_file.close()
    stream_decoded_file and stream_decoded_file.close()

    # 4) Check final SHA1
    if sha1.hexdigest() == file_metadata.metadata["sha1_checksum"]:
        print(f"Files decoded successfully, SHA1 ({sha1.hexdigest()}) matched: {available_filename}")
    else:
        print(
            f"Files decoded was unsuccessful, SHA1 mismatched, metadata SHA1 ({file_metadata.metadata['sha1_checksum']}) != computed SHA1 ({sha1.hexdigest()}) => removing file (debug={debug})"
        )
        if not debug:
            os.remove(available_filename)


if __name__ == "__main__":
    video_url = input("Please enter the URL to the video file: ")
    downloadFromYT(video_url)
    process_images(os.path.join("storage", "output", "Test03.iso.mp4"), config['encoding_map_path'])
