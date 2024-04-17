from statistics import mode, StatisticsError
import sys

def find_nearest_tuple(color_tuples):
    transformed = [0 if t[0] < 103 else 1 for t in color_tuples if t[0] < 103 or t[0] > 153]
    try:
        dominant_category = mode(transformed)
    except StatisticsError:
        print(f"color_tuples: {color_tuples}")
        sys.exit(1)
    return (0, 0, 0) if dominant_category == 0 else (255, 255, 255)
