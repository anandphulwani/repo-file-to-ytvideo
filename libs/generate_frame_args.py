def generate_frame_args(frame_queue, config, frame_data_iter, encoding_color_map, debug):
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        try:
                content_type, frame_data = next(frame_data_iter)
                if frame_data is None:
                    break
                yield (frame, config, encoding_color_map, frame_data, None, content_type, debug)
        except StopIteration:
            break

