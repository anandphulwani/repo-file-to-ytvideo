from .find_nearest_color import find_nearest_color
from .average_colors import average_colors

def determine_color_key(frame, x, y, encoding_color_map): 
    nearest_color_key = ''
    colorX1Y1 = tuple(frame[y, x])
    colorX1Y2 = ''
    colorX2Y1 = ''
    colorX2Y2 = ''
    if colorX1Y1[0] <= 50 and colorX1Y1[1] <= 50 and colorX1Y1[2] <= 50:
        nearest_color_key = "0"
    elif colorX1Y1[0] >= 200 and colorX1Y1[1] >= 200 and colorX1Y1[2] >= 200:
        nearest_color_key = "1"
    else:
        colorX1Y2 = tuple(frame[y + 1, x])
        if colorX1Y2[0] <= 50 and colorX1Y2[1] <= 50 and colorX1Y2[2] <= 50:
            nearest_color_key = "0"
        elif colorX1Y2[0] >= 200 and colorX1Y2[1] >= 200 and colorX1Y2[2] >= 200:
            nearest_color_key = "1"
        else:
            colorX2Y1 = tuple(frame[y, x + 1])
            if colorX2Y1[0] <= 50 and colorX2Y1[1] <= 50 and colorX2Y1[2] <= 50:
                nearest_color_key = "0"
            elif colorX2Y1[0] >= 200 and colorX2Y1[1] >= 200 and colorX2Y1[2] >= 200:
                nearest_color_key = "1"
            else:
                colorX2Y2 = tuple(frame[y + 1, x + 1])
                if colorX2Y2[0] <= 50 and colorX2Y2[1] <= 50 and colorX2Y2[2] <= 50:
                    nearest_color_key = "0"
                elif colorX2Y2[0] >= 200 and colorX2Y2[1] >= 200 and colorX2Y2[2] >= 200:
                    nearest_color_key = "1"
                else:
                    color = average_colors(colorX1Y1, colorX1Y2, colorX2Y1, colorX2Y2)
                    nearest_color_key = find_nearest_color(color, encoding_color_map)
    return nearest_color_key    
