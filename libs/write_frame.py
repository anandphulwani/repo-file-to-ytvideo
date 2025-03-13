def write_frame(stream, frame_to_write):
    """Write a frame multiple times as specified in the config."""
    stream.stdin.write(frame_to_write)
    stream.stdin.flush()


def write_mulitple_frames(stream, frames_to_write):
    """Write multiple frames to the pipe."""
    for frame in frames_to_write:
        stream.stdin.write(frame)
    stream.stdin.flush()
