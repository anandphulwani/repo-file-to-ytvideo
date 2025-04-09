from .shared_buffer import SharedFrameBuffer
import numpy as np


#############################################################################
# A GENERATOR that yields tasks to the pool from the shared memory queue.
#############################################################################
def produce_tasks(frame_queue, stop_event, config_params, content_type, frame_step, total_baseN_length, num_frames, metadata_frames,
                  convert_return_output_data):
    """
    Takes shared memory descriptors from the frame_queue (pushed by the reader thread),
    attaches to them, and yields in the format that process_frame_optimized(...) expects:
       (config_params, content_type, frame_to_decode, frame_index, frame_step, 
        total_baseN_length, num_frames, metadata_frames)
    """
    while not stop_event.is_set():
        item = frame_queue.get()
        if item is None:
            # End of stream
            break

        # Build the tuple for your worker function:
        frame_index, shm_name, shape, dtype_str = item
        shape = tuple(shape)  # in case it's a list
        dtype = np.dtype(dtype_str)

        # Attach to shared memory
        sb = SharedFrameBuffer(name=shm_name, shape=shape, dtype=dtype, create=False)
        frame_to_decode = sb.array

        # Yield the task
        yield (config_params, content_type, frame_to_decode, frame_index, frame_step, total_baseN_length, num_frames, metadata_frames,
               convert_return_output_data)

        # Detach from the shared memory block (do not unlink!)
        sb.close()
