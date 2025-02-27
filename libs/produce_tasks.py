#############################################################################
# A GENERATOR that yields tasks to the pool from the queue.
#############################################################################
def produce_tasks(frame_queue, stop_event, config_params, frame_step, total_baseN_length, num_frames, metadata_frames):
    """
    Takes items from the frame_queue (pushed by the reader thread),
    and yields them in the format that process_frame_optimized(...) expects:
       (config_params, frame_bgr, frame_index, frame_step, 
        total_baseN_length, num_frames, metadata_frames)
    """
    while not stop_event.is_set():
        item = frame_queue.get()
        if item is None:
            # End of stream
            break
        (frame_index, frame_bgr) = item

        # Build the tuple for your worker function:
        yield (config_params, frame_bgr, frame_index, frame_step, total_baseN_length, num_frames, metadata_frames)
