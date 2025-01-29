import os


def get_available_filename_to_decode(config, filename):
    data_folder_decoded = config['data_folder_decoded']
    original_filepath = os.path.join(data_folder_decoded, filename)

    if not os.path.exists(original_filepath):
        return filename

    decoded_filename = f"decoded_{filename}"
    decoded_filepath = os.path.join(data_folder_decoded, decoded_filename)
    if not os.path.exists(decoded_filepath):
        return decoded_filename

    count = 1
    while True:
        incremented_filename = f"decoded({count:02})_{filename}"
        incremented_filepath = os.path.join(data_folder_decoded, incremented_filename)
        if not os.path.exists(incremented_filepath):
            return incremented_filename
        count += 1
