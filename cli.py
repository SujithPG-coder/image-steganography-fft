"""
Command-line interface for image steganography.

Examples
--------
    python cli.py encode -i cover.png -o stego.png -m "Top secret"
    python cli.py encode -i cover.png -o stego.png -f secret.txt --method dct
    python cli.py decode -i stego.png
    python cli.py analyze -c cover.png -s stego.png -o analysis.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from stego.core import capacity, decode, encode, psnr


def cmd_encode(args: argparse.Namespace) -> None:
    message = Path(args.file).read_text(encoding="utf-8") if args.file else args.message
    if not message:
        sys.exit("error: provide a message with -m or -f")
    cover = Image.open(args.input)
    stego = encode(cover, message, args.method)
    out = Path(args.output).with_suffix(".png")       # always lossless
    stego.save(out)
    print(f"Hidden {len(message.encode('utf-8'))} bytes using {args.method.upper()} "
          f"(capacity {capacity(cover, args.method):,} bytes)")
    print(f"Saved: {out}   PSNR = {psnr(cover, stego):.2f} dB")


def cmd_decode(args: argparse.Namespace) -> None:
    print(decode(Image.open(args.input), args.method))


def cmd_analyze(args: argparse.Namespace) -> None:
    from examples.make_figures import comparison_figure
    comparison_figure(Image.open(args.cover), Image.open(args.stego), args.output)
    print(f"Saved analysis figure: {args.output}")


def main() -> None:
    p = argparse.ArgumentParser(description="Hide and recover text in images.")
    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser("encode", help="hide a message")
    e.add_argument("-i", "--input", required=True, help="cover image")
    e.add_argument("-o", "--output", required=True, help="output stego image (.png)")
    g = e.add_mutually_exclusive_group()
    g.add_argument("-m", "--message", help="message text")
    g.add_argument("-f", "--file", help="read message from a text file")
    e.add_argument("--method", choices=["lsb", "dct"], default="lsb")
    e.set_defaults(func=cmd_encode)

    d = sub.add_parser("decode", help="recover a hidden message")
    d.add_argument("-i", "--input", required=True, help="stego image")
    d.add_argument("--method", choices=["lsb", "dct"], default="lsb")
    d.set_defaults(func=cmd_decode)

    a = sub.add_parser("analyze", help="FFT comparison of cover vs stego image")
    a.add_argument("-c", "--cover", required=True)
    a.add_argument("-s", "--stego", required=True)
    a.add_argument("-o", "--output", default="analysis.png")
    a.set_defaults(func=cmd_analyze)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
