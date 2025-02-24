import numpy as np
import numba


@numba.njit
def determine_color_key(
    frame: np.ndarray,
    x: int,
    y: int,
    box_step: int,
    encoding_color_map_keys: np.ndarray,
    encoding_color_map_values: np.ndarray,
    encoding_color_map_values_lower_bounds: np.ndarray,
    encoding_color_map_values_upper_bounds: np.ndarray,
):
    """
    Determines the color key for a given position (x, y) in the frame.
    Prioritizes quick detection using dynamically computed thresholds before falling back to closest match.
    """
    # Precompute mid positions for even/odd sampling
    if box_step > 1:
        half = box_step // 2  # integer division

    # --------------------------------------------------
    # 1) Determine the pixel(s) to read.
    # --------------------------------------------------
    if box_step == 1:
        # Single pixel sampling
        b, g, r = frame[y, x]
    elif (box_step % 2) == 1:
        # Odd-sized region, use the center pixel
        center_y = y + half
        center_x = x + half
        b, g, r = frame[center_y, center_x]
    else:
        # Even-sized region, average 4 center pixels
        center_y = y + half - 1
        center_x = x + half - 1

        b = (frame[center_y, center_x, 0] + frame[center_y, center_x + 1, 0] + frame[center_y + 1, center_x, 0] +
             frame[center_y + 1, center_x + 1, 0]) // 4
        g = (frame[center_y, center_x, 1] + frame[center_y, center_x + 1, 1] + frame[center_y + 1, center_x, 1] +
             frame[center_y + 1, center_x + 1, 1]) // 4
        r = (frame[center_y, center_x, 2] + frame[center_y, center_x + 1, 2] + frame[center_y + 1, center_x, 2] +
             frame[center_y + 1, center_x + 1, 2]) // 4

    # ----------------------------------------------------------------
    # 2) Quick detection based on thresholds
    # ----------------------------------------------------------------
    for i in range(len(encoding_color_map_keys)):
        if (encoding_color_map_values_lower_bounds[i, 0] <= r <= encoding_color_map_values_upper_bounds[i, 0]
                and encoding_color_map_values_lower_bounds[i, 1] <= g <= encoding_color_map_values_upper_bounds[i, 1]
                and encoding_color_map_values_lower_bounds[i, 2] <= b <= encoding_color_map_values_upper_bounds[i, 2]):
            return encoding_color_map_keys[i]

    # ----------------------------------------------------------------
    # 3) Fallback: Find the nearest color based on Euclidean distance.
    # ----------------------------------------------------------------
    min_dist = float('inf')
    best_match = None

    for i in range(len(encoding_color_map_keys)):
        value_r, value_g, value_b = encoding_color_map_values[i]
        # Euclidean distance (no sqrt for speed)
        dist = (r - value_r)**2 + (g - value_g)**2 + (b - value_b)**2

        if dist < min_dist:
            min_dist = dist
            best_match = encoding_color_map_keys[i]
    return best_match
