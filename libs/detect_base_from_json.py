import json
import sys


def detect_base_from_json(config):
    # Load and check the JSON encoding map
    with open(config['encoding_map_path'], 'r') as file:
        encoding_map = json.load(file)
    base = len(encoding_map)

    # Define format strings for each base
    base_formats = {
        2: "08b",  # Binary format for each byte
        8: "03o",  # Octal format for each byte
        10: "d",  # Decimal format for each byte
        16: "02x",  # Hexadecimal format for each byte
        64: ""  # Base64 is a special case handled separately
    }

    if base in base_formats:
        return base, base_formats[base]
    else:
        print("Unsupported base detected in JSON encoding map.")
        sys.exit(1)
