import numpy as np


def find_nearest_color(pixel_color, encoding_color_map):
    color_map_rgb = {
        key: tuple(int(encoding_color_map[key][i:i + 2], 16) for i in (1, 3, 5))
        for key in encoding_color_map
    }
    min_distance = float('inf')
    nearest_color_key = None
    for key, value in color_map_rgb.items():
        distance = np.linalg.norm(np.array(pixel_color) - np.array(value))
        if distance < min_distance:
            min_distance = distance
            nearest_color_key = key
    return nearest_color_key
