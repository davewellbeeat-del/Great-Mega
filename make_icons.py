"""Regenerate the app icons (optional dev tool; needs Pillow: pip install pillow).

Draws a dark crown on a gold square and writes everything the app needs into static/icons/.
"""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "static" / "icons"
GOLD, INK = (247, 195, 49, 255), (27, 19, 0, 255)


def crown(size: int, scale: float, background: str) -> Image.Image:
    """background: 'rounded' (transparent corners), 'square' (full bleed)."""
    ss = 4                                   # supersample for smooth edges
    s = size * ss
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if background == "rounded":
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=GOLD)
    else:
        d.rectangle([0, 0, s, s], fill=GOLD)

    def p(x, y):                             # crown drawn in a 0-100 box, centred, then scaled
        return (s / 2 + (x - 50) * s / 100 * scale, s / 2 + (y - 53.5) * s / 100 * scale)

    d.polygon([p(22, 68), p(17, 34), p(36, 52), p(50, 27), p(64, 52), p(83, 34), p(78, 68)], fill=INK)
    for cx, cy in ((17, 33), (50, 25), (83, 33)):
        (x0, y0), (x1, y1) = p(cx - 4.5, cy - 4.5), p(cx + 4.5, cy + 4.5)
        d.ellipse([x0, y0, x1, y1], fill=INK)
    d.rounded_rectangle([*p(22, 72), *p(78, 82)], radius=int(s * 0.012), fill=INK)
    return img.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    crown(192, 1.0, "rounded").save(OUT / "icon-192.png")
    crown(512, 1.0, "rounded").save(OUT / "icon-512.png")
    crown(512, 0.78, "square").save(OUT / "maskable-512.png")       # Android adaptive icons crop to a circle
    crown(180, 0.9, "square").save(OUT / "apple-touch-icon.png")    # iPhone rounds the corners itself
    crown(256, 1.0, "rounded").save(OUT / "app.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
