import string


def rot13_rot5(text):
    result = []
    for char in text:
        if char.isalpha():  # Apply ROT13
            base = ord('A') if char.isupper() else ord('a')
            result.append(chr(base + (ord(char) - base + 13) % 26))
        elif char.isdigit():  # Apply ROT5
            result.append(chr(ord('0') + (ord(char) - ord('0') + 5) % 10))
        else:  # Keep other characters the same
            result.append(char)
    return ''.join(result)
