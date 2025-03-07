import math
import base64

BASE64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def base64_char_to_int(c):
    """Return the integer (0..63) for a single Base64 character."""
    return BASE64_CHARS.index(c)


# Named functions for number conversion
def int_from_bin(x):
    return int(x, 2)


def int_from_oct(x):
    return int(x, 8)


def int_from_dec(x):
    return int(x, 10)


def int_from_hex(x):
    return int(x, 16)


# Decoding functions with error handling
def decode_base2(data):
    """Decodes base 2 (binary) encoded data into bytes, preserving leading zeros."""
    if isinstance(data, bytes):  # Convert bytes to string if necessary
        data = data.decode("utf-8")

    if len(data) % 8 != 0:
        raise ValueError(f"Invalid binary length: {len(data)} (must be a multiple of 8)")

    int_value = int(data, 2)  # Convert binary to integer
    return int_value.to_bytes(len(data) // 8, 'big')  # Preserve leading zeros


def decode_base4(data):
    """Decodes base 4 encoded data into bytes."""
    int_value = int(data, 4)
    return int_value.to_bytes((int_value.bit_length() + 7) // 8, 'big')


def decode_base8(data):
    """Decodes base 8 (octal) encoded data into bytes."""
    int_value = int_from_oct(data)
    return int_value.to_bytes((int_value.bit_length() + 7) // 8, 'big')


def decode_base10(data):
    """Decodes base 10 (decimal) data into a string."""
    return str(data).encode()


def decode_base16(data):
    """Decodes base 16 (hexadecimal) encoded data into bytes, preserving leading zeros."""
    if isinstance(data, bytes):  # Convert bytes to string if necessary
        data = data.decode("utf-8")

    if len(data) % 2 != 0:
        raise ValueError(f"Invalid hex length: {len(data)} (must be even)")

    return bytes.fromhex(data)  # Decode hex string into bytes


def decode_base64(data):
    """Decodes base 64 encoded data into bytes."""
    return base64.b64decode(data)


def get_length_in_base(data_length, encoding_bits_per_value):
    """Returns the length of a string when it gets converted into a particular base."""
    total_bits = data_length * 8  # Each character is 8 bits (ASCII/UTF-8)
    return math.ceil(total_bits / encoding_bits_per_value)


def get_length_from_base(base_length, encoding_bits_per_value):
    """Returns the original data length from the base-encoded length."""
    total_bits = base_length * encoding_bits_per_value
    return math.ceil(total_bits / 8)  # Convert bits back to bytes


# **Updated Encoding Functions**
def encode_base16(data):
    """Encodes binary or text data into a hexadecimal string."""
    if isinstance(data, bytes):
        print("encode_base16 data:", data, ", bytes data hex:", data.hex())
        return data.hex()  # Convert bytes to hex string
    print("Not bytes, encode_base16 data:", data, ",  data hex:", "".join(format(ord(c), "02x") for c in data))
    return "".join(format(ord(c), "02x") for c in data)  # Convert text to hex string


def encode_base64(data):
    """Encodes binary or text data into a Base64 string."""
    if isinstance(data, bytes):
        return base64.b64encode(data).decode()  # Convert bytes to Base64 string
    return base64.b64encode(data.encode()).decode()  # Convert text to Base64 string


def detect_base_from_json(encoding_map):
    """Detects encoding base from JSON encoding map and returns relevant data."""
    base = len(encoding_map)
    if base <= 1:
        raise ValueError("Base must be greater than 1.")

    base_data = {
        2: {
            "format": "08b",
            "chunk_size": 8,
            "func": int_from_bin,
            "decode_func": decode_base2
        },
        4: {
            "format": "02b",
            "chunk_size": 2,
            "func": int,
            "decode_func": decode_base4
        },
        8: {
            "format": "03o",
            "chunk_size": 3,
            "func": int_from_oct,
            "decode_func": decode_base8
        },
        10: {
            "format": "d",
            "chunk_size": 3,
            "func": int_from_dec,
            "decode_func": decode_base10
        },
        16: {
            "format": "02x",
            "chunk_size": 2,
            "func": encode_base16,  # Now returns a string
            "decode_func": decode_base16
        },
        64: {
            "format": "",
            "chunk_size": 1,
            "func": encode_base64,  # Now returns a string
            "decode_func": decode_base64
        },
    }

    if base in base_data:
        return base, base_data[base]["format"], base_data[base]["chunk_size"], base_data[base]["func"], base_data[base]["decode_func"]

    raise ValueError("detected_base_from_json.py: Unsupported base detected in JSON encoding map.")
