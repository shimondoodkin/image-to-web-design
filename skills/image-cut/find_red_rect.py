import PIL.Image
import numpy as np

def find_red_rectangle(image_path):
    img = PIL.Image.open(image_path).convert('RGB')
    data = np.array(img)
    
    # Red is roughly (255, 0, 0).
    # Let's look for pixels where R is high and G, B are low.
    red_mask = (data[:, :, 0] > 200) & (data[:, :, 1] < 50) & (data[:, :, 2] < 50)
    
    rows = np.any(red_mask, axis=1)
    cols = np.any(red_mask, axis=0)
    
    if not np.any(rows) or not np.any(cols):
        return None
    
    y1, y2 = np.where(rows)[0][[0, -1]]
    x1, x2 = np.where(cols)[0][[0, -1]]
    
    return x1, y1, x2, y2

if __name__ == "__main__":
    coords = find_red_rectangle(r'scripts\_gaps_out\img_3b6ca8eb1165.png')
    if coords:
        print(f"{coords[0]},{coords[1]},{coords[2]},{coords[3]}")
    else:
        print("Not found")
