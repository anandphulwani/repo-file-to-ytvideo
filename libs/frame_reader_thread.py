#############################################################################
# A THREAD that continuously reads frames from cap.read()
#    and pushes them into a multiprocessing-safe queue.
#############################################################################
def frame_reader_thread(cap, frame_queue, stop_event, start_index, end_index, frame_step):
    """
    Reads frames from OpenCV in a dedicated thread.
    Only enqueues frames whose index is in [start_index..end_index]
    and (index - start_index) % frame_step == 0.
    Once done, enqueues None to signal end.
    """
    frame_index = 0
    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            break

        # Only push frames that we actually want to decode:
        if frame_index >= start_index and frame_index <= end_index:
            if (frame_index - start_index) % frame_step == 0:
                # Put (frame_index, frame) in the queue
                frame_queue.put((frame_index, frame))

        frame_index += 1
        # If we have already passed end_index, we can break
        if frame_index > end_index:
            # print("Breaking because frame_index set end_index to", end_index)
            break

    # Signal that we're done reading frames:
    frame_queue.put(None)
