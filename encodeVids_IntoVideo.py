import gc
from os import path, makedirs
import sys
import json
import cv2
import heapq
from multiprocessing import Pool, cpu_count
from libs.config_loader import load_config
from libs.file_codec import file_to_encodeddata
from libs.ffmpeg_process import create_ffmpeg_process, close_ffmpeg_process
from libs.merge_ts_to_mp4_dynamic_chunk import merge_ts_to_mp4_dynamic_chunk

config = load_config('config.ini')


def generate_frame_args(cap, config, frame_data_iter, encoding_color_map):
    frame_index = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        try:
            is_metadata, frame_data = next(frame_data_iter)
            if frame_data is None:
                break
            yield (frame, config, encoding_color_map, frame_data, frame_index, is_metadata)
            frame_index += 1
        except StopIteration:
            break


def encode_frame(args):
    frame, config, encoding_color_map, frame_data, frame_index, is_metadata = args
    data_box_size_step = config['data_box_size_step'][0] if is_metadata else config[
        'data_box_size_step'][1]
    usable_width = config['usable_width'][0] if is_metadata else config['usable_width'][1]
    usable_height = config['usable_height'][0] if is_metadata else config['usable_height'][1]

    if frame_data is None:
        print(f'frame_index: {frame_index}, frame_data: `{frame_data}` does not have any data.')
        sys.exit(1)

    frame[0 + config['margin']:config['frame_height'] - config['margin'],
          0 + config['margin']:config['frame_width'] - config['margin']] = (255, 255, 255)

    bits_used_in_frame = 0
    for y in range(config['start_height'], config['start_height'] + usable_height,
                   data_box_size_step):
        for x in range(config['start_width'], config['start_width'] + usable_width,
                       data_box_size_step):
            if bits_used_in_frame >= len(frame_data):
                break
            try:
                char = frame_data[bits_used_in_frame]
            except Exception as e:
                print("Error:", e)
                sys.exit(1)
            if char in encoding_color_map:
                color = tuple(int(encoding_color_map[char][i:i + 2], 16) for i in (1, 3, 5))[::-1]
            else:
                raise ValueError(f"Unknown character: {char} found in encoded data stream")
            frame[y:y + data_box_size_step, x:x + data_box_size_step] = color
            bits_used_in_frame += 1
        if bits_used_in_frame >= len(frame_data):
            break
    return (frame_index, frame, is_metadata)


def check_video_file(config, cap):
    if not cap.isOpened():
        raise IOError("Error opening video stream or file")
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if config['frame_width'] != frame_width or config['frame_height'] != frame_height:
        print(
            f"Config's frame dimensions ({config['frame_width']}x{config['frame_height']}) do not match video dimensions ({frame_width}x{frame_height})."
        )
        sys.exit(1)


def process_video_frames(file_path, config):
    with open(config['encoding_map_path'], 'r') as file:
        encoding_color_map = json.load(file)

    frame_data_iter = iter(file_to_encodeddata(config, file_path))
    print('Encoding done.')

    cap = cv2.VideoCapture(config['bgr_video_path'])
    check_video_file(config, cap)

    # Create output directory based on input file name
    output_dir = path.basename(file_path) + config['output_video_suffix']
    output_dir = path.join("storage", "output", output_dir)
    makedirs(output_dir, exist_ok=True)
    print(f"Output directory created at: {output_dir}")

    # Initialize FFmpeg process for content segments
    segment_index = 0

    content_and_metadata_stream = None
    metadata_stream_toggle = False

    next_frame_to_write = 0
    heap = []

    with Pool(cpu_count()) as pool:
        result_iterator = pool.imap_unordered(
            encode_frame, generate_frame_args(cap, config, frame_data_iter, encoding_color_map))

        for result in result_iterator:
            heapq.heappush(heap, result)
            while heap and heap[0][0] == next_frame_to_write:
                _, frame_to_write, is_metadata = heapq.heappop(heap)

                # Determine if a new FFmpeg process needs to be started
                should_toggle_metadata = is_metadata and not metadata_stream_toggle
                should_start_new_segment = not is_metadata and (
                    next_frame_to_write % config['frames_per_content_part_file'] == 0)

                if should_toggle_metadata or should_start_new_segment:
                    if content_and_metadata_stream:
                        close_ffmpeg_process(content_and_metadata_stream, f"{segment_index:02d}")

                    # Determine parameters for create_ffmpeg_process
                    segment_index = segment_index + 1 if should_start_new_segment else segment_index
                    metadata_stream_toggle = True if should_toggle_metadata else metadata_stream_toggle
                    content_and_metadata_stream = create_ffmpeg_process(
                        output_dir, config, None if should_toggle_metadata else segment_index,
                        should_toggle_metadata)
                    print(
                        f"Started FFmpeg process for {'metadata segment.' if should_toggle_metadata else f'content segment {segment_index:02d}.'}"
                    )

                # Write the frame multiple times as specified in the config
                total_frames_repetition = config['total_frames_repetition'][
                    0] if is_metadata else config['total_frames_repetition'][1]
                for _ in range(total_frames_repetition):
                    content_and_metadata_stream.stdin.write(frame_to_write)
                content_and_metadata_stream.stdin.flush()
                next_frame_to_write += 1
                if len(heap) % 10 == 0:
                    gc.collect()
        gc.collect()

    # Release everything if the job is finished
    cap.release()
    close_ffmpeg_process(content_and_metadata_stream, "Metadata")
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

    process_video_frames(file_path, config)
    merge_ts_to_mp4_dynamic_chunk(output_dir, path.join("storage", "output", "Test03.iso.mp4"),
                                  path.join("storage", "output"))

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
