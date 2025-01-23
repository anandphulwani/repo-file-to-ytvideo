# import pygame
# import random
# import imageio
# from tqdm import tqdm  # Import tqdm for the progress bar

# # Initialize Pygame
# pygame.init()

# # Set up the display
# width, height = 1920, 1080
# padded_height = 1088  # Closest number divisible by 16
# screen = pygame.display.set_mode((width, padded_height))
# pygame.display.set_caption("Disco Lights Animation")

# # Define colors
# colors = [
#     (255, 0, 0),    # Red
#     (0, 255, 0),    # Green
#     (0, 0, 255),    # Blue
#     (255, 255, 0),  # Yellow
#     (255, 0, 255),  # Magenta
#     (0, 255, 255),  # Cyan
#     (255, 255, 255) # White
# ]

# # Initialize the writer
# output_path = 'disco_lights2.mp4'
# writer = imageio.get_writer(output_path, fps=30)  # Adjust fps for desired speed

# # Determine the total number of frames
# total_frames = 30 * 5  # 30 * 60 * 60  # 30 FPS * 60 seconds * 60 minutes for a 1-hour video

# # Main loop with tqdm progress bar
# running = True
# with tqdm(total=total_frames, desc="Generating Video") as pbar:
#     while running and pbar.n < total_frames:
#         for event in pygame.event.get():
#             if event.type == pygame.QUIT:
#                 running = False

#         # Draw randomly colored squares on the screen
#         for _ in range(300):  # Number of squares
#             random_color = random.choice(colors)
#             random_pos = (random.randint(0, width), random.randint(0, padded_height))
#             random_size = random.randint(20, 100)  # Random size of the square
#             pygame.draw.rect(screen, random_color, (*random_pos, random_size, random_size))

#         pygame.display.flip()
#         frame = pygame.surfarray.array3d(pygame.display.get_surface())
#         frame = frame.transpose([1, 0, 2])
#         print(f"height: {height}")
#         frame = frame[:height, :, :]  # Crop to the original height
#         writer.append_data(frame)
#         pygame.time.delay(100)  # Delay to slow down the animation
#         screen.fill((0, 0, 0))  # Reset the screen

#         pbar.update(1)  # Update the progress bar for each frame generated

# # Finish up
# writer.close()
# pygame.quit()

import pygame
import random
import imageio
import cv2  # Import OpenCV
from tqdm import tqdm

# Initialize Pygame
pygame.init()

# Set up the display
width, height = 1920, 1080
screen = pygame.display.set_mode((width, height))
pygame.display.set_caption("Disco Lights Animation")

# Define colors
colors = [
    (255, 0, 0),  # Red
    (0, 255, 0),  # Green
    (0, 0, 255),  # Blue
    (255, 255, 0),  # Yellow
    (255, 0, 255),  # Magenta
    (0, 255, 255),  # Cyan
    (255, 255, 255)  # White
]

# Initialize the writer
output_path = 'disco_lights2.mp4'
writer = imageio.get_writer(output_path, fps=30, ffmpeg_params=['-vf', 'scale=1920:1080,format=yuv420p'])
# writer = imageio.get_writer(output_path, fps=30)

# Main loop
total_frames = 30 * 60 * 15  # for demonstration
running = True
with tqdm(total=total_frames, desc="Generating Video") as pbar:
    while running and pbar.n < total_frames:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        for _ in range(300):  # Number of squares
            random_color = random.choice(colors)
            random_pos = (random.randint(0, width), random.randint(0, height))
            random_size = random.randint(20, 100)  # Size of the square
            pygame.draw.rect(screen, random_color, (*random_pos, random_size, random_size))

        pygame.display.flip()

        # Convert surface to a numpy array
        frame = pygame.surfarray.array3d(pygame.display.get_surface())
        frame = cv2.transpose(frame)  # Transpose to change to (height, width, channels)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)  # Convert RGB to BGR which OpenCV expects

        # Optional: Resize to ensure dimensions are exactly as required (1920x1080)
        frame = cv2.resize(frame, (1920, 1080), interpolation=cv2.INTER_LINEAR)

        writer.append_data(frame)  # Append the resized frame
        pygame.time.delay(100)
        screen.fill((0, 0, 0))
        pbar.update(1)

# Cleanup
writer.close()
pygame.quit()
