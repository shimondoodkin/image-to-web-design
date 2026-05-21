"""Pytest fixtures for image-cut tests."""
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture(autouse=True)
def _chdir_to_skill_root(monkeypatch):
    """Run each image-cut test with cwd = skills/image-cut/ so the existing
    relative paths in the tests (e.g. subprocess.run(['tools/crop.py', ...]))
    resolve correctly regardless of where pytest was launched from.
    """
    skill_root = Path(__file__).resolve().parent.parent
    monkeypatch.chdir(skill_root)


@pytest.fixture
def tmp_dir(tmp_path):
    """Return a Path for temporary test artifacts."""
    return tmp_path


@pytest.fixture
def sample_image(tmp_dir):
    """Create a 200x100 RGB image with a known pattern.

    Pattern: red top-half, blue bottom-half, with a single green pixel at (50, 25).
    """
    img = Image.new("RGB", (200, 100), "red")
    for y in range(50, 100):
        for x in range(200):
            img.putpixel((x, y), (0, 0, 255))
    img.putpixel((50, 25), (0, 255, 0))
    path = tmp_dir / "sample.png"
    img.save(path)
    return path


@pytest.fixture
def large_image(tmp_dir):
    """Create a 2000x1500 image — non-vision-safe (long edge > 1568)."""
    img = Image.new("RGB", (2000, 1500), "white")
    path = tmp_dir / "large.png"
    img.save(path)
    return path


@pytest.fixture
def portrait_image(tmp_dir):
    """Create a 600x900 image — portrait orientation."""
    img = Image.new("RGB", (600, 900), "white")
    path = tmp_dir / "portrait.png"
    img.save(path)
    return path
