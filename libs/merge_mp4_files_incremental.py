import os
import ffmpeg
import threading
import time
from tqdm import tqdm  # make sure tqdm is installed: pip install tqdm


def extract_frame(mp4_file, output_dir, frame_number=3):
    """
    Extract a specific frame from an MP4 file and save it as an image.

    Parameters:
    - mp4_file (str): Path to the input MP4 file.
    - output_dir (str): Directory to save the extracted frame.
    - frame_number (int): The frame number to extract (default is 3).
    """
    # Generate the output frame file path
    frame_output_path = os.path.join(output_dir, f"frame{frame_number:03d}_{os.path.basename(mp4_file)}.jpg")

    try:
        (ffmpeg.input(mp4_file).filter_("select", f"gte(n,{frame_number - 1})")  # 0-based indexing
         .output(frame_output_path, vframes=1, vsync="vfr").overwrite_output().run())
        print(f"Extracted frame {frame_number} from {mp4_file} to {frame_output_path}")
    except ffmpeg.Error as e:
        print(f"Failed to extract frame from {mp4_file}: {e.stderr.decode()}")


def get_duration(mp4_file):
    """Return the duration of an MP4 file in seconds using ffmpeg.probe."""
    try:
        probe = ffmpeg.probe(mp4_file)
        duration = float(probe['format']['duration'])
        return duration
    except Exception as e:
        print(f"Error getting duration of {mp4_file}: {e}")
        return 0


def delete_file_async(file_path):
    """Delete a file in a separate thread."""

    def delete_file():
        try:
            os.remove(file_path)
            print(f"Deleted source file: {file_path}")
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")

    thread = threading.Thread(target=delete_file)
    thread.start()
    return thread


def merge_mp4_files_incremental(input_directory, final_output_path, frame_output_dir=None, debug=False):
    """
    Merges all .mp4 files at once using the concat demuxer.
    While merging, it monitors ffmpeg's progress and, as soon as the output
    has passed the duration of a source file plus an additional 10-second buffer,
    deletes that file in another thread.
    Additionally, it prints the merge progress using tqdm (with integer seconds)
    and shows ffmpeg's stderr output.
    """
    # 1. Gather and sort files (using custom sort logic)
    mp4_files = [os.path.join(input_directory, f) for f in os.listdir(input_directory) if f.endswith(".mp4")]
    if not mp4_files:
        print("No .mp4 files found in the specified directory.")
        return

    def sort_key(x):
        filename = os.path.basename(x)
        if "pre_metadata" in filename:
            return (0, "")
        if "metadata" in filename:
            return (1, "")
        elif "delimiter" in filename:
            return (2, "")
        else:
            digits = "".join(filter(str.isdigit, filename))
            return (2, int(digits) if digits else 0)

    mp4_files_sorted = sorted(mp4_files, key=sort_key)
    total_files = len(mp4_files_sorted)
    print(f"Found {total_files} .mp4 files to process.")

    # Debug frame extraction (before we start removing them)
    if debug:
        if not frame_output_dir:
            print("'frame_output_dir' is not specified. Please specify it.")
            return
        os.makedirs(frame_output_dir, exist_ok=True)
        for mp4_file in mp4_files_sorted:
            extract_frame(mp4_file, frame_output_dir, frame_number=3)

    # 3. Create a concat list file for ffmpeg
    concat_list_path = os.path.join(input_directory, "concat_list.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for mp4_file in mp4_files_sorted:
            f.write(f"file '{os.path.abspath(mp4_file)}'\n")

    # 4. Compute cumulative durations for each file (in seconds)
    cumulative_durations = []  # List of tuples: (file, cumulative_end_time)
    cumulative = 0
    for file in mp4_files_sorted:
        duration = get_duration(file)
        cumulative += duration
        cumulative_durations.append((file, cumulative))
    print("Cumulative durations (in seconds):")
    for file, end_time in cumulative_durations:
        print(f"  {os.path.basename(file)} -> {int(end_time)}")

    # Total duration for progress bar (final merged video's duration) as an integer
    total_duration = int(cumulative_durations[-1][1]) if cumulative_durations else 0

    # 5. Start the ffmpeg merge process with progress output
    process = (ffmpeg.input(concat_list_path, format="concat", safe=0).output(final_output_path, c="copy",
                                                                              progress="pipe:1").overwrite_output().run_async(pipe_stdout=True,
                                                                                                                              pipe_stderr=True))

    deletion_threads = []
    deleted_files = set()
    buffer_time = 10  # 10-second buffer as integer

    def monitor_progress():
        """Read ffmpeg's progress, update tqdm with integer seconds, and delete files when done."""
        current_progress_int = 0
        pbar = tqdm(total=total_duration, desc="Merging progress", unit="sec")
        while True:
            line = process.stdout.readline()
            if not line:
                break
            try:
                decoded = line.decode('utf-8').strip()
            except Exception:
                continue

            if decoded.startswith("out_time_ms="):
                try:
                    out_time_ms = int(decoded.split("=")[1])
                    new_time = out_time_ms / 1e6  # convert microseconds to seconds
                    new_time_int = int(new_time)
                    if new_time_int > current_progress_int:
                        pbar.update(new_time_int - current_progress_int)
                        current_progress_int = new_time_int

                    # Check for deletion condition for all files except the last one
                    for file, cum_duration in cumulative_durations:
                        if file == mp4_files_sorted[-1]:
                            continue  # Skip deletion for the last file here
                        if file not in deleted_files and new_time_int >= (int(cum_duration) + buffer_time):
                            print(f"\nCurrent merged time {new_time_int} sec exceeds end time of {os.path.basename(file)} "
                                  f"({int(cum_duration)} sec) plus a {buffer_time}-sec buffer. Deleting file.")
                            t = delete_file_async(file)
                            deletion_threads.append(t)
                            deleted_files.add(file)
                except Exception as e:
                    print(f"Error processing progress line: {decoded} - {e}")

            if decoded.startswith("progress=") and decoded.split("=")[1] == "end":
                break
        pbar.close()

    def monitor_stderr():
        """Read and print ffmpeg's stderr output."""
        while True:
            line = process.stderr.readline()
            if not line:
                break
            try:
                decoded = line.decode('utf-8').strip()
            except Exception:
                continue
            print(f"FFmpeg stderr: {decoded}")

    # Start the progress and stderr monitors in separate threads
    monitor_thread = threading.Thread(target=monitor_progress)
    stderr_thread = threading.Thread(target=monitor_stderr)
    monitor_thread.start()
    stderr_thread.start()

    # Wait for ffmpeg to finish merging
    process.wait()
    monitor_thread.join()
    stderr_thread.join()

    # Delete the last file if it hasn't been deleted already
    last_file = mp4_files_sorted[-1]
    if last_file not in deleted_files:
        print(f"Deleting last file: {os.path.basename(last_file)} after merge completion.")
        t = delete_file_async(last_file)
        deletion_threads.append(t)
        deleted_files.add(last_file)

    # Ensure all deletion threads have completed
    for t in deletion_threads:
        t.join()

    # Clean up the concat list file
    if os.path.exists(concat_list_path):
        os.remove(concat_list_path)

    if not os.listdir(input_directory):
        os.rmdir(input_directory)

    print("Merging complete and source files deleted as they were processed.")
