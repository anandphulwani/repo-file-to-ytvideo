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
            bgr_frames_count = 1 if config["use_same_bgr_frame_for_repetetion"] else config["total_frames_repetition"][content_type.value]
            frames_batch = []
            for _ in range(bgr_frames_count):
                frame = frame_queue.get()
                if frame is None:
                    break
                frames_batch.append(frame)

            if not frames_batch:
                break
            yield (frames_batch, config, encoding_color_map, frame_data, None, content_type, debug)
        except StopIteration:
            break
