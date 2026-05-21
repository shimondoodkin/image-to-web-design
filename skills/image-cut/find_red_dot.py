from PIL import Image

def find_red_dot_center(image_path="temp_image.png"):
    img = Image.open(image_path)
    pixels = img.load()
    width, height = img.size

    red_pixels = []
    # Iterate through all pixels and find red ones
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y][:3]  # Get RGB values, ignore alpha if present
            # Assuming "red" is (255, 0, 0) with a small tolerance
            if r > 200 and g < 50 and b < 50:
                red_pixels.append((x, y))

    if not red_pixels:
        raise ValueError("No red pixels found in the image.")

    # Calculate the center of the red pixels
    sum_x = sum(p[0] for p in red_pixels)
    sum_y = sum(p[1] for p in red_pixels)
    center_x = round(sum_x / len(red_pixels))
    center_y = round(sum_y / len(red_pixels))

    return f"{center_x},{center_y}"

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "temp_image.png"
    try:
        coords = find_red_dot_center(path)
        print(coords)
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
