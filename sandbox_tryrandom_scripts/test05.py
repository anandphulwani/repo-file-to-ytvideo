from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageSequenceClip
import os

# Settings
text = "Hello"
font_size = 70
frames_count = 60  # Number of frames in the animation
frame_rate = 30  # Frames per second in the output video
img_size = (720, 480)
font_path = "arial.ttf"  # Update with the path to your font if needed

# Create frames directory
frames_dir = "frames"
os.makedirs(frames_dir, exist_ok=True)

# Generate frames
for frame in range(frames_count):
    img = Image.new('RGB', img_size, color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)

    for i, char in enumerate(text):
        # Calculate position for each character to animate
        position = (10 + frame * 5 + i * font_size, 200)  # Simple horizontal movement
        draw.text(position, char, font=font, fill=(0, 0, 0))

    # Save frame
    img.save(f"{frames_dir}/frame_{frame:03}.png")

# Compile frames into a video
frame_files = [f"{frames_dir}/{img}" for img in sorted(os.listdir(frames_dir)) if img.endswith(".png")]
clip = ImageSequenceClip(frame_files, fps=frame_rate)
clip.write_videofile("text_animation.mp4", fps=frame_rate)

# Optional: Cleanup frames directory if no longer needed
# shutil.rmtree(frames_dir)
