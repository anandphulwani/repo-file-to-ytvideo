def write_frame(stream, frame_to_write):
    """Write a frame multiple times as specified in the config."""
    stream.stdin.write(frame_to_write)
    stream.stdin.flush()
