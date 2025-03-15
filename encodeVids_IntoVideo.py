import gc
from os import path, makedirs
import sys
import json
import cv2
import shutil
import threading
from multiprocessing import Pool, cpu_count
from queue import Queue
from libs.config_loader import load_config
from libs.content_type import ContentType
from libs.FileToEncodedData import FileToEncodedData
from libs.ffmpeg_process import create_ffmpeg_process, close_ffmpeg_process
from libs.merge_mp4_files_incremental import merge_mp4_files_incremental
from libs.generate_frame_args import generate_frame_args
from libs.check_video_file import check_video_file
from libs.encode_frame import encode_frame
from libs.write_frames import write_frames
from libs.background_reader import background_reader

config = load_config('config.ini')


def process_video_frames(file_path, config, debug):
    with open(config['encoding_map_path'], 'r') as file:
        encoding_color_map = json.load(file)

    frame_data_iter = FileToEncodedData(config, file_path, debug)
    print('Encoding done.')

    cap = cv2.VideoCapture(config['bgr_video_path'])
    check_video_file(config, cap)

    # Create output directory based on input file name
    output_dir = path.basename(file_path) + config['output_video_suffix']
    if not output_dir:
        print(f"Output directory name is empty. Please specify a valid filename for the input file: {file_path}")
        sys.exit(1)
    output_dir = path.join("storage", "output", output_dir)
    if path.exists(output_dir):
        shutil.rmtree(output_dir)
    makedirs(output_dir, exist_ok=True)
    print(f"Output directory created at: {output_dir}")

    # Start the background-reader thread with a queue of maxsize=90
    frame_queue = Queue(maxsize=14 * 4)
    stop_event = threading.Event()

    reader_thread = threading.Thread(
        target=background_reader,
        args=(cap, frame_queue, stop_event),
        daemon=True  # optionally make it a daemon if you want auto-stop
    )
    reader_thread.start()

    # Initialize FFmpeg process for content segments
    segment_index = 0

    content_and_metadata_stream = None

    next_frame_to_write = 0
    with Pool(cpu_count()) as pool:
        result_iterator = pool.imap(encode_frame, generate_frame_args(frame_queue, config, frame_data_iter, encoding_color_map, debug))

        for frame_to_write in result_iterator:
            should_start_new_segment = next_frame_to_write % config['frames_per_content_part_file'] == 0
            if should_start_new_segment:
                content_and_metadata_stream = close_ffmpeg_process(content_and_metadata_stream, ContentType.DATACONTENT,
                                                                   f"{segment_index:02d}") if content_and_metadata_stream else None

                # Determine parameters for create_ffmpeg_process
                segment_index = segment_index + 1 if should_start_new_segment else segment_index
                content_and_metadata_stream = create_ffmpeg_process(output_dir, config, segment_index, ContentType.DATACONTENT)
                print(f"Started FFmpeg process for content segment {segment_index:02d}.")

            # Write the frame multiple times as specified in the config
            write_frames(content_and_metadata_stream, frame_to_write)
            next_frame_to_write += 1
            if next_frame_to_write % 1000 == 0:
                gc.collect()
        gc.collect()

    content_and_metadata_stream = close_ffmpeg_process(content_and_metadata_stream, ContentType.DATACONTENT,
                                                       f"{segment_index:02d}") if content_and_metadata_stream else None
    # Start a new FFmpeg process
    content_and_metadata_stream = create_ffmpeg_process(output_dir, config, segment_index, ContentType.METADATA)
    print(f"Started FFmpeg process for metadata segment.")

    for frame_to_write in (encode_frame(frame_args)
                           for frame_args in generate_frame_args(frame_queue, config, frame_data_iter, encoding_color_map, debug)):
        # Write the frame multiple times as specified in the config
        write_frames(content_and_metadata_stream, frame_to_write)
    gc.collect()

    # Release everything if the job is finished
    content_and_metadata_stream = close_ffmpeg_process(content_and_metadata_stream, ContentType.METADATA, None)

    # Start a new FFmpeg process
    content_and_metadata_stream = create_ffmpeg_process(output_dir, config, segment_index, ContentType.PREMETADATA)
    print(f"Started FFmpeg process for pre_metadata segment.")

    for frame_to_write in (encode_frame(frame_args)
                           for frame_args in generate_frame_args(frame_queue, config, frame_data_iter, encoding_color_map, debug)):
        # Write the frame multiple times as specified in the config
        write_frames(content_and_metadata_stream, frame_to_write)
    gc.collect()

    # Release everything if the job is finished
    stop_event.set()
    reader_thread.join()
    cap.release()
    content_and_metadata_stream = close_ffmpeg_process(content_and_metadata_stream, ContentType.PREMETADATA, None)
    print("Modification is done.")


if __name__ == "__main__":
    # Ask the user for the path to the file they wish to encode
    # file_path = input("Please enter the file path to encode: ")

    # Encode the file
    # try:
    # inject_frames_to_outvideo()

    file_path = path.join("storage", "Test03.iso")
    output_dir = path.basename(file_path) + config['output_video_suffix']
    output_dir = path.join("storage", "output", output_dir)

    process_video_frames(file_path, config, debug=False)
    merge_mp4_files_incremental(output_dir, path.join("storage", "output", "Test03.iso.mp4"), path.join("storage", "output"))

    # process_video_frames(path.join("storage", "gparted.iso"), config)

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
