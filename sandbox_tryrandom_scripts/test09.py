import ffmpeg
import numpy as np


def generate_frame(width, height):
    """Generates a random frame."""
    return np.random.randint(0, 255, (height, width, 3), dtype=np.uint8).tobytes()


def process_frames(output_filepath, num_frames=30000, width=640, height=480):
    """Generates frames and writes them to an output file using FFmpeg."""
    # Setup FFmpeg process for asynchronous writing
    ffmpeg_process = (ffmpeg.input('pipe:',
                                   framerate='30',
                                   format='rawvideo',
                                   pix_fmt='bgr24',
                                   s=f'{width}x{height}').output(
                                       output_filepath,
                                       vcodec='h264',
                                       pix_fmt='nv21',
                                       **{
                                           'b:v': '2000k'
                                       }).overwrite_output().run_async(pipe_stdin=True))

    # Generate and write frames
    for i in range(num_frames):
        print(i)
        frame = generate_frame(width, height)
        ffmpeg_process.stdin.write(frame)

    # Finalize everything
    ffmpeg_process.stdin.close()
    ffmpeg_process.wait()


# Example usage
if __name__ == "__main__":
    output_video = 'output.mp4'  # Change to your desired output video path
    process_frames(output_video)
