import queue


def background_reader(cap, frame_queue, stop_event):
    """
    Continuously reads frames from the given VideoCapture 'cap' and
    pushes them into 'frame_queue' (bounded to 'max_frames'). The 'stop_event'
    is used to stop reading before we exhaust the video if needed.
    """
    ret, frame = None, None
    while not stop_event.is_set():
        try:
            if frame is None:
                ret, frame = cap.read()
            if not ret:
                frame_queue.put(None, timeout=0.5)
                break
            frame_queue.put(frame, timeout=0.5)
            ret, frame = None, None
        except queue.Full:
            pass
