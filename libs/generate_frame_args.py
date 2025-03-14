import time
import psutil


def generate_frame_args(frame_queue, config, frame_data_iter, encoding_color_map, debug):
    while True:
        if psutil.virtual_memory().available < config['ram_threshold_trigger']:
            while psutil.virtual_memory().available < config['ram_threshold_trigger']:
                time.sleep(1)
            while psutil.virtual_memory().available < config['ram_threshold_resume']:
                time.sleep(1)

        try:
            content_type, frame_data = next(frame_data_iter)
            if frame_data is None:
                break
            frame = frame_queue.get()
            if frame is None:
                break
            yield (frame, config, encoding_color_map, frame_data, None, content_type, debug)
        except StopIteration:
            break
