import numpy as np
import mmap


def generate_unicode_delta_numpy(file1, file2, output_file, chunk_size=65536):
    with open(file1, "rb") as f1, open(file2, "rb") as f2, open(output_file, "w", encoding="utf-8") as out:
        # Memory-map both files
        mm1 = mmap.mmap(f1.fileno(), 0, access=mmap.ACCESS_READ)
        mm2 = mmap.mmap(f2.fileno(), 0, access=mmap.ACCESS_READ)

        offset = 0
        while offset < len(mm1) and offset < len(mm2):
            # Read chunks
            chunk1 = mm1[offset:offset + chunk_size]
            chunk2 = mm2[offset:offset + chunk_size]

            # Convert chunks to NumPy arrays
            arr1 = np.frombuffer(chunk1, dtype=np.uint8)
            arr2 = np.frombuffer(chunk2, dtype=np.uint8)

            # Find differences
            diffs = np.where(arr1 != arr2)[0]
            for diff in diffs:
                out.write(f"{offset + diff}: {arr1[diff]:02x} -> {arr2[diff]:02x}\n")

            offset += chunk_size

        # Handle case where files have different lengths
        if len(mm1) != len(mm2):
            longer, shorter, label = (mm1, mm2, "file1") if len(mm1) > len(mm2) else (mm2, mm1, "file2")
            for i in range(len(shorter), len(longer)):
                value = longer[i]
                out.write(f"{i}: {value:02x} -> None ({label} extra byte)\n")

        print(f"Differences written to {output_file}")


# Example usage
generate_unicode_delta_numpy("Windows 10 Lite Edition 19H2 x64.iso", "decoded_Windows 10 Lite Edition 19H2 x64.iso", "delta_file_unicode.txt")
