def average_colors(*colors):
    num_colors = len(colors)
    if num_colors == 0:
        raise ValueError("At least one color must be provided")
    
    avg_red = sum(int(color[0]) for color in colors) // num_colors
    avg_green = sum(int(color[1]) for color in colors) // num_colors
    avg_blue = sum(int(color[2]) for color in colors) // num_colors
    
    return (avg_red, avg_green, avg_blue)