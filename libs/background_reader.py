import cv2
import queue


def background_reader(cap, frame_queue, stop_event, frame_start, frame_step):
    """
    Continuously reads frames from the given VideoCapture 'cap' and
    pushes them into 'frame_queue' (bounded to 'max_frames'). The 'stop_event'
    is used to stop reading before we exhaust the video if needed.
    """
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_start)  # Set the initial frame position
    frame_idx = frame_start
    ret, frame = None, None
    while not stop_event.is_set():
        try:
            if frame is None:
                ret, frame = cap.read()
            if not ret:
                frame_queue.put(None, timeout=0.5)
                break
            frame_queue.put(frame, timeout=0.5)

            for _ in range(frame_step - 1):
                ret_skip, _ = cap.read()
                if not ret_skip:
                    frame_queue.put(None)
                    return

            # Skip 'frame_step' frames
            frame_idx += frame_step

            ret, frame = None, None
        except queue.Full:
            pass
