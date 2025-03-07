import base64
import binascii
from tqdm import tqdm
import os
import sys
import math
import hashlib
from .detect_base_from_json import get_length_from_base
from .content_type import ContentType
from .metadata_utils import get_metadata, get_pre_metadata


class FileToEncodedData:

    def __init__(self, config, file_path, debug=False):
        if not os.path.exists(file_path):
            print("The specified file does not exist.")
            sys.exit(1)
        self.content_type = ContentType.DATACONTENT
        self.config = config
        self.file_path = file_path
        self.debug = debug
        self.sha1 = hashlib.sha1()
        self.total_baseN_length = 0
        self.format_string = config["encoding_format_string"]
        self.usable_databoxes_in_frame = config['usable_databoxes_in_frame']
        self.stream_encoded_file = open(f"{file_path}_encoded_stream.txt", "w") if debug else None
        self.file_size = os.path.getsize(file_path)
        self.file = open(file_path, "rb", buffering=100 * 1024 * 1024)
        self.pbar = tqdm(total=self.file_size, desc="Processing File", unit="B", unit_scale=True)
        self.buffer = ''
        self.pre_metadata = None
        self.metadata = None
        self.current_metadata_key = None
        self.metadata_rscodec_value = None
        self.metadata_item_frame_count = None
        self.metadata_or_pre_metadata_read_position = None
        self.metadata_frames_and_details = {}

    def create_pre_metadata(self):
        self.buffer = ''
        self.pre_metadata = self.get_pre_metadata()
        self.metadata_or_pre_metadata_read_position = 0
        self.pbar = tqdm(total=len(self.pre_metadata), desc="Processing Pre Metadata", unit="B", unit_scale=True)

    def create_metadata(self):
        self.buffer = ''
        self.metadata_or_pre_metadata_read_position = 0
        self.metadata_item_frame_count = 0
        # Prepare for metadata iternation
        self.metadata = self.get_metadata()
        self.metadata_keys = iter(self.metadata.keys())  # Create an iterator over metadata items
        self.current_metadata_key = next(self.metadata_keys, None)
        self.metadata_or_pre_metadata_read_position = 0
        self.pbar = tqdm(total=len(self.metadata[self.current_metadata_key]), desc="Processing Metadata", unit="B", unit_scale=True)

    def __iter__(self):
        return self

    def __next__(self):
        # If metadata iteration is complete, move to the next encoding type
        if self.content_type == ContentType.METADATA and self.metadata_or_pre_metadata_read_position >= len(self.metadata[self.current_metadata_key]):
            self.metadata_frames_and_details[self.current_metadata_key] = [
                self.metadata_item_frame_count,
                len(self.metadata[self.current_metadata_key]),
                self.metadata_rscodec_value if self.current_metadata_key == "reed_solomon" else None,
            ]

            self.metadata_item_frame_count = 0
            self.current_metadata_key = next(self.metadata_keys, None)
            if self.current_metadata_key is not None:
                # Reset metadata read position and buffer for the new metadata type
                self.metadata_or_pre_metadata_read_position = 0
                self.buffer = ''
                self.pbar = tqdm(total=len(self.metadata[self.current_metadata_key]),
                                 desc=f"Processing {self.current_metadata_key}",
                                 unit="B",
                                 unit_scale=True)

        # Determine how many baseN data to read
        needed_baseN_data = self.usable_databoxes_in_frame[self.content_type.value] - len(self.buffer)
        if needed_baseN_data > 0:
            bytes_to_read = max(math.ceil((needed_baseN_data * self.config["encoding_bits_per_value"]) / 8), 10 * 1024 * 1024)  # Read at least 10 MB
            file_chunk = b''

            if self.content_type == ContentType.PREMETADATA or self.content_type == ContentType.METADATA:
                # Read metadata/pre-metadata, extract chunk and convert to bytes
                if self.content_type == ContentType.PREMETADATA or self.current_metadata_key is not None:
                    metadata_or_premetadata_str = self.metadata[
                        self.current_metadata_key] if self.content_type == ContentType.METADATA else self.pre_metadata

                    start_pos = self.metadata_or_pre_metadata_read_position
                    end_pos = min(start_pos + bytes_to_read, len(metadata_or_premetadata_str))

                    file_chunk = metadata_or_premetadata_str[start_pos:end_pos].encode('utf-8')
                    self.metadata_or_pre_metadata_read_position += (end_pos - start_pos)
            else:
                file_chunk = self.file.read(bytes_to_read)

            if not file_chunk and len(self.buffer) == 0:
                self.pbar.close()
                if self.content_type == ContentType.PREMETADATA:
                    self.content_type = None
                if self.content_type == ContentType.METADATA:
                    self.create_pre_metadata()
                    self.content_type = ContentType.PREMETADATA
                elif self.content_type == ContentType.DATACONTENT:
                    self.stream_encoded_file.close() if self.stream_encoded_file else None
                    self.file.close()
                    self.create_metadata()
                    self.content_type = ContentType.METADATA
                raise StopIteration

            self.sha1.update(file_chunk)

            # Convert file_chunk to baseN data (either C-based or fallback)
            if self.config["encoding_base"] == 16:  # Hex encoding
                chunk_baseN_data = binascii.hexlify(file_chunk).decode('ascii') if file_chunk else ''
            elif self.config["encoding_base"] == 64:  # Base64 encoding
                chunk_baseN_data = base64.b64encode(file_chunk).decode('ascii') if file_chunk else ''
            else:
                # Fallback to old method if the encoding is custom
                chunk_baseN_data = "".join(f"{byte:{self.format_string}}" for byte in file_chunk)

            self.total_baseN_length += len(chunk_baseN_data)

            # Add new baseN data to buffer
            self.buffer += chunk_baseN_data

        if len(self.buffer) >= self.usable_databoxes_in_frame[self.content_type.value]:
            data_to_yield = self.buffer[:self.usable_databoxes_in_frame[self.content_type.value]]
            self.buffer = self.buffer[self.usable_databoxes_in_frame[self.content_type.value]:]
        else:
            data_to_yield = self.buffer
            self.buffer = ''

        # Update progress and metadata
        self.pbar.update(get_length_from_base(len(data_to_yield), self.config["encoding_bits_per_value"]))

        self.stream_encoded_file.write(data_to_yield) if self.stream_encoded_file and self.content_type == ContentType.DATACONTENT else None
        self.metadata_item_frame_count = self.metadata_item_frame_count + 1 if self.content_type == ContentType.METADATA else 0
        return (self.content_type, data_to_yield)

    def get_metadata(self):
        metadata_dict, self.metadata_rscodec_value = get_metadata(self.config, self.file_path, self.file_size, self.total_baseN_length,
                                                                  self.sha1.hexdigest())
        return metadata_dict

    def get_pre_metadata(self):
        return get_pre_metadata(self.config, self.metadata_frames_and_details)
