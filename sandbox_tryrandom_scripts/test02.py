import os
import shutil
import numpy as np
from moviepy.video.tools.segmenting import findObjects
from moviepy.editor import TextClip, CompositeVideoClip, ColorClip

frames_dir = "frames"
if os.path.exists(frames_dir):
    shutil.rmtree(frames_dir)
os.makedirs(frames_dir)

# Step 1: Setup the scene
screensize = (720, 460)
background_color = (255, 255, 255)  # White background for contrast
text_color = 'black'  # Ensure contrast for findObjects
duration = 10

txt_clip = TextClip("GeeksforGeeks", fontsize=70, color=text_color, font="Arial", bg_color='white').set_duration(duration)
background_clip = ColorClip(size=screensize, color=background_color, duration=duration)
cvc = CompositeVideoClip([background_clip, txt_clip.set_pos('center')], size=screensize)
letters = findObjects(cvc)  # Extracts characters as separate clips
for i, letter in enumerate(letters):
    frame_filename = os.path.join(frames_dir, f"letter_{i}.png")
    letter.save_frame(frame_filename, t=0)


def move_letters(letters):
    return [letter.set_pos(lambda t: (letter.screenpos[0], letter.screenpos[1] - 50 * np.sin(t * 2 * np.pi / duration))) for letter in letters]


animated_letters = move_letters(letters)
final_clip = CompositeVideoClip([background_clip] + animated_letters, size=screensize).set_duration(duration)

output_file_path = "animated_text.mp4"
final_clip.write_videofile(output_file_path, fps=24)
