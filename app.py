"""
Image Steganography - Tkinter desktop application.

Hide a secret text message inside an image and recover it later.  The FFT
magnitude spectrum of the image is plotted before and after encoding so the
(invisible) effect of the embedding can be analysed in the frequency domain.

Run:  python app.py
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import matplotlib.pyplot as plt
from PIL import Image, ImageTk

from stego.core import capacity, decode, encode, fft_magnitude, ifft_reconstruct, psnr

BG = "#f0f0f0"
FONT = "Helvetica"
FILETYPES = [("Images", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]


def show_spectrum(img: Image.Image, title: str) -> None:
    plt.figure(figsize=(6, 6))
    plt.imshow(fft_magnitude(img), cmap="gray")
    plt.title(title)
    plt.colorbar(label="Magnitude (dB)")
    plt.axis("off")
    plt.show(block=False)


def show_ifft(img: Image.Image, title: str) -> None:
    plt.figure(figsize=(6, 6))
    plt.imshow(ifft_reconstruct(img), cmap="gray")
    plt.title(title)
    plt.axis("off")
    plt.show(block=False)


class SteganographyApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Image Steganography")
        root.geometry("720x720")
        root.configure(bg=BG)
        root.resizable(False, False)
        self.frame: tk.Frame | None = None
        self.method = tk.StringVar(value="lsb")
        self.home()

    # ------------------------------------------------------------------ utils
    def _new_frame(self) -> tk.Frame:
        if self.frame is not None:
            self.frame.destroy()
        self.frame = tk.Frame(self.root, bg=BG)
        self.frame.pack(expand=True, fill="both", padx=10, pady=10)
        return self.frame

    def _button(self, parent, text, cmd, color) -> tk.Button:
        return tk.Button(parent, text=text, command=cmd, font=(FONT, 14), bg=color,
                         fg="white", relief=tk.RAISED, padx=12, pady=6)

    def _preview(self, parent, img: Image.Image) -> None:
        thumb = img.copy()
        thumb.thumbnail((320, 220))
        photo = ImageTk.PhotoImage(thumb)
        lbl = tk.Label(parent, image=photo, bg=BG)
        lbl.image = photo
        lbl.pack(pady=5)

    def _method_selector(self, parent) -> None:
        box = tk.Frame(parent, bg=BG)
        tk.Label(box, text="Method:", bg=BG, font=(FONT, 12)).pack(side="left")
        ttk.Radiobutton(box, text="LSB (spatial, high capacity)", value="lsb",
                        variable=self.method).pack(side="left", padx=6)
        ttk.Radiobutton(box, text="DCT (frequency domain)", value="dct",
                        variable=self.method).pack(side="left", padx=6)
        box.pack(pady=8)

    # ------------------------------------------------------------------ screens
    def home(self) -> None:
        f = self._new_frame()
        tk.Label(f, text="Image Steganography", bg=BG, fg="#333",
                 font=(FONT, 34, "bold")).pack(pady=(60, 10))
        tk.Label(f, text="Hide secret messages inside images\nwith FFT-based frequency analysis",
                 bg=BG, fg="#555", font=(FONT, 14)).pack(pady=(0, 40))
        self._button(f, "Encode Image", self.encode_screen, "#4CAF50").pack(pady=15)
        self._button(f, "Decode Image", self.decode_screen, "#FF5722").pack(pady=15)

    def encode_screen(self) -> None:
        path = filedialog.askopenfilename(title="Select cover image", filetypes=FILETYPES)
        if not path:
            return
        cover = Image.open(path).convert("RGB")
        f = self._new_frame()
        tk.Label(f, text="Selected cover image", bg=BG, font=(FONT, 16)).pack()
        self._preview(f, cover)
        self._method_selector(f)
        tk.Label(f, text=f"Capacity: {capacity(cover, 'lsb'):,} bytes (LSB) / "
                         f"{capacity(cover, 'dct'):,} bytes (DCT)",
                 bg=BG, fg="#555", font=(FONT, 11)).pack()
        tk.Label(f, text="Enter the message to hide:", bg=BG, font=(FONT, 14)).pack(pady=(10, 4))
        text = tk.Text(f, width=50, height=5, font=(FONT, 12))
        text.pack()
        row = tk.Frame(f, bg=BG)
        self._button(row, "Encode & Save", lambda: self._do_encode(cover, text), "#4CAF50").pack(side="left", padx=8)
        self._button(row, "FFT Spectrum", lambda: show_spectrum(cover, "Cover image - FFT magnitude"), "#2196F3").pack(side="left", padx=8)
        self._button(row, "Back", self.home, "#E91E63").pack(side="left", padx=8)
        row.pack(pady=15)

    def _do_encode(self, cover: Image.Image, text: tk.Text) -> None:
        message = text.get("1.0", "end-1c")
        try:
            stego = encode(cover, message, self.method.get())
        except ValueError as exc:
            messagebox.showerror("Encoding failed", str(exc))
            return
        path = filedialog.asksaveasfilename(title="Save stego image", defaultextension=".png",
                                            filetypes=[("PNG (lossless)", "*.png")])
        if not path:
            messagebox.showwarning("Cancelled", "Image not saved")
            return
        if not path.lower().endswith(".png"):
            path += ".png"          # lossy formats (JPEG) would destroy the hidden data
        stego.save(path)
        messagebox.showinfo("Success", f"Message hidden and saved.\nPSNR = {psnr(cover, stego):.2f} dB")
        show_spectrum(stego, "Stego image - FFT magnitude (after encoding)")

    def decode_screen(self) -> None:
        path = filedialog.askopenfilename(title="Select stego image", filetypes=FILETYPES)
        if not path:
            return
        img = Image.open(path).convert("RGB")
        f = self._new_frame()
        tk.Label(f, text="Selected image", bg=BG, font=(FONT, 16)).pack()
        self._preview(f, img)
        self._method_selector(f)
        tk.Label(f, text="Hidden message:", bg=BG, font=(FONT, 14)).pack(pady=(10, 4))
        out = tk.Text(f, width=55, height=6, font=(FONT, 12), state="disabled")
        out.pack()

        def run() -> None:
            try:
                msg = decode(img, self.method.get())
            except ValueError as exc:
                msg = f"[No message found: {exc}]"
            out.configure(state="normal")
            out.delete("1.0", "end")
            out.insert("1.0", msg)
            out.configure(state="disabled")

        row = tk.Frame(f, bg=BG)
        self._button(row, "Decode", run, "#4CAF50").pack(side="left", padx=8)
        self._button(row, "FFT / IFFT", lambda: (show_spectrum(img, "Stego image - FFT magnitude"),
                                                 show_ifft(img, "Reconstructed image (IFFT)")),
                     "#2196F3").pack(side="left", padx=8)
        self._button(row, "Back", self.home, "#E91E63").pack(side="left", padx=8)
        row.pack(pady=15)


if __name__ == "__main__":
    root = tk.Tk()
    SteganographyApp(root)
    root.mainloop()
