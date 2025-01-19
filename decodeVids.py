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
from libs.downloadFromYT import downloadFromYT
from libs.determine_color_key import determine_color_key
from libs.transmit_file import transmit_file

config = load_config('config.ini')


def get_available_filename_to_decode(filename):
    data_folder_decoded = config['data_folder_decoded']
    original_filepath = os.path.join(data_folder_decoded, filename)

    if not os.path.exists(original_filepath):
        return filename

    decoded_filename = f"decoded_{filename}"
    decoded_filepath = os.path.join(data_folder_decoded, decoded_filename)
    if not os.path.exists(decoded_filepath):
        return decoded_filename

    count = 1
    while True:
        incremented_filename = f"decoded({count:02})_{filename}"
        incremented_filepath = os.path.join(data_folder_decoded, incremented_filename)
        if not os.path.exists(incremented_filepath):
            return incremented_filename
        count += 1


def writer_process(write_queue, file_path):
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


def get_file_metadata(vid, encoding_color_map, frame_step, num_frames):
    # Initialize variables
    metadata_main_delimiter = '|::-::|'
    metadata_sub_delimiter = '|:-:|'
    bit_buffer = ''
    output_data = ''
    metadata_bit_count = 0

    metadata_frames = frame_step
    metadata_length = None

    while True:
        if output_data != '':
            break
        for frame_index in range(2, num_frames, frame_step):
            frame = vid.get_data(frame_index)
            y = config['start_height']
            while y < config['end_height']:
                for x in range(config['start_width'], config['end_width'], 2):
                    # Look for the metadata length prefix
                    if metadata_length is None and len(output_data) > len(
                            metadata_main_delimiter) and output_data.endswith(
                                metadata_main_delimiter):
                        output_data = output_data.replace(metadata_main_delimiter, "")
                        metadata_length = int(output_data)
                        output_data = ''

                    nearest_color_key = determine_color_key(frame, x, y, encoding_color_map)
                    bit_buffer += nearest_color_key
                    if metadata_length is not None:
                        metadata_bit_count += 1
                    if len(bit_buffer) == 8:
                        decoded_char = int(bit_buffer, 2).to_bytes(1, byteorder='big')
                        output_data += decoded_char.decode('utf-8', errors='ignore')
                        bit_buffer = ''

                        # Check if we've received enough data based on metadata_length
                        if metadata_length and metadata_bit_count >= metadata_length:
                            break  # Exit the inner loops once metadata is fully read
                else:
                    y += 2
                    continue  # Continue `while y` loop, Only reached if its inner loop was not forcefully broken
                break  # Break out of `while y` loop
            else:
                continue  # Continue `for frame_index` loop, Only reached if its inner loop was not forcefully broken
            break  # Break out of `for frame_index` loop
        else:
            break  # Break out of `while True` loop, Only reached if its inner loop was not forcefully broken
        continue  # Continue `while True` loop

    # After exiting the loop, process the final_metadata
    if not output_data:
        print("No metadata found.")
        sys.exit(1)

    # Since metadata was tripled, extract one instance
    triplet_length = len(output_data) // 3
    metadata_triplet = output_data[:triplet_length]

    # Verify that all three copies are identical
    if output_data[:triplet_length] != output_data[triplet_length:2*triplet_length] or \
       output_data[:triplet_length] != output_data[2*triplet_length:]:
        print("Metadata triplication verification failed.")
        sys.exit(1)

    metadata_with_checksum = metadata_triplet

    # Extract checksum
    checksum_prefix = '|CHECKSUM:'
    checksum_start = metadata_with_checksum.find(checksum_prefix)
    if checksum_start == -1:
        print("Checksum not found in metadata.")
        sys.exit(1)

    checksum_end = metadata_with_checksum.find('|', checksum_start + len(checksum_prefix))
    if checksum_end == -1:
        print("Invalid checksum format.")
        sys.exit(1)

    checksum_value_str = metadata_with_checksum[checksum_start + len(checksum_prefix):checksum_end]
    try:
        checksum_value = int(checksum_value_str)
    except ValueError:
        print("Invalid checksum value.")
        sys.exit(1)

    # Extract the actual metadata without checksum
    actual_metadata = metadata_with_checksum[:checksum_start]

    # Verify checksum
    calculated_checksum = sum(ord(c) for c in actual_metadata) % 256
    if calculated_checksum != checksum_value:
        print("Checksum verification failed.")
        sys.exit(1)

    # Split the actual_metadata into parts
    # Expected format:
    # |::-::|FILE METADATA|:-:|{file_basename}|:-:|{file_size}|:-:|{total_binary_length}|:-:|{sha1_hash}|::-::|
    if actual_metadata.startswith(metadata_main_delimiter) and actual_metadata.endswith(
            metadata_main_delimiter):
        actual_metadata = actual_metadata[len(metadata_main_delimiter
                                              ):-len(metadata_main_delimiter)]
    else:
        print(f"Metadata delimiter ({metadata_main_delimiter}) mismatch.")
        sys.exit(1)

    parts = actual_metadata.split(metadata_sub_delimiter)

    if len(parts) != 5:
        print("The metadata does not split into the correct number of parts.")
        sys.exit(1)

    # Extract fields
    # parts[0] should start with 'FILE METADATA'
    if not parts[0].startswith('FILE METADATA'):
        print("Metadata header mismatch.")
        sys.exit(1)

    file_basename = parts[1]
    file_size = parts[2]
    total_binary_length = parts[3]
    sha1_hash = parts[4]

    # Create the transmit_file_obj
    transmit_file_obj = transmit_file(file_basename, file_size, total_binary_length, sha1_hash)

    return metadata_frames, transmit_file_obj


def process_frame(frame_details):
    frame, encoding_color_map, frame_index, frame_step, total_binary_length, num_frames = frame_details

    if frame_index >= (num_frames - frame_step):
        data_index = config['bits_per_frame'] * math.floor(frame_index / frame_step)

    bit_buffer = ''
    output_data = []
    bits_used_in_frame = 0

    y = config['start_height']
    while y < config['end_height']:
        for x in range(config['start_width'], config['end_width'], 2):
            if bits_used_in_frame >= config['bits_per_frame'] or \
                (frame_index >= (num_frames - frame_step) and data_index >= total_binary_length):
                break
            nearest_color_key = determine_color_key(frame, x, y, encoding_color_map)
            bit_buffer += nearest_color_key
            if len(bit_buffer) == 8:
                output_data.append(int(bit_buffer, 2).to_bytes(1, byteorder='big'))
                bit_buffer = ''
            if frame_index >= (num_frames - frame_step):
                data_index += 1
            bits_used_in_frame += 1
        y += 2
        if bits_used_in_frame >= config['bits_per_frame'] or \
            (frame_index >= (num_frames - frame_step) and data_index >= total_binary_length):
            break
    if len(bit_buffer) != 0:
        print('bit_buffer is not empty.')
        sys.exit(1)
    return frame_index, output_data


def count_frames(video_path):
    video = cv2.VideoCapture(video_path)
    frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    video.release()
    return frame_count


def process_images(video_path, encoding_map_path, debug=False):
    with open(encoding_map_path, 'r') as file:
        encoding_color_map = json.load(file)

    vid = imageio.get_reader(video_path, 'ffmpeg')
    num_frames = count_frames(video_path)
    print(f"Number of frames: {num_frames}")

    frame_step = config['repeat_same_frame'][1]

    sha1 = hashlib.sha1()

    manager = Manager()
    write_queue = manager.Queue()
    heap = []

    pbar = tqdm(total=int(num_frames / frame_step), desc="Processing Frames")
    metadata_frames, file_metadata = get_file_metadata(vid, encoding_color_map, frame_step,
                                                       num_frames)
    frame_start = metadata_frames + config['pick_frame_to_read'][1]

    stream_encoded_file = open(f"{file_metadata.name}_encoded_stream.txt", "r") if debug else None
    stream_decoded_file = open(f"{file_metadata.name}_decoded_stream.txt", "w") if debug else None

    next_frame_to_write = frame_start

    heap = []  # Process results as they become available

    # Create a multiprocessing pool to process the remaining frames except the first and last one
    writer_pool = Pool(1)
    available_filename = get_available_filename_to_decode(file_metadata.name)
    writer_pool.apply_async(writer_process, (write_queue, available_filename))
    with Pool(cpu_count()) as pool:
        frame_iterator = ((vid.get_data(index), encoding_color_map, index, frame_step,
                           file_metadata.binary_length, num_frames)
                          for index in range(frame_start, num_frames, frame_step))
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
                            print(
                                f"Mismatch at frame {frame_index}: expected:\n{expected_binary_string}\n, got:\n{data_binary_string}\n"
                            )
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

    if sha1.hexdigest() == file_metadata.sha1:
        print("Files decoded successfully, SHA1 matched: " + available_filename)
    else:
        print(
            "Files decoded was unsuccessfull, SHA1 mismatched, deleting file if debug is false: " +
            available_filename)
        if not debug:
            os.remove(available_filename)


if __name__ == "__main__":
    video_url = input("Please enter the URL to the video file: ")
    downloadFromYT(video_url)
    process_images(os.path.join("storage", "output", "Test03.iso.mp4"), config['encoding_map_path'])
