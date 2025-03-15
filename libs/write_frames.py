def write_frames(stream, frames_to_write):
    """Write multiple frames to the pipe."""
    for frame in frames_to_write:
        stream.stdin.write(frame)
    stream.stdin.flush()
