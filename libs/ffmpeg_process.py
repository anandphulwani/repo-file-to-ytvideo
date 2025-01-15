from os import path
import ffmpeg


def create_ffmpeg_process(output_dir, config, segment_idx, is_metadata):
    content_output_path = None
    if is_metadata:
        content_output_path = path.join(output_dir, 'metadata.ts')
    else:
        content_output_path = path.join(output_dir, f'content_part{segment_idx:02d}.ts')
    return (ffmpeg.input('pipe:',
                         framerate=config['output_fps'],
                         format='rawvideo',
                         pix_fmt='bgr24',
                         s=f'{config["frame_width"]}x{config["frame_height"]}').output(
                             content_output_path,
                             f='mpegts',
                             vcodec='libx264',
                             pix_fmt='yuv420p',
                             b='2000k',
                             crf=23,
                             bufsize='1024k').global_args('-loglevel',
                                                          'error').run_async(pipe_stdin=True))


def close_ffmpeg_process(ffmpeg_process, segment_index):
    if ffmpeg_process:
        ffmpeg_process.stdin.close()
        ffmpeg_process.wait()
        print(f"Segment {segment_index} completed.")
