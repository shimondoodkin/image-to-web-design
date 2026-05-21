from PIL import Image, ImageDraw

img = Image.new("RGB", (768, 768), "black")
draw = ImageDraw.Draw(img)
# Draw a red square at (25, 25) to (35, 35) which is centered at (30, 30)
draw.rectangle([(25, 25), (35, 35)], fill="red")
img.save("temp_image.png")
