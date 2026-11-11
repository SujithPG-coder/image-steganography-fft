"""
Core steganography and frequency-analysis routines.

Two embedding methods are provided:

* ``lsb``  - spatial-domain Least Significant Bit embedding.  Every byte of the
  message is stored in the LSBs of 3 consecutive pixels (9 RGB values): 8
  values carry the data bits and the 9th value is a *continue/stop* flag
  (even = more data follows, odd = last byte).  High capacity, invisible to
  the eye (max. change of 1 intensity level).

* ``dct``  - frequency-domain embedding.  The blue channel is split into 8x8
  blocks, each block is transformed with the 2-D DCT and one mid-frequency
  coefficient is quantised (Quantisation Index Modulation) to carry one bit.
  Lower capacity but the data lives in the frequency components, as described
  in the project objectives.

FFT / IFFT helpers are used to visualise the magnitude spectrum of the cover
and stego images and to show that embedding leaves the spectrum unchanged.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy.fft import dctn, idctn

__all__ = [
    "encode", "decode", "capacity", "lsb_encode", "lsb_decode", "dct_encode",
    "dct_decode", "fft_magnitude", "ifft_reconstruct", "mse", "psnr",
]

# --------------------------------------------------------------------------- #
# Utilities
# --------------------------------------------------------------------------- #

def _to_rgb(img: Image.Image) -> Image.Image:
    """Ensure a 3-channel 8-bit RGB image (handles RGBA, palette, grayscale)."""
    return img if img.mode == "RGB" else img.convert("RGB")


def capacity(img: Image.Image, method: str = "lsb") -> int:
    """Maximum number of message *bytes* that fit in ``img``."""
    w, h = img.size
    if method == "lsb":
        return (w * h) // 3
    if method == "dct":
        return max(((w // 8) * (h // 8) - _HEADER_BITS) // 8, 0)
    raise ValueError(f"unknown method '{method}'")


# --------------------------------------------------------------------------- #
# Spatial-domain LSB
# --------------------------------------------------------------------------- #

def lsb_encode(img: Image.Image, message: str) -> Image.Image:
    """Hide ``message`` (UTF-8) in the LSBs of the image pixels."""
    if not message:
        raise ValueError("message is empty")
    data = message.encode("utf-8")
    img = _to_rgb(img)
    if len(data) > capacity(img, "lsb"):
        raise ValueError(f"message too long: {len(data)} bytes, image holds "
                         f"{capacity(img, 'lsb')} bytes")

    arr = np.array(img, dtype=np.uint8)
    flat = arr.reshape(-1)                       # R,G,B,R,G,B,...
    for i, byte in enumerate(data):
        base = 9 * i
        bits = [(byte >> (7 - b)) & 1 for b in range(8)]
        bits.append(1 if i == len(data) - 1 else 0)   # stop flag
        for k, bit in enumerate(bits):
            flat[base + k] = (flat[base + k] & 0xFE) | bit
    return Image.fromarray(flat.reshape(arr.shape), "RGB")


def lsb_decode(img: Image.Image) -> str:
    """Recover a message hidden with :func:`lsb_encode`."""
    flat = np.array(_to_rgb(img), dtype=np.uint8).reshape(-1)
    out = bytearray()
    for base in range(0, len(flat) - 8, 9):
        vals = flat[base:base + 9]
        byte = 0
        for v in vals[:8]:
            byte = (byte << 1) | (int(v) & 1)
        out.append(byte)
        if vals[8] & 1:
            break
    return out.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# Frequency-domain DCT-QIM
# --------------------------------------------------------------------------- #

_BLOCK = 8
_COEF = (3, 4)          # mid-frequency coefficient used to carry the bit
_STEP = 30.0            # quantisation step (robust against uint8 rounding)
_HEADER_BITS = 32       # message length in bytes


def _bits_from_bytes(data: bytes) -> list[int]:
    return [(b >> (7 - i)) & 1 for b in data for i in range(8)]


def dct_encode(img: Image.Image, message: str) -> Image.Image:
    """Embed one bit per 8x8 block in a mid-frequency DCT coefficient of the
    blue channel using Quantisation Index Modulation."""
    if not message:
        raise ValueError("message is empty")
    data = message.encode("utf-8")
    img = _to_rgb(img)
    if len(data) > capacity(img, "dct"):
        raise ValueError(f"message too long: {len(data)} bytes, image holds "
                         f"{capacity(img, 'dct')} bytes in DCT mode")
    bits = _bits_from_bytes(len(data).to_bytes(4, "big") + data)

    arr = np.array(img, dtype=np.float64)
    ch = arr[:, :, 2].copy()
    h, w = ch.shape
    k = 0
    for by in range(0, h - h % _BLOCK, _BLOCK):
        for bx in range(0, w - w % _BLOCK, _BLOCK):
            if k >= len(bits):
                break
            # keep the block away from saturation so clipping to 0..255 after
            # the inverse DCT cannot destroy the embedded bit
            pix = np.clip(ch[by:by + _BLOCK, bx:bx + _BLOCK], 6, 249)
            block = dctn(pix, norm="ortho")
            c = block[_COEF]
            q = np.round((c - bits[k] * _STEP / 2) / _STEP) * _STEP + bits[k] * _STEP / 2
            block[_COEF] = q
            ch[by:by + _BLOCK, bx:bx + _BLOCK] = idctn(block, norm="ortho")
            k += 1
    out = arr.copy()
    out[:, :, 2] = ch
    return Image.fromarray(np.clip(np.round(out), 0, 255).astype(np.uint8), "RGB")


def dct_decode(img: Image.Image) -> str:
    """Recover a message hidden with :func:`dct_encode`."""
    ch = np.array(_to_rgb(img), dtype=np.float64)[:, :, 2]
    h, w = ch.shape
    bits: list[int] = []
    needed = None
    for by in range(0, h - h % _BLOCK, _BLOCK):
        for bx in range(0, w - w % _BLOCK, _BLOCK):
            c = dctn(ch[by:by + _BLOCK, bx:bx + _BLOCK], norm="ortho")[_COEF]
            r = (c / (_STEP / 2)) % 2           # even multiple -> 0, odd -> 1
            bits.append(1 if 0.5 <= r < 1.5 else 0)
            if needed is None and len(bits) == _HEADER_BITS:
                length = int("".join(map(str, bits)), 2)
                if length > capacity(img, "dct"):
                    raise ValueError("no DCT-encoded message found")
                needed = _HEADER_BITS + 8 * length
            if needed is not None and len(bits) >= needed:
                payload = bits[_HEADER_BITS:needed]
                data = bytes(int("".join(map(str, payload[i:i + 8])), 2)
                             for i in range(0, len(payload), 8))
                return data.decode("utf-8", errors="replace")
    raise ValueError("no DCT-encoded message found")


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #

def encode(img: Image.Image, message: str, method: str = "lsb") -> Image.Image:
    return {"lsb": lsb_encode, "dct": dct_encode}[method](img, message)


def decode(img: Image.Image, method: str = "lsb") -> str:
    return {"lsb": lsb_decode, "dct": dct_decode}[method](img)


# --------------------------------------------------------------------------- #
# FFT analysis and quality metrics
# --------------------------------------------------------------------------- #

def fft_magnitude(img: Image.Image) -> np.ndarray:
    """Centred log-magnitude spectrum (dB) of the grayscale image."""
    g = np.asarray(img.convert("L"), dtype=np.float64)
    spectrum = np.fft.fftshift(np.fft.fft2(g))
    return 20 * np.log10(np.abs(spectrum) + 1)


def ifft_reconstruct(img: Image.Image) -> np.ndarray:
    """FFT followed by IFFT - reconstructs the grayscale image from its spectrum."""
    g = np.asarray(img.convert("L"), dtype=np.float64)
    return np.abs(np.fft.ifft2(np.fft.fft2(g)))


def mse(a: Image.Image, b: Image.Image) -> float:
    x = np.asarray(_to_rgb(a), dtype=np.float64)
    y = np.asarray(_to_rgb(b), dtype=np.float64)
    return float(np.mean((x - y) ** 2))


def psnr(a: Image.Image, b: Image.Image) -> float:
    """Peak Signal-to-Noise Ratio in dB (higher = less visible distortion)."""
    m = mse(a, b)
    return float("inf") if m == 0 else 10 * np.log10(255.0 ** 2 / m)
