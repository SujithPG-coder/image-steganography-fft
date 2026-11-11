"""Generate the demo figures shown in the README.

    python -m examples.make_figures
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from stego.core import encode, fft_magnitude, psnr

ROOT = Path(__file__).resolve().parents[1]


def comparison_figure(cover: Image.Image, stego: Image.Image, out: str | Path,
                      title: str = "") -> None:
    cover, stego = cover.convert("RGB"), stego.convert("RGB")
    diff = np.abs(np.asarray(cover, float) - np.asarray(stego, float)).sum(axis=2)
    fig, ax = plt.subplots(2, 3, figsize=(15, 9))
    ax[0, 0].imshow(cover); ax[0, 0].set_title("Cover image")
    ax[0, 1].imshow(stego); ax[0, 1].set_title(f"Stego image (PSNR {psnr(cover, stego):.1f} dB)")
    im = ax[0, 2].imshow(diff, cmap="magma"); ax[0, 2].set_title("|Cover - Stego| (pixel change)")
    fig.colorbar(im, ax=ax[0, 2], fraction=0.046)
    ax[1, 0].imshow(fft_magnitude(cover), cmap="gray"); ax[1, 0].set_title("FFT magnitude - cover")
    ax[1, 1].imshow(fft_magnitude(stego), cmap="gray"); ax[1, 1].set_title("FFT magnitude - stego")
    sd = np.abs(fft_magnitude(cover) - fft_magnitude(stego))
    im = ax[1, 2].imshow(sd, cmap="inferno"); ax[1, 2].set_title("Spectrum difference (dB)")
    fig.colorbar(im, ax=ax[1, 2], fraction=0.046)
    for a in ax.ravel():
        a.axis("off")
    if title:
        fig.suptitle(title, fontsize=15)
    fig.tight_layout()
    fig.savefig(out, dpi=100)
    plt.close(fig)


if __name__ == "__main__":
    from skimage import data   # sample image (CC0) from scikit-image

    out_dir = ROOT / "docs" / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    cover = Image.fromarray(data.coffee())
    cover.save(ROOT / "examples" / "cover.png")
    secret = ("Steganography hides the very existence of a message. "
              "This text is invisible to the eye but fully recoverable. ") * 40
    for method in ("lsb", "dct"):
        msg = secret if method == "lsb" else secret[:400]
        stego = encode(cover, msg, method)
        stego.save(ROOT / "examples" / f"stego_{method}.png")
        comparison_figure(cover, stego, out_dir / f"analysis_{method}.png",
                          f"{method.upper()} embedding - {len(msg.encode())} bytes hidden")
        print(method, f"PSNR = {psnr(cover, stego):.2f} dB")
