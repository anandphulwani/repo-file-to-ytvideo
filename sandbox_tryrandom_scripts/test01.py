from moviepy.editor import TextClip, ImageClip, CompositeVideoClip, ColorClip

# Step 1: Create and Save the TextClip as an Image
# Create TextClip with desired text, font size, color, and background color
text = "GeeksforGeeks"
txt_clip = TextClip(text, fontsize=70, color='black', font="Arial", bg_color='white')

# Save the TextClip as an image at the first frame
txt_img_path = "text_image.png"
txt_clip.save_frame(txt_img_path, t=0)  # Saving the first frame as an image

# Step 2: Convert the Saved Image to an ImageClip
# Load the saved image as an ImageClip
txt_img_clip = ImageClip(txt_img_path)

# Set the duration and position of the ImageClip as needed
txt_img_clip = txt_img_clip.set_duration(10).set_pos('center')

# Step 3: Prepare the Background Clip
# Define the size of the video and the background color
screensize = (720, 460)
background_clip = ColorClip(size=screensize, color=(255, 255, 255), duration=10)  # White background

# Step 4: Composite the ImageClip over the Background Clip
# Create a CompositeVideoClip including the background and the text image clip
final_clip = CompositeVideoClip([background_clip, txt_img_clip])

# Step 5: Preview or Write the Final Clip to a File
# Preview the final composition (or use write_videofile to save to a file)
# final_clip.preview()  # Remove this line if you're running in a non-interactive environment

# Uncomment the line below to save the output to a file instead of previewing
final_clip.write_videofile("output_video.mp4", fps=24)
