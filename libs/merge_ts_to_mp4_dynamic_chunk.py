import os
import ffmpeg
import sys
import threading
import psutil
from tqdm import tqdm


def extract_frame(ts_file, output_dir, frame_number=3):
    """
    Extract a specific frame from a .ts file and save it as an image.

    Parameters:
    - ts_file (str): Path to the input .ts file.
    - output_dir (str): Directory to save the extracted frame.
    - frame_number (int): The frame number to extract (default is 3).
    """
    # Generate the output frame file path
    frame_output_path = os.path.join(output_dir, f"frame{frame_number:03d}_{os.path.basename(ts_file)}.jpg")

    try:
        # Use the 'select' filter for sequential frame extraction
        ffmpeg.input(ts_file).output(
            frame_output_path,
            vf=f"select=gte(n\\,{frame_number - 1})",  # Adjust for 0-based indexing
            vsync="vfr",
            vframes=1).run(overwrite_output=True)
        print(f"Extracted frame {frame_number} from {ts_file} to {frame_output_path}")
    except ffmpeg.Error as e:
        print(f"Failed to extract frame from {ts_file}: {e.stderr.decode()}")


def merge_ts_to_mp4_dynamic_chunk(
        input_directory,
        final_output_path,
        frame_output_dir,
        memory_fraction=0.2,  # Fraction of available memory to use for chunk size
        base_chunk_size=1024 * 1024,  # Base chunk size in bytes (1 MB)
        debug=False):
    """
    Concatenates .ts files in the specified directory into a single output.mp4 file.
    Deletes each source .ts file immediately after it has been processed to save disk space.
    The concatenation and conversion to MP4 are performed on-the-fly by streaming data to FFmpeg's stdin.
    The chunk size is dynamically adjusted based on the system's available memory.

    Parameters:
    - input_directory (str): Path to the directory containing .ts files.
    - final_output_path (str): Path for the final MP4 output file.
    - memory_fraction (float): Fraction of available memory to use for chunk size.
    - base_chunk_size (int): Base chunk size in bytes.
    """

    # Ensure required libraries are installed
    try:
        import psutil
    except ImportError:
        print("psutil library is not installed. Please install it using 'pip install psutil'")
        return

    try:
        from tqdm import tqdm
    except ImportError:
        print("tqdm library is not installed. Please install it using 'pip install tqdm'")
        return

    # Helper function to sort the .ts files in the desired order
    def sort_ts_files(ts_files):

        def sort_key(x):
            filename = os.path.basename(x)
            if 'pre_metadata.ts' in filename:
                return (0, '')
            if 'metadata.ts' in filename:
                return (1, '')
            elif 'delimiter.ts' in filename:
                return (2, '')
            else:
                # Extract the numeric part from content_partXX.ts
                digits = ''.join(filter(str.isdigit, filename))
                return (2, int(digits) if digits else 0)

        return sorted(ts_files, key=sort_key)

    # Calculate dynamic chunk size based on available memory
    def calculate_chunk_size():
        mem = psutil.virtual_memory()
        available_mem = mem.available
        chunk_size = int(available_mem * memory_fraction)
        # Clamp the chunk size between base_chunk_size and 10 MB
        chunk_size = max(base_chunk_size, min(chunk_size, 10 * 1024 * 1024))
        return chunk_size

    # Gather and sort .ts files
    ts_files = [os.path.join(input_directory, f) for f in os.listdir(input_directory) if f.endswith('.ts')]

    if not ts_files:
        print("No .ts files found in the specified directory.")
        return

    ts_files_sorted = sort_ts_files(ts_files)
    total_files = len(ts_files_sorted)
    print(f"Found {total_files} .ts files to process.")

    # Calculate chunk size
    chunk_size = calculate_chunk_size()
    print(f"Using chunk size: {chunk_size / (1024 * 1024):.2f} MB")

    # Start FFmpeg process with stdin as pipe
    try:
        process = (
            ffmpeg.input('pipe:0', format='mpegts')  # Specify format if necessary
            .output(final_output_path, format='mp4', vcodec='libx264', acodec='aac', strict='experimental',
                    movflags='faststart').overwrite_output().run_async(pipe_stdin=True, pipe_stdout=True, pipe_stderr=True))
    except ffmpeg.Error as e:
        print(f"Failed to start FFmpeg: {e.stderr.decode()}")
        return

    # Function to read FFmpeg's stderr and print it (optional)
    def read_ffmpeg_stderr(pipe):
        for line in iter(pipe.readline, b''):
            print(line.decode().strip())
        pipe.close()

    # Start a thread to read FFmpeg's stderr
    stderr_thread = threading.Thread(target=read_ffmpeg_stderr, args=(process.stderr, ))
    stderr_thread.start()

    if debug:
        if not frame_output_dir:
            print("'frame_output_dir' is not specified. Please specify it.")
            return
        os.makedirs(frame_output_dir, exist_ok=True)

    try:
        with tqdm(total=total_files, desc="Processing .ts files", unit="file") as pbar:
            for ts_file in ts_files_sorted:
                try:
                    print(f"Processing and appending {ts_file}...")
                    if debug:
                        extract_frame(ts_file, frame_output_dir)  # Extract frame before appending
                    with open(ts_file, 'rb') as infile:
                        while True:
                            data = infile.read(chunk_size)
                            if not data:
                                break
                            process.stdin.write(data)
                    print(f"Successfully appended {ts_file}. Deleting the source file...")
                    os.remove(ts_file)
                except Exception as e:
                    print(f"Error processing {ts_file}: {e}")
                    # Depending on requirements, decide to continue or halt
                    continue
                pbar.update(1)
    except Exception as e:
        print(f"Error writing to FFmpeg's stdin: {e}")
    finally:
        # Close FFmpeg's stdin to signal that no more data will be sent
        process.stdin.close()

    # Wait for FFmpeg to finish processing
    process.wait()
    stderr_thread.join()

    # Delete the input directory if it's empty
    if not os.listdir(input_directory):
        os.rmdir(input_directory)

    # Check FFmpeg's exit code
    if process.returncode != 0:
        print(f"FFmpeg exited with error code {process.returncode}. Check the stderr for details.")
    else:
        print(f"FFmpeg conversion complete. Output saved to {final_output_path}.")
