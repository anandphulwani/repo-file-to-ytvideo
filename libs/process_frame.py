import math
from .content_type import ContentType
from .determine_color_key import determine_color_key


def process_frame(frame_details):
    config, frame, encoding_color_map, frame_index, frame_step, total_baseN_length, num_frames, metadata_frames = frame_details
    data_index = config['usable_databoxes_in_frame'][ContentType.DATACONTENT.value] * math.floor(
        (frame_index - metadata_frames - config['pick_frame_to_read'][ContentType.DATACONTENT.value]) / frame_step) if frame_index == (
            num_frames - frame_step + config['pick_frame_to_read'][ContentType.DATACONTENT.value]) else None

    baseN_data_buffer = ''
    output_data = []
    databoxes_used_in_frame = 0

    usable_width = config['usable_width'][ContentType.DATACONTENT.value]
    usable_height = config['usable_height'][ContentType.DATACONTENT.value]

    y = config['start_height']
    while y < config['start_height'] + usable_height:
        for x in range(config['start_width'], config['start_width'] + usable_width, config['data_box_size_step'][ContentType.DATACONTENT.value]):
            if databoxes_used_in_frame >= config['usable_databoxes_in_frame'][ContentType.DATACONTENT.value] or \
                (data_index is not None and data_index >= total_baseN_length):
                break
            nearest_color_key = determine_color_key(frame, x, y, encoding_color_map)
            baseN_data_buffer += nearest_color_key
            if len(baseN_data_buffer) == 8:
                output_data.append(int(baseN_data_buffer, 2).to_bytes(1, byteorder='big'))
                baseN_data_buffer = ''
            if data_index is not None:
                data_index += 1
            databoxes_used_in_frame += 1
        y += config['data_box_size_step'][ContentType.DATACONTENT.value]
        if databoxes_used_in_frame >= config['usable_databoxes_in_frame'][ContentType.DATACONTENT.value] or \
            (data_index is not None and data_index >= total_baseN_length):
            break
    if len(baseN_data_buffer) != 0:
        print("baseN_data_buffer is not empty, currently it holds: ", baseN_data_buffer, ", databoxes_used_in_frame: ", databoxes_used_in_frame,
              ", config['usable_databoxes_in_frame'][", ContentType.DATACONTENT.value, "]: ",
              config['usable_databoxes_in_frame'][ContentType.DATACONTENT.value])
        sys.exit(1)
    return frame_index, output_data
