"""Tests for the outpaint padding/mask snippet shipped inside
skills/image-isolation-technique/SKILL.md.

The snippet lives in skills/image-isolation-technique/_examples/outpaint_mask.py
so it can be imported and tested as code; the SKILL.md embeds the same source
inline for human readers.
"""
from pathlib import Path
import importlib.util

from PIL import Image


SNIPPET = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "image-isolation-technique"
    / "_examples"
    / "outpaint_mask.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("outpaint_mask", SNIPPET)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_center_anchor_produces_expected_size_and_white_padding(tmp_path):
    mod = _load_module()

    src = Image.new("RGB", (100, 100), (200, 50, 50))
    src_path = tmp_path / "src.png"
    src.save(src_path)

    padded_path = tmp_path / "padded.png"
    mask_path = tmp_path / "mask.png"
    mod.pad_and_make_mask(
        src=str(src_path),
        out_image=str(padded_path),
        out_mask=str(mask_path),
        target_size=(200, 150),
        anchor="center",
    )

    padded = Image.open(padded_path)
    mask = Image.open(mask_path)
    assert padded.size == (200, 150)
    assert mask.size == (200, 150)
    # Centre anchor places the 100×100 source at offset (50, 25)
    # so pixel (0,0) is padding (mask should be white = 255)
    assert mask.getpixel((0, 0)) == 255
    # Pixel inside the source region (e.g. centre) should be preserved (black = 0)
    assert mask.getpixel((100, 75)) == 0
    # Source pixel preserved in the padded image
    assert padded.getpixel((100, 75)) == (200, 50, 50)


def test_left_anchor_places_source_at_left(tmp_path):
    mod = _load_module()
    src = Image.new("RGB", (50, 50), (0, 200, 0))
    src_path = tmp_path / "src.png"
    src.save(src_path)

    padded_path = tmp_path / "padded.png"
    mask_path = tmp_path / "mask.png"
    mod.pad_and_make_mask(
        src=str(src_path),
        out_image=str(padded_path),
        out_mask=str(mask_path),
        target_size=(200, 50),
        anchor="left",
    )

    mask = Image.open(mask_path)
    # Source flush left → mask black at (0, 25), white at (199, 25)
    assert mask.getpixel((0, 25)) == 0
    assert mask.getpixel((199, 25)) == 255


def test_target_smaller_than_source_raises(tmp_path):
    mod = _load_module()
    src = Image.new("RGB", (100, 100), (0, 0, 0))
    src_path = tmp_path / "src.png"
    src.save(src_path)
    try:
        mod.pad_and_make_mask(
            src=str(src_path),
            out_image=str(tmp_path / "out.png"),
            out_mask=str(tmp_path / "mask.png"),
            target_size=(50, 50),
            anchor="center",
        )
    except AssertionError:
        return
    raise AssertionError("expected AssertionError when target_size < source")
