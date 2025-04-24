def writer_process(write_queue, file_path):
    with open(file_path, 'wb') as binary_output_file:
        while True:
            item = write_queue.get(True)  # This will block until an item is available
            if item is None:  # Check for the termination signal
                break
            frame_index, data = item
            try:
                binary_output_file.write(data)
            except Exception as e:
                print(f"Error writing data: {e} on frame_index: {frame_index}")
                break  # Exit on error
