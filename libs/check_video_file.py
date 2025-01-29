import sys
import cv2


def check_video_file(config, cap):
    if not cap.isOpened():
        raise IOError("Error opening video stream or file")
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if config['frame_width'] != frame_width or config['frame_height'] != frame_height:
        print(
            f"Config's frame dimensions ({config['frame_width']}x{config['frame_height']}) do not match video dimensions ({frame_width}x{frame_height})."
        )
        sys.exit(1)
