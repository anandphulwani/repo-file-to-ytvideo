import base64
from tqdm import tqdm
import os
import sys
import math
import hashlib
import zfec
from .content_type import ContentType
from .rot13_rot5 import rot13_rot5
from reedsolo import RSCodec


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
        self.file = open(file_path, "rb")
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
        bytes_to_read = math.ceil((needed_baseN_data * self.config["encoding_bits_per_value"]) / 8)
        file_chunk = ''

        if self.content_type == ContentType.PREMETADATA or self.content_type == ContentType.METADATA:
            # Read metadata/pre-metadata, extract chunk and convert to bytes
            if self.content_type == ContentType.PREMETADATA or self.current_metadata_key is not None:
                metadata_or_premetadata_str = self.metadata[
                    self.current_metadata_key] if self.content_type == ContentType.METADATA else self.pre_metadata
                file_chunk = bytes(
                    int(metadata_or_premetadata_str[i:i + 8], 2)
                    for i in range(self.metadata_or_pre_metadata_read_position,
                                   min(self.metadata_or_pre_metadata_read_position + bytes_to_read * 8, len(metadata_or_premetadata_str)), 8))
                self.metadata_or_pre_metadata_read_position += bytes_to_read * 8
        else:
            file_chunk = self.file.read(bytes_to_read)

        if not file_chunk:
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

        # Update progress and metadata
        self.pbar.update(
            len(file_chunk * 8 if self.content_type == ContentType.METADATA or self.content_type == ContentType.PREMETADATA else file_chunk))
        self.sha1.update(file_chunk)

        # Convert file bytes to a baseN string
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

        self.stream_encoded_file.write(data_to_yield) if self.stream_encoded_file and self.content_type == ContentType.DATACONTENT else None
        self.metadata_item_frame_count = self.metadata_item_frame_count + 1 if self.content_type == ContentType.METADATA else 0
        return (self.content_type, data_to_yield)

    def get_metadata(self):
        """
        Returns the metadata.
        """
        main_delim = self.config["premetadata_metadata_main_delimiter"]
        sub_delim = self.config["premetadata_metadata_sub_delimiter"]

        metadata_items = {}
        # ------------------------------------------
        # STEP 1: Build the metadata WITHOUT length
        # ------------------------------------------
        temp_metadata = (f"{main_delim}METADATA"
                         f"{sub_delim}{os.path.basename(self.file_path)}"
                         f"{sub_delim}{self.file_size}"
                         f"{sub_delim}{self.total_baseN_length}"
                         f"{sub_delim}{self.sha1.hexdigest()}"
                         f"{main_delim}")

        # ------------------------------------------------
        # STEP 2: Simple checksum (e.g. sum of ASCII % 256)
        # ------------------------------------------------
        checksum_value = sum(ord(c) for c in temp_metadata) % 256
        # Append checksum for clarity
        metadata_with_checksum = f"{temp_metadata}|CHECKSUM:{checksum_value}|"

        # --------------------------------------------
        # STEP 3: Tripling results for redundancy
        # --------------------------------------------
        # Repeat metadata_with_checksum 3 times
        final_metadata = metadata_with_checksum * 3
        metadata_items["normal"] = final_metadata

        # -----------------------------------------
        # STEP 4: Apply Base64 encoding
        # -----------------------------------------
        base64_encoded = base64.b64encode(metadata_with_checksum.encode()).decode()
        metadata_items["base64"] = base64_encoded

        # -----------------------------------------
        # STEP 5: Apply ROT13 cipher
        # -----------------------------------------
        rot13_encoded = rot13_rot5(metadata_with_checksum)
        metadata_items["rot13"] = rot13_encoded

        # -------------------------------------------------
        # STEP 6: Convert to Reed-Solomon error correction
        # -------------------------------------------------
        self.metadata_rscodec_value = min(len(metadata_with_checksum), 255)
        reed_solomon_encoded = RSCodec(self.metadata_rscodec_value).encode(metadata_with_checksum.encode())
        reed_solomon_encoded = base64.b64encode(reed_solomon_encoded).decode('utf-8')
        metadata_items["reed_solomon"] = reed_solomon_encoded

        # -----------------------------
        # STEP 7: Apply Erasure Coding
        # -----------------------------
        zfec_k, zfec_m = 3, 5
        zfec_encoder = zfec.Encoder(zfec_k, zfec_m)
        block_size = -(-len(metadata_with_checksum.encode()) // zfec_k)  # Ceiling division
        blocks = [metadata_with_checksum.encode()[i * block_size:(i + 1) * block_size].ljust(block_size, b' ') for i in range(zfec_k)]
        zfec_encoded_text = zfec_encoder.encode(blocks)
        zfec_encoded_hex = "".join(fragment.hex() for fragment in zfec_encoded_text)
        metadata_items["zfec"] = zfec_encoded_hex

        return metadata_items

    def get_pre_metadata(self):
        """
        Returns the pre_metadata.
        """

        pre_metadata = ''
        main_delim = self.config["premetadata_metadata_main_delimiter"]
        sub_delim = self.config["premetadata_metadata_sub_delimiter"]
        length_of_digits_to_represent_size = self.config["length_of_digits_to_represent_size"]

        for key, value in self.metadata_frames_and_details.items():
            pre_metadata += f"{sub_delim}{key}" + f"{sub_delim}{value[0]}" + (f"{sub_delim}{value[2]}"
                                                                              if key == "reed_solomon" else "") + f"{sub_delim}{value[1]}"

        pre_metadata = main_delim + 'PREMETADATA' + pre_metadata + main_delim
        pre_metadata_len = len(main_delim) + length_of_digits_to_represent_size + len(main_delim) + len(pre_metadata)
        if len(str(pre_metadata_len)) > length_of_digits_to_represent_size:
            raise ValueError(
                f"Pre-metadata length ({len(str(pre_metadata_len))}) exceeds the maximum allowed size ({self.config['length_of_digits_to_represent_size']})"
            )

        pre_metadata_with_length = main_delim + str(pre_metadata_len).zfill(length_of_digits_to_represent_size) + main_delim + pre_metadata

        return pre_metadata_with_length
