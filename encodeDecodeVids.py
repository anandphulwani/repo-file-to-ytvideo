from PIL import Image
import math
import os
import base64
import sys
import json
from moviepy.editor import ImageSequenceClip
import numpy as np
from PIL import Image
from tqdm import tqdm
import cv2

def detect_base_from_json(encoding_map_path):
    # Load and check the JSON encoding map
    with open(encoding_map_path, 'r') as file:
        encoding_map = json.load(file)
    base = len(encoding_map)

    # Map the base to its corresponding function
    base_functions = {
        2: bin,
        8: oct,
        10: lambda x: str(x),
        16: hex,
        64: lambda x: base64.b64encode(x).decode('utf-8')
    }

    if base in base_functions:
        return base, base_functions[base]
    else:
        print("Unsupported base detected in JSON encoding map.")
        sys.exit(1)

def file_to_encodeddata(file_path, encoding_map_path='encoding_color_map.json'):
    base, base_function = detect_base_from_json(encoding_map_path)

    print(f"Base is {base}")

    # Check if the file exists
    if not os.path.exists(file_path):
        print("The specified file does not exist.")
        sys.exit(1)

    # Read the file content
    with open(file_path, "rb") as file:
        file_content = file.read()

    # Convert the file content based on the detected base
    if base == 64:  # Directly encode for base64
        encoded_data = base_function(file_content)
    else:
        # For other bases, encode each byte individually
        encoded_data = "".join(base_function(byte)[2:] for byte in file_content)

    return encoded_data

def encodeddata_to_frames(file_path='fdm.exe', encoding_map_path='encoding_color_map.json', width=1920, height=1080, pixel_size=1, fps=1):
    encoded_data = file_to_encodeddata(file_path, encoding_map_path)
    base, base_function = detect_base_from_json(encoding_map_path)
    
    # Open the file in write mode and save the encoded data
    with open(f"{file_path}_stream.txt", "w") as file:
        file.write(encoded_data)
        
    # Load the encoding color map
    with open(encoding_map_path, 'r') as file:
        encoding_color_map = json.load(file)

    num_elements = len(encoded_data) # Calculate the total number of elements needed to represent the encoded data    
    elements_per_image = (width // pixel_size) * (height // pixel_size) # Calculate the number of elements that can fit in one image
    num_images = math.ceil(num_elements / elements_per_image) # Calculate the number of images needed
    frames = []
    
    # Loop through each image
    for i in tqdm(range(num_images)):
        # Determine the part of the encoded data to use for this image
        start_index = i * elements_per_image
        end_index = min(start_index + elements_per_image, num_elements)
        part_data = encoded_data[start_index:end_index]
        
        # Create a new image
        img = Image.new('RGB', (width, height), color='white')
        
        # Fill the image with encoded data
        for j, char in enumerate(part_data):
            # Determine the color of the pixel
            if char in encoding_color_map:
                color = tuple(int(encoding_color_map[char][k:k+2], 16) for k in (1, 3, 5))
            elif char == '=' and base == 64:
                # Handle padding character for base64 specifically
                color = (0, 0, 0)
            else:
                print(f"Unknow character:{char} found in encoded data stream")
                sys.exit(1)
            
            # Calculate pixel position
            x = (j % (width // pixel_size)) * pixel_size
            y = (j // (width // pixel_size)) * pixel_size
            
            # Draw the pixel
            for px in range(pixel_size):
                for py in range(pixel_size):
                    img.putpixel((x + px, y + py), color)
        
        # Convert PIL image to numpy array and add to frames
        frame = np.array(img)
        # frames.append(frame)
        yield frame

def inject_frames_to_outvideo(video_path = "animation_3600.mp4", output_path = "animation_3600_mod.mp4", framegenfn = encodeddata_to_frames(), skip_seconds=0, original_fps=24, new_fps=30):
    # Open the source video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError("Error opening video stream or file")

    # Define the codec and create VideoWriter object
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), new_fps, (frame_width, frame_height))

    # Calculate the number of frames to skip and position the video
    # frames_to_skip = skip_seconds * original_fps
    # cap.set(cv2.CAP_PROP_POS_FRAMES, frames_to_skip)

    # Variables to control the injection of new frames
    frame_counter = 0
    isinjectedframedone = False

    # Read and process the video
    while True:
        ret, frame = cap.read()
        if not ret:
            break  # Stop if end of video reached

        # Write the frame to the output video
        out.write(frame)
        frame_counter += 1
        # print(f"{frame_counter}: remainderVal: {frame_counter % 30}, remainder: {frame_counter % 30 in [5, 15, 25]}")
        # print(f"{frame_counter}: firstCondition: {injected_frame_counter < len(frames_to_inject)}, injected_frame_counter: {injected_frame_counter}, len(frames_to_inject) {len(frames_to_inject)}")

        if not isinjectedframedone and frame_counter % 30 in [12]:
            new_frame = next(framegenfn, None)
            if new_frame is not None:
                # print(f"injected a frame at {frame_counter}")
            # Check if it's time to inject a frame
            # if injected_frame_counter < len(frames_to_inject) and frame_counter % 30 in [5, 15, 25]:
                # print(f"injected_frame_counter: {injected_frame_counter}, len(frames_to_inject) {len(frames_to_inject)}")
                # Assuming frames_to_inject is a generator or a list of frames
                # img = frames_to_inject[injected_frame_counter]
                # Inject the frame and its duplicate
                out.write(new_frame)
                # out.write(new_frame)
                # injected_frame_counter += 1
                # frame_counter += 2  # Update counter to account for the injected frames
            else:
                print("injected frame done.")
                isinjectedframedone = True
        if isinjectedframedone and frame_counter % 30 == 0:
            print("injected frame done and second done.")
            break

    # Release everything if the job is finished
    print("It is done")
    cap.release()
    out.release()



# Example usage
# video_path = 
# output_path = 

# try:
#     inject_frames(video_path, output_path, frames)
#     print("Video processing completed.")
# except IOError as e:
#     print(str(e))

if __name__ == "__main__":
    # Ask the user for the path to the file they wish to encode
    # file_path = input("Please enter the file path to encode: ")

    # Optional: Ask for the path to the encoding color map JSON file
    # This step can be skipped if you always use a default path for the encoding map
    encoding_map_path = input("Please enter the path to the encoding color map JSON file (press enter to use default): ")
    if not encoding_map_path.strip():
        encoding_map_path = 'encoding_color_map.json'  # Default path

    # Encode the file
    # try:
    inject_frames_to_outvideo()
    
    # encoded_data = file_to_encodeddata(file_path, encoding_map_path)
    # if encoded_data:
    #     print("File successfully encoded.")
    #     inject_frames_to_outvideo()
    #     encodeddata_to_video(encoded_data, file_path)
    # else:
    #     print("No encoded data was returned.")
    
    #except FileNotFoundError:
    #    print(f"File not found: {file_path}")
    #    sys.exit(1)
    #except Exception as e:
    #    print(f"An error occurred: {e}")
    #    sys.exit(1)