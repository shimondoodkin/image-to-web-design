"""Pad an image to a target size and produce a white-over-padding mask.

Used by the outpaint recipe in image-isolation-technique/SKILL.md. The recipe:

  1. Call pad_and_make_mask(src, out_image, out_mask, target_size).
  2. Call image-edit-instruction(out_image, instruction, mask=out_mask, out=...)
     with an instruction like "Fill the white masked area with a natural
     continuation of the painting around it. Do not modify the unmasked area."

The mask convention matches image-edit-instruction:
  - white (255) = the model may modify (the new padding)
  - black (0)   = preserve (the original source region)
"""
from PIL import Image


def pad_and_make_mask(
    src: str,
    out_image: str,
    out_mask: str,
    target_size: tuple,
    anchor: str = "center",
) -> None:
    """Pad `src` to `target_size`, write padded image + mask.

    `target_size` is (width, height) in pixels and must be >= the source
    on both axes. `anchor` is one of: center, left, right, top, bottom.
    """
    img = Image.open(src).convert("RGB")
    tw, th = target_size
    sw, sh = img.size
    assert tw >= sw and th >= sh, (
        f"target_size {target_size} must be >= source size {img.size}"
    )

    if anchor == "center":
        ox, oy = (tw - sw) // 2, (th - sh) // 2
    elif anchor == "left":
        ox, oy = 0, (th - sh) // 2
    elif anchor == "right":
        ox, oy = tw - sw, (th - sh) // 2
    elif anchor == "top":
        ox, oy = (tw - sw) // 2, 0
    elif anchor == "bottom":
        ox, oy = (tw - sw) // 2, th - sh
    else:
        raise ValueError(f"unknown anchor: {anchor!r}")

    padded = Image.new("RGB", (tw, th), (255, 255, 255))
    padded.paste(img, (ox, oy))
    padded.save(out_image)

    mask = Image.new("L", (tw, th), 255)
    preserve = Image.new("L", (sw, sh), 0)
    mask.paste(preserve, (ox, oy))
    mask.save(out_mask)
