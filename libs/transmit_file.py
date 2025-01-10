class transmit_file:
    def __init__(self, name, size, binary_length, sha1):
        self.name = name
        self.size = int(size)
        self.binary_length = int(binary_length)
        self.sha1 = sha1
