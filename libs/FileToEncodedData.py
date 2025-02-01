import base64
from tqdm import tqdm
import os
import sys
import hashlib
import zfec
from .detect_base_from_json import detect_base_from_json
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
        self.total_binary_length = 0
        self.format_string = detect_base_from_json(config)[1]
        self.usable_bits_in_frame = config['usable_bits_in_frame']
        self.stream_encoded_file = open(f"{file_path}_encoded_stream.txt", "w") if debug else None
        self.file_size = os.path.getsize(file_path)
        self.file = open(file_path, "rb")
        self.pbar = tqdm(total=self.file_size, desc="Processing File", unit="B", unit_scale=True)
        self.buffer = ''
        self.metadata = None
        self.metadata_read_position = 0

    def create_metadata(self):
        self.buffer = ''
        # Prepare for metadata iternation
        self.metadata = self.get_metadata()
        self.pbar = tqdm(total=len(self.metadata), desc="Processing File", unit="B", unit_scale=True)

    def __iter__(self):
        return self

    def __next__(self):
        if self.content_type == ContentType.METADATA and self.metadata is None:
            self.create_metadata()

        # Determine how many bytes to read
        needed_bits = self.usable_bits_in_frame[self.content_type.value] - len(self.buffer)
        bytes_to_read = needed_bits // 8
        file_chunk = ''
        if self.metadata is not None:
            # Convert binary string to bytes
            file_chunk = bytes(
                int(self.metadata[i:i + 8], 2)
                for i in range(self.metadata_read_position, min(self.metadata_read_position + bytes_to_read * 8, len(self.metadata)), 8))
            self.metadata_read_position += bytes_to_read * 8  # Move by bits
        else:
            file_chunk = self.file.read(bytes_to_read)

        if not file_chunk:
            self.file.close() if self.content_type == ContentType.DATACONTENT else None
            self.pbar.close()
            self.stream_encoded_file.close() if self.stream_encoded_file else None
            self.content_type = ContentType.METADATA if self.content_type == ContentType.DATACONTENT else None
            raise StopIteration

        # Update progress and metadata
        self.pbar.update(len(file_chunk * 8 if self.metadata is not None else file_chunk))
        self.sha1.update(file_chunk)
        self.total_binary_length += len(file_chunk) * 8  # Assuming 8 bits per byte

        # Convert file bytes to a binary string
        chunk_bits = "".join(f"{byte:{self.format_string}}" for byte in file_chunk)

        # Add new bits to buffer
        self.buffer += chunk_bits

        if len(self.buffer) >= self.usable_bits_in_frame[self.content_type.value]:
            data_to_yield = self.buffer[:self.usable_bits_in_frame[self.content_type.value]]
            self.buffer = self.buffer[self.usable_bits_in_frame[self.content_type.value]:]
        else:
            data_to_yield = self.buffer
            self.buffer = ''

        self.stream_encoded_file.write(data_to_yield) if self.stream_encoded_file and self.content_type == ContentType.DATACONTENT else None
        return (self.content_type, data_to_yield)

    def get_metadata(self):
        """
        Returns the metadata.
        """
        format_string = detect_base_from_json(self.config)[1]

        metadata_items = {}
        # ------------------------------------------
        # STEP 1: Build the metadata WITHOUT length
        # ------------------------------------------
        temp_metadata = (f"|::-::|METADATA"
                         f"|:-:|{os.path.basename(self.file_path)}"
                         f"|:-:|{self.file_size}"
                         f"|:-:|{self.total_binary_length}"
                         f"|:-:|{self.sha1.hexdigest()}"
                         f"|::-::|")

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
        rscodec_value = 255 if len(metadata_with_checksum) > 255 else len(metadata_with_checksum) - 1
        reed_solomon_encoded = RSCodec(rscodec_value).encode(metadata_with_checksum.encode()).decode(errors='ignore')
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

        # -----------------------------------------
        # STEP 8: Convert all metadata to binary
        # -----------------------------------------
        binary_metadata_items = {}
        for key, value in metadata_items.items():
            binary_metadata_items[key] = "".join(format(ord(char), format_string) for char in value)

        return binary_metadata_items
