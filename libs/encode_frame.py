import sys
import cv2
import datetime
from os import path


def encode_frame(args):
    frame, config, encoding_color_map, frame_data, frame_index, content_type, debug = args
    data_box_size_step = config['data_box_size_step'][content_type.value]
    usable_width = config['usable_width'][content_type.value]
    usable_height = config['usable_height'][content_type.value]

    if frame_data is None:
        print(f'frame_index: {frame_index}, frame_data: `{frame_data}` does not have any data.')
        sys.exit(1)

    frame[0 + config['margin']:config['frame_height'] - config['margin'],
          0 + config['margin']:config['frame_width'] - config['margin']] = (255, 255, 255)

    bits_used_in_frame = 0
    for y in range(config['start_height'], config['start_height'] + usable_height, data_box_size_step):
        for x in range(config['start_width'], config['start_width'] + usable_width, data_box_size_step):
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

    # Save the frame
    cv2.imwrite(path.join("storage", "output", f"frame_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.png"), frame) if debug else None
    return (frame_index, frame, content_type)
