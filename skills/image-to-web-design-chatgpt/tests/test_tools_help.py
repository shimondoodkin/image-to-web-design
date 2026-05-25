"""Smoke: every tool's --help exits 0. Catches argparse regressions on copies."""
import subprocess
import sys


def _help_ok(script: str) -> None:
    r = subprocess.run(
        [sys.executable, script, "--help"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr


def test_crop_help():
    _help_ok("tools/crop.py")


def test_vision_prep_help():
    _help_ok("tools/vision_prep.py")


def test_translate_help():
    _help_ok("tools/translate.py")
