import numpy as np
import pytest
from PIL import Image

from stego.core import capacity, decode, encode, psnr


@pytest.fixture
def cover():
    rng = np.random.default_rng(0)
    return Image.fromarray(rng.integers(0, 256, (120, 160, 3), dtype=np.uint8))


@pytest.mark.parametrize("method", ["lsb", "dct"])
def test_roundtrip(cover, method, tmp_path):
    msg = "Hello, GitHub! 123 ✓"
    stego = encode(cover, msg, method)
    path = tmp_path / "stego.png"
    stego.save(path)
    assert decode(Image.open(path), method) == msg


@pytest.mark.parametrize("value", [0, 255])
@pytest.mark.parametrize("method", ["lsb", "dct"])
def test_extreme_pixels(value, method):
    img = Image.fromarray(np.full((96, 96, 3), value, dtype=np.uint8))
    assert decode(encode(img, "edge case", method), method) == "edge case"


def test_rgba_and_grayscale_inputs():
    rgba = Image.new("RGBA", (40, 40), (10, 20, 30, 128))
    gray = Image.new("L", (40, 40), 77)
    for img in (rgba, gray):
        assert decode(encode(img, "mode ok")) == "mode ok"


def test_lsb_is_imperceptible(cover):
    stego = encode(cover, "x" * 1000)
    diff = np.abs(np.asarray(cover, int) - np.asarray(stego, int))
    assert diff.max() <= 1
    assert psnr(cover, stego) > 50


def test_capacity_limit(cover):
    with pytest.raises(ValueError):
        encode(cover, "a" * (capacity(cover, "lsb") + 1))
    with pytest.raises(ValueError):
        encode(cover, "a" * (capacity(cover, "dct") + 1), "dct")


def test_empty_message(cover):
    with pytest.raises(ValueError):
        encode(cover, "")
