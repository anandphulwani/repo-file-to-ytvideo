from os import path
import ffmpeg
from .content_type import ContentType


def create_ffmpeg_process(output_dir, config, segment_idx, content_type):
    content_output_path = None
    if content_type == ContentType.PREMETADATA:
        content_output_path = path.join(output_dir, 'pre_metadata.ts')
    elif content_type == ContentType.METADATA:
        content_output_path = path.join(output_dir, f'metadata.ts')
    elif content_type == ContentType.DATACONTENT:
        content_output_path = path.join(output_dir, f'content_part{segment_idx:02d}.ts')
    return (ffmpeg.input('pipe:',
                         framerate=config['output_fps'],
                         format='rawvideo',
                         pix_fmt='bgr24',
                         s=f'{config["frame_width"]}x{config["frame_height"]}').output(content_output_path,
                                                                                       f='mpegts',
                                                                                       vcodec='libx264',
                                                                                       pix_fmt='yuv420p',
                                                                                       b='2000k',
                                                                                       crf=23,
                                                                                       bufsize='1024k').global_args(
                                                                                           '-loglevel', 'error').run_async(pipe_stdin=True))


def close_ffmpeg_process(ffmpeg_process, content_type, segment_idx=None):
    if ffmpeg_process:
        ffmpeg_process.stdin.close()
        ffmpeg_process.wait()
        print(
            f"{'PREMETADATA' if content_type == ContentType.PREMETADATA else 'METADATA' if content_type == ContentType.METADATA else f'DATACONTENT segment {segment_idx}'} completed"
        )
