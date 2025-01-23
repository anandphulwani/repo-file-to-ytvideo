from PIL import Image, ImageDraw, ImageFont

width, height = 640, 480
background_color = (255, 255, 255)
text_color = (0, 0, 0)
font_size = 40

frames = []
for i in range(100):  # Create 100 frames
    img = Image.new('RGB', (width, height), color=background_color)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", font_size)
    d.text((10 + i, 220), "Hello, World!", fill=text_color, font=font)
    frames.append(img)

frames[0].save('text_animation.gif', save_all=True, append_images=frames[1:], optimize=False, duration=40, loop=0)
