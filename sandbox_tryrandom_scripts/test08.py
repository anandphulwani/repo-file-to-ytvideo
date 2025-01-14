import subprocess
import numpy as np
import time


def generate_frame():
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8).tobytes()


command = [
    # 'ffmpeg',
    # '-y',
    # '-f', 'rawvideo',
    # '-vcodec', 'rawvideo',
    # '-s', '640x480',
    # '-pix_fmt', 'nv21',
    # '-r', '30',
    # '-i', '-',
    # '-an',
    # '-vcodec', 'h264',
    # '-b:v', '2000k',
    # 'output.mp4'
    'ffmpeg',
    '-y',
    '-f',
    'rawvideo',
    '-vcodec',
    'rawvideo',
    '-pix_fmt',
    'bgr24',
    '-s',
    '640x480',
    '-r',
    '30',
    '-i',
    '-',
    '-an',
    '-vcodec',
    'h264',
    '-pix_fmt',
    'nv21',
    '-b:v',
    '2000k',
    'output.mp4'
]

# ffmpeg
# .input('pipe:', framerate='30', format='rawvideo', pix_fmt='bgr24', s=f'{width}x{height}')
# .output(output_filepath, vcodec='h264', pix_fmt='nv21', **{'b:v': '2000k'})
# .overwrite_output()
# .run_async(pipe_stdin=True)

ffmpeg = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

try:
    for i in range(30000):
        print(i, end="")
        frame = generate_frame()
        print(' !!', end="")
        ffmpeg.stdin.write(frame)
        print(' Done', end="")
        ffmpeg.stdin.flush()
        print(' .')
        time.sleep(0.05)
except KeyboardInterrupt:
    print("Stopped manually")
except Exception as e:
    print("Error:", e)
finally:
    ffmpeg.stdin.close()
    # Read any errors from FFmpeg
    while True:
        line = ffmpeg.stderr.readline()
        if not line:
            break
        print("FFmpeg output:", line.decode())
    ffmpeg.wait()
    print("FFmpeg process finished")
