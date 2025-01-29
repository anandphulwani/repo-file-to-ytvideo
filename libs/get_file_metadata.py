import sys
from .content_type import ContentType
from .determine_color_key import determine_color_key
from .transmit_file import transmit_file


def get_file_metadata(config, vid, encoding_color_map, num_frames):
    # Initialize variables
    metadata_main_delimiter = '|::-::|'
    metadata_sub_delimiter = '|:-:|'
    bit_buffer = ''
    output_data = ''
    metadata_bit_count = 0

    metadata_length = None

    frame_step = config['total_frames_repetition'][ContentType.METADATA.value]

    usable_width = config['usable_width'][ContentType.METADATA.value]
    usable_height = config['usable_height'][ContentType.METADATA.value]

    while True:
        if output_data != '':
            break
        for frame_index in range(config['pick_frame_to_read'][ContentType.METADATA.value], num_frames, frame_step):
            metadata_frames = frame_index - config['pick_frame_to_read'][ContentType.METADATA.value] + frame_step

            frame = vid.get_data(frame_index)
            y = config['start_height']
            while y < config['start_height'] + usable_height:
                for x in range(config['start_width'], config['start_width'] + usable_width, config['data_box_size_step'][ContentType.METADATA.value]):
                    # Look for the metadata length prefix
                    if metadata_length is None and len(output_data) > len(metadata_main_delimiter) and output_data.endswith(metadata_main_delimiter):
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
                    y += config['data_box_size_step'][ContentType.METADATA.value]
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
    if actual_metadata.startswith(metadata_main_delimiter) and actual_metadata.endswith(metadata_main_delimiter):
        actual_metadata = actual_metadata[len(metadata_main_delimiter):-len(metadata_main_delimiter)]
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
