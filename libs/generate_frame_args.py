def generate_frame_args(frame_queue, config, frame_data_iter, encoding_color_map, debug, start_index=0, frame_step=1):
    frame_index = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        try:
            if frame_index >= start_index and ((frame_index - start_index) % frame_step) == 0:
                content_type, frame_data = next(frame_data_iter)
                if frame_data is None:
                    break
                yield (frame, config, encoding_color_map, frame_data, frame_index, content_type, debug)
        except StopIteration:
            break
        frame_index += 1
