from .config_loader import load_config
from .content_type import ContentType


class PreMetadata:
    # Define the list of section names.
    SECTION_NAMES = ["normal", "base64", "rot13", "reed_solomon", "zfec"]
    # Dynamically build the SECTION_KEYS mapping: every section gets ["frame_count", "data_size"]
    SECTION_KEYS = {section: ["frame_count", "data_size"] for section in SECTION_NAMES}
    # Inject "rscodec_value" into the "reed_solomon" section at position 1 (second element)
    SECTION_KEYS["reed_solomon"].insert(1, "rscodec_value")

    def __init__(self):
        self.config = load_config('config.ini')
        # Overall premetadata frame count.
        self.premetadata_frame_count = None
        self.metadata_frame_count = None
        self.premetadata_and_metadata_frame_count = None
        # Initialize sections using a dictionary comprehension.
        self.sections = {section: {key: None for key in keys} for section, keys in PreMetadata.SECTION_KEYS.items()}

    def parse(self, meta_str, premetadata_frame_count):
        """
        Parse a metadata string of the form:
          |::-::|PREMETADATA|:-:|normal|:-:|1|:-:|2880|:-:|base64|:-:|1|:-:|1280
          |:-:|rot13|:-:|1|:-:|960|:-:|reed_solomon|:-:|1|:-:|119|:-:|1506
          |:-:|zfec|:-:|1|:-:|3200|::-::|
          
        Also initializes the object's premetadata_frame_count (must be an integer).
        """
        # Validate the premetadata_frame_count argument.
        if not isinstance(premetadata_frame_count, int):
            raise ValueError("PreMetadata.py: premetadata_frame_count must be an integer")
        self.premetadata_frame_count = premetadata_frame_count

        main_delim = self.config['premetadata_metadata_main_delimiter']
        sub_delim = self.config['premetadata_metadata_sub_delimiter']
        if not (meta_str.startswith(main_delim) and meta_str.endswith(main_delim)):
            raise ValueError("PreMetadata.py: Invalid pre_metadata format: missing start or end markers.")

        # Remove the start and end markers.
        inner_str = meta_str[len(main_delim):-len(main_delim)]
        # Split the inner string using the delimiter.
        tokens = inner_str.split(sub_delim)

        if tokens[0] != "PREMETADATA":
            raise ValueError("PreMetadata.py: Invalid pre_metadata header: expected 'PREMETADATA'")

        # Process tokens using the dynamic SECTION_KEYS mapping.
        i = 1  # start after the header token "PREMETADATA"
        while i < len(tokens):
            section = tokens[i]
            if section not in PreMetadata.SECTION_KEYS:
                raise ValueError("PreMetadata.py: Unknown section encountered: " + section)
            keys = PreMetadata.SECTION_KEYS[section]
            # For each key in the section, convert the token to an integer and assign it.
            for j, key in enumerate(keys, start=1):
                self.sections[section][key] = int(tokens[i + j])
            # Move the index forward: 1 for the section token plus one for each key.
            i += len(keys) + 1

        # **Calculate metadata_frame_count**
        self.metadata_frame_count = sum(self.sections[section]["frame_count"] * self.config["total_frames_repetition"][ContentType.METADATA.value]
                                        for section in self.sections)

        # **Calculate premetadata_and_metadata_frame_count**
        self.premetadata_and_metadata_frame_count = self.metadata_frame_count + self.premetadata_frame_count

    def __str__(self):
        # Build a string representation of the object.
        sections_str = "\n".join(f"{section}: {data}" for section, data in self.sections.items())
        return f"Premetadata Frame Count: {self.premetadata_frame_count}\n{sections_str}"
