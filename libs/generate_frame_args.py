def generate_frame_args(cap, config, frame_data_iter, encoding_color_map):
    frame_index = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        try:
            content_type, frame_data = next(frame_data_iter)
            if frame_data is None:
                break
            yield (frame, config, encoding_color_map, frame_data, frame_index, content_type)
            frame_index += 1
        except StopIteration:
            break
