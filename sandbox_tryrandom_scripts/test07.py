number = 1233456789
# Pad the number to 20 characters
padded_number = str(number).zfill(20)

# Convert each character to binary and concatenate
binary_representation = ''.join(format(ord(char), '08b') for char in padded_number)

print(binary_representation)