import json

def detect_base_from_json(encoding_map_path):
    # Identical function from your encoder script
    # Load and check the JSON encoding map
    with open(encoding_map_path, 'r') as file:
        encoding_map = json.load(file)
    base = len(encoding_map)
    return base


# def detect_base_from_json():
#     # Load and check the JSON encoding map
#     with open(config['encoding_map_path'], 'r') as file:
#         encoding_map = json.load(file)
#     base = len(encoding_map)

#     # Map the base to its corresponding function
#     base_functions = {
#         2: bin,
#         8: oct,
#         10: lambda x: str(x),
#         16: hex,
#         64: lambda x: base64.b64encode(x).decode('utf-8')
#     }

#     if base in base_functions:
#         return base, base_functions[base]
#     else:
#         print("Unsupported base detected in JSON encoding map.")
#         sys.exit(1)
