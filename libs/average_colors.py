
# def average_colors(color1, color2, color3, color4, color5, color6):
#     avg_red = (int(color1[0]) + int(color2[0]) + int(color3[0]) + int(color4[0]) + int(color5[0]) + int(color6[0])) // 6
#     avg_green = (int(color1[1]) + int(color2[1]) + int(color3[1]) + int(color4[1]) + int(color5[1]) + int(color6[1])) // 6
#     avg_blue = (int(color1[2]) + int(color2[2]) + int(color3[2]) + int(color4[2]) + int(color5[2]) + int(color6[2])) // 6
#     return (avg_red, avg_green, avg_blue)


# def average_colors(color1, color2, color3, color4):
#     avg_red = (int(color1[0]) + int(color2[0]) + int(color3[0]) + int(color4[0])) // 4
#     avg_green = (int(color1[1]) + int(color2[1]) + int(color3[1]) + int(color4[1])) // 4
#     avg_blue = (int(color1[2]) + int(color2[2]) + int(color3[2]) + int(color4[2])) // 4
#     return (avg_red, avg_green, avg_blue)

def average_colors(*colors):
    num_colors = len(colors)
    if num_colors == 0:
        raise ValueError("At least one color must be provided")
    
    avg_red = sum(int(color[0]) for color in colors) // num_colors
    avg_green = sum(int(color[1]) for color in colors) // num_colors
    avg_blue = sum(int(color[2]) for color in colors) // num_colors
    
    return (avg_red, avg_green, avg_blue)