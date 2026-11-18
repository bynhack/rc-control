"""Renders the dashboard images for the P4 and converts them for LVGL.

Each asset is one hash of dash_render.html, screenshotted by headless Chrome
at its exact size, then written to main/assets/<name>.bin as raw pixels:
backgrounds as RGB565 (the panel's depth; ordered dithering so gradients
don't band), textures as ARGB8888 (LVGL's byte order: B, G, R, A).
dash_p4.c embeds the .bin files and knows their sizes.

Run:  python build_assets.py   (needs Google Chrome, Pillow, numpy and network
      access for Google Fonts)
"""

import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "main", "assets")
PAGE = "file://" + os.path.join(HERE, "dash_render.html")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# name: (width, height, format)
ASSETS = {
    "a-bg": (1024, 600, "rgb565"),
    "a-arc": (476, 476, "argb8888"),
    "a-tip": (48, 48, "argb8888"),
    "b-bg": (1024, 600, "rgb565"),
    "b-needle": (40, 262, "argb8888"),
    "b-wheel": (80, 80, "argb8888"),
}

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0 - 0.5


def render(name, w, h, png):
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
         "--default-background-color=00000000", f"--window-size={w},{h}", "--virtual-time-budget=6000",
         f"--screenshot={png}", f"{PAGE}#{name}"],
        check=True, capture_output=True)


def to_rgb565(img):
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    h, w, _ = a.shape
    d = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w][..., None]
    step = np.array([255 / 31, 255 / 63, 255 / 31], dtype=np.float32)
    q = np.clip(np.floor(a / step + 0.5 + d), 0, [31, 63, 31]).astype(np.uint16)
    px = (q[..., 0] << 11) | (q[..., 1] << 5) | q[..., 2]
    return px.astype("<u2").tobytes()


def to_argb8888(img):
    a = np.asarray(img.convert("RGBA"), dtype=np.uint8)
    return a[..., [2, 1, 0, 3]].tobytes()


def main():
    os.makedirs(OUT, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, (w, h, fmt) in ASSETS.items():
            png = os.path.join(tmp, name + ".png")
            render(name, w, h, png)
            img = Image.open(png)
            if img.size != (w, h):
                sys.exit(f"{name}: got {img.size}, wanted {(w, h)}")
            img.save(os.path.join(HERE, "preview", name + ".png")) if os.path.isdir(os.path.join(HERE, "preview")) else None
            data = to_rgb565(img) if fmt == "rgb565" else to_argb8888(img)
            path = os.path.join(OUT, name.replace("-", "_") + ".bin")
            with open(path, "wb") as f:
                f.write(data)
            print(f"{name:10s} {w}x{h} {fmt:9s} {len(data):8d} bytes")


if __name__ == "__main__":
    main()
