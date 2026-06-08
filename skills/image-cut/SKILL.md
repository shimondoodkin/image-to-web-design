---
name: image-cut
description: use this skill when you read an image with intent to take part of the image.
---

there is a problem in claude 4.7, 4.8 to see get preceicce coordinates and bounding boxes at arbitrary size inputs.
it can see with good enaugh percition when width is 768 and padded with 50px at right.
and height is also <=768 padded with 50px at bottom

so to see the full image, need or, 1 to look at it in parts, or to sale it in that dimention. 
as utility for fine details if really requered after finding a region look at region to get details in the region.

here are tools - python scripts you can utilize:


1. take image and make it fit in sight region (downscale/pad to the 768 sweet spot, + 50px right/bottom margin, content at (0,0))

 ```bash
  python look_prep_claude.py screenshot.png --output look.png
 ```

2. after you know the ccordinaties from looking at look image, need to convert them back to screenshot coordinates. for this you cave a tool:

  ```bash
  python un-look-prep-claude.py --input-was screenshot.png --coords '{"logo":[40,30],"cta":[700,480,760,510]}'

  ```
  output would be similar to input translated, the coordinates are in paris of x,y one after another
  {"logo":[40,30],"cta":[700,480,760,510]}