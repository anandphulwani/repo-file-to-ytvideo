from .config_loader import load_config


class Metadata:
    # Define the metadata keys
    METADATA_KEYS = ["filename", "filesize", "total_baseN_length", "sha1_checksum"]

    def __init__(self):
        self.config = load_config('config.ini')
        self.metadata = {key: None for key in Metadata.METADATA_KEYS}

    def parse(self, meta_str):
        """
        Parse a metadata string of the form:
          |::-::|METADATA|:-:|Test03.iso|:-:|2134119|:-:|17072952|:-:|13c1d0cd49f31cf5976a14ca8821f1da69f6167a|::-::|
        """
        main_delim = self.config['premetadata_metadata_main_delimiter']
        sub_delim = self.config['premetadata_metadata_sub_delimiter']

        if not (meta_str.startswith(main_delim) and meta_str.endswith(main_delim)):
            raise ValueError("Metadata.py: Invalid metadata format: missing start or end markers.")

        # Remove the start and end markers.
        inner_str = meta_str[len(main_delim):-len(main_delim)]
        # Split the inner string using the delimiter.
        tokens = inner_str.split(sub_delim)

        if tokens[0] != "METADATA":
            raise ValueError("Metadata.py: Invalid metadata header: expected 'METADATA'")

        if len(tokens[1:]) != len(Metadata.METADATA_KEYS):
            raise ValueError("Metadata.py: Invalid metadata format: incorrect number of fields")

        # Assign parsed values
        for i, key in enumerate(Metadata.METADATA_KEYS):
            self.metadata[key] = tokens[i + 1] if key == "filename" or key == "sha1_checksum" else int(tokens[i + 1])

    def __str__(self):
        # Build a string representation of the object.
        metadata_str = "\n".join(f"{key}: {value}" for key, value in self.metadata.items())
        return f"Metadata:\n{metadata_str}"
