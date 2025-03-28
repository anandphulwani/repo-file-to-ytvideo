from os import path
import ffmpeg
import subprocess
from .content_type import ContentType


def create_ffmpeg_process(output_dir, config, segment_idx, content_type):
    content_output_path = None
    if content_type == ContentType.PREMETADATA:
        content_output_path = path.join(output_dir, 'pre_metadata.mp4')
    elif content_type == ContentType.METADATA:
        content_output_path = path.join(output_dir, f'metadata.mp4')
    elif content_type == ContentType.DATACONTENT:
        content_output_path = path.join(output_dir, f'content_part{segment_idx:02d}.mp4')
    
    ffmpeg_input_framerate = f'{config['output_fps']}/{config['total_frames_repetition'][content_type.value]}' if config["use_same_bgr_frame_for_repetetion"] else f'{config["output_fps"]}'
    
    preset_dict = { 1: 'veryslow', 2: 'slower', 3: 'slow', 4: 'medium', 5: 'fast', 6: 'faster', 7: 'veryfast', 8: 'superfast', 9: 'ultrafast'}
    preset = preset_dict.get(config['encoding_speed'], "medium")
    
    return (ffmpeg.input('pipe:',
                         framerate=ffmpeg_input_framerate,
                         format='rawvideo',
                         pix_fmt='bgr24',
                         s=f'{config["frame_width"]}x{config["frame_height"]}')
            #
            .output(content_output_path,
                    vcodec='libx264',
                    pix_fmt='yuv420p',
                    b='2000k',
                    crf=23,
                    preset=preset,
                    tune='zerolatency',
                    bufsize='1024k',
                    r=f'{config["output_fps"]}')
            #
            .global_args('-loglevel', 'error')
            #
            .run_async(pipe_stdin=True, pipe_stdout=subprocess.DEVNULL, pipe_stderr=subprocess.DEVNULL))


def close_ffmpeg_process(ffmpeg_process, content_type, segment_idx=None):
    if ffmpeg_process:
        ffmpeg_process.stdin.close()
        ffmpeg_process.wait()
        print(
            f"{'PREMETADATA' if content_type == ContentType.PREMETADATA else 'METADATA' if content_type == ContentType.METADATA else f'DATACONTENT segment {segment_idx}'} completed"
        )
    return ffmpeg_process
