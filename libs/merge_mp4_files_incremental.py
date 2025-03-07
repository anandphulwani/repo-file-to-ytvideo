import os
import ffmpeg


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


def merge_mp4_files_incremental(input_directory, final_output_path, frame_output_dir=None, debug=False):
    """
    Incrementally concatenates .mp4 files in the specified directory into a single MP4 file
    using pairwise merges (ffmpeg concat demuxer) so that each input file can be removed
    once it is merged, thus saving disk space.

    If 'debug' is True, it optionally extracts the 3rd frame of each MP4 before merging.

    Parameters:
    - input_directory (str): Path to the directory containing .mp4 files.
    - final_output_path (str): Path for the final MP4 output file.
    - frame_output_dir (str): Directory to save debug frames (only used if debug=True).
    - debug (bool): Whether to extract frames for debugging.
    """

    # Gather all .mp4 files
    mp4_files = [os.path.join(input_directory, f) for f in os.listdir(input_directory) if f.endswith(".mp4")]

    if not mp4_files:
        print("No .mp4 files found in the specified directory.")
        return

    # Custom sorting logic
    def sort_mp4_files(files):

        def sort_key(x):
            filename = os.path.basename(x)
            if "pre_metadata" in filename:
                return (0, "")
            if "metadata" in filename:
                return (1, "")
            elif "delimiter" in filename:
                return (2, "")
            else:
                # Extract the numeric part from content_partXX.mp4
                digits = "".join(filter(str.isdigit, filename))
                return (2, int(digits) if digits else 0)

        return sorted(files, key=sort_key)

    mp4_files_sorted = sort_mp4_files(mp4_files)
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

    # If there's only 1 file, just rename or copy it.
    if len(mp4_files_sorted) == 1:
        single_file = mp4_files_sorted[0]
        print(f"Only one file found. Moving {single_file} to {final_output_path}...")
        os.rename(single_file, final_output_path)
        return

    # Otherwise, we'll do incremental merges in a temp folder or using a temp filename
    # We'll keep track of a "current_merged.mp4" that grows in each iteration.
    temp_merged_path = os.path.join(input_directory, "current_merged.mp4")

    # Step 1: Move or copy the first file to become our initial "merged" file
    first_file = mp4_files_sorted[0]
    print(f"Initializing merge with first file: {first_file}")
    os.rename(first_file, temp_merged_path)  # or copy if you prefer
    print(f"Renamed {first_file} -> {temp_merged_path}")
    # Remove the first file from the list
    merged_count = 1

    # Pairwise merge each remaining file
    for mp4_file in mp4_files_sorted[1:]:
        # Create a concat list for the current_merged + next file
        concat_list_path = os.path.join(input_directory, "concat_list.txt")
        with open(concat_list_path, "w", encoding="utf-8") as f:
            # Write the existing merged
            f.write(f"file '{os.path.abspath(temp_merged_path)}'\n")
            # Write the next file to merge
            f.write(f"file '{os.path.abspath(mp4_file)}'\n")

        merged_output_path = os.path.join(input_directory, "merged_temp_output.mp4")

        print(f"Merging file #{merged_count + 1} of {total_files}: {mp4_file}\n"
              f"  - Intermediate output -> {merged_output_path}")

        try:
            (ffmpeg.input(concat_list_path, format="concat", safe=0).output(merged_output_path, c="copy").overwrite_output().run())
        except ffmpeg.Error as e:
            print(f"FFmpeg merge failed while processing {mp4_file}: {e.stderr.decode()}")
            # Cleanup the concat list
            if os.path.exists(concat_list_path):
                os.remove(concat_list_path)
            return

        # Remove the old concat list
        os.remove(concat_list_path)

        # Now remove the old merged file and the newly-merged-in file
        if os.path.exists(temp_merged_path):
            os.remove(temp_merged_path)
        if os.path.exists(mp4_file):
            os.remove(mp4_file)

        # Rename merged_temp_output to our "current_merged"
        os.rename(merged_output_path, temp_merged_path)
        merged_count += 1
        print(f"  - Successfully merged, removed old pieces.\n"
              f"  - Updated 'current_merged.mp4' now has {merged_count} file(s) inside.\n")

    # Finally, rename or move the final merged to the user-specified output
    print(f"Finished incremental merge of {merged_count} files.")
    print(f"Moving final merged from {temp_merged_path} to {final_output_path}...")
    if os.path.exists(final_output_path):
        os.remove(final_output_path)  # Overwrite if needed
    os.rename(temp_merged_path, final_output_path)

    # Optionally remove the input directory if it's empty now
    if not os.listdir(input_directory):
        os.rmdir(input_directory)

