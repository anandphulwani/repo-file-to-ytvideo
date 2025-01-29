def write_frame_repeatedly(stream, frame_to_write, content_type, config):
    """Write a frame multiple times as specified in the config."""
    for _ in range(config['total_frames_repetition'][content_type.value]):
        stream.stdin.write(frame_to_write)
    stream.stdin.flush()
