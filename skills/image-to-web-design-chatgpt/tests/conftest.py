"""Pytest fixtures for image-to-web-design-chatgpt tests."""
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture(autouse=True)
def _chdir_to_skill_root(monkeypatch):
    """Run each test with cwd = skills/image-to-web-design-chatgpt/ so the
    `tools/vision_prep.py`-style relative paths resolve regardless of
    where pytest was launched from.
    """
    skill_root = Path(__file__).resolve().parent.parent
    monkeypatch.chdir(skill_root)


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


def make_image(path, size, color="white"):
    Image.new("RGB", size, color).save(path)
    return path
