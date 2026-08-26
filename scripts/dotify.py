#!/usr/bin/env python3
"""
dotify.py — turn a photo into a dot-matrix SVG portrait.

Samples the image down to a grid of cells and draws one circle per cell,
sized by how bright that patch of the photo is. Supports colour output
(a single theme-agnostic SVG) or a green monochrome pair (-dark/-light,
matching the GitHub contribution-graph green) meant to sit inside a
<picture> block.

Usage:
    python scripts/dotify.py me.jpg -o assets/portrait --cols 100 --equalize --detail 0.5 --color
"""
import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageOps, ImageFilter


def parse_args():
    p = argparse.ArgumentParser(description="Convert a photo into a dot-matrix SVG portrait.")
    p.add_argument("image", help="Path to the source photo")
    p.add_argument("-o", "--out", default="assets/portrait", help="Output path prefix (no extension)")
    p.add_argument("--cols", type=int, default=88, help="Dots across (quality/size dial)")
    p.add_argument("--equalize", action="store_true", help="Histogram-equalize brightness before sampling")
    p.add_argument("--detail", type=float, default=0.0, help="Local-contrast boost, 0-1ish")
    p.add_argument("--color", action="store_true", help="Keep original colours (writes one file, no dark/light pair)")
    p.add_argument("--invert", action="store_true", help="Invert brightness (dark subject, light background)")
    p.add_argument("--circle", action="store_true", help="Mask output to a feathered circle")
    p.add_argument("--square", action="store_true", help="Crop to 1:1 before sampling")
    p.add_argument("--focus", default="0.5,0.5", help="Crop focus point as 'x,y' fractions, used with --square")
    p.add_argument("--mode", choices=["dots", "binary", "ascii", "braille"], default="dots")
    p.add_argument("--animate", action="store_true", help="Add a shimmer sweep animation (monochrome only)")
    p.add_argument("--reveal", action="store_true", help="Add a row-by-row reveal animation on load")
    p.add_argument("--reveal-time", type=float, default=2.5, help="Total reveal sweep duration, seconds")
    p.add_argument("--reveal-fade", type=float, default=0.45, help="Per-row fade-in duration, seconds")
    p.add_argument("--reveal-dir", choices=["down", "up"], default="down")
    p.add_argument("--accent", default="#39D353", help="Accent colour for the monochrome mode")
    return p.parse_args()


def load_and_prepare(path, square, focus):
    img = Image.open(path)
    # Respect an alpha channel as a subject mask if present, and use it to
    # crop out flat background before measuring brightness.
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    img = img.convert("RGBA") if has_alpha else img.convert("RGB")

    if square:
        w, h = img.size
        side = min(w, h)
        fx, fy = (float(v) for v in focus.split(","))
        cx, cy = int(w * fx), int(h * fy)
        left = max(0, min(w - side, cx - side // 2))
        top = max(0, min(h - side, cy - side // 2))
        img = img.crop((left, top, left + side, top + side))

    return img, has_alpha


def brightness_grid(img, has_alpha, cols, equalize, detail):
    w, h = img.size
    rows = max(1, round(cols * h / w))

    gray = img.convert("L") if img.mode != "RGBA" else img.convert("RGBA").split()[0:3]
    if img.mode == "RGBA":
        rgb = Image.merge("RGB", img.split()[:3])
        gray = rgb.convert("L")
        alpha = img.split()[3]
    else:
        gray = img.convert("L")
        alpha = None

    if has_alpha and alpha is not None:
        # Flatten to white where fully transparent so background doesn't
        # pollute the histogram-equalization step.
        bg = Image.new("L", gray.size, 255)
        mask = alpha.point(lambda a: 255 if a < 8 else 0)
        gray = Image.composite(bg, gray, mask)

    if equalize:
        gray = ImageOps.equalize(gray)

    if detail > 0:
        blurred = gray.filter(ImageFilter.GaussianBlur(radius=max(1, gray.size[0] // 60)))
        g_px = gray.load()
        b_px = blurred.load()
        out = Image.new("L", gray.size)
        o_px = out.load()
        for y in range(gray.size[1]):
            for x in range(gray.size[0]):
                v = g_px[x, y] + detail * (g_px[x, y] - b_px[x, y])
                o_px[x, y] = max(0, min(255, int(v)))
        gray = out

    small = gray.resize((cols, rows), Image.LANCZOS)
    small_alpha = alpha.resize((cols, rows), Image.LANCZOS) if (has_alpha and alpha is not None) else None

    if img.mode == "RGBA" and has_alpha:
        rgb_small = Image.merge("RGB", img.split()[:3]).resize((cols, rows), Image.LANCZOS)
    else:
        rgb_small = img.convert("RGB").resize((cols, rows), Image.LANCZOS)

    return small, rgb_small, small_alpha, cols, rows


def build_svg(bright, rgb, alpha, cols, rows, color, invert, circle, animate, reveal,
              reveal_time, reveal_fade, reveal_dir, accent, cell=10):
    W, H = cols * cell, rows * cell
    b_px = bright.load()
    rgb_px = rgb.load()
    a_px = alpha.load() if alpha is not None else None

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">']
    parts.append("<style>")
    if reveal:
        parts.append(f".row{{opacity:0;animation:fadeIn {reveal_fade}s ease forwards;}}")
    if animate:
        parts.append(
            "@keyframes shimmer{0%{opacity:.35}50%{opacity:1}100%{opacity:.35}}"
            ".dot{animation:shimmer 3.2s ease-in-out infinite;}"
        )
    parts.append("@keyframes fadeIn{to{opacity:1}}")
    parts.append("</style>")

    if circle:
        cx, cy, r = W / 2, H / 2, min(W, H) / 2 * 0.98
        parts.append(f'<defs><clipPath id="circleClip"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath></defs>')
        parts.append('<g clip-path="url(#circleClip)">')

    total_delay_span = reveal_time
    for ry in range(rows):
        row_group_attrs = ""
        if reveal:
            frac = ry / max(1, rows - 1)
            if reveal_dir == "up":
                frac = 1 - frac
            delay = frac * (total_delay_span - reveal_fade)
            row_group_attrs = f' class="row" style="animation-delay:{delay:.2f}s"'
        parts.append(f"<g{row_group_attrs}>")
        for rx in range(cols):
            v = b_px[rx, ry] / 255.0
            if invert:
                v = 1 - v
            # brighter pixel -> smaller dot (background), darker/mid -> bigger dot (subject detail)
            size_frac = 1 - v
            if a_px is not None and a_px[rx, ry] < 10:
                continue
            radius = (cell / 2) * 0.92 * max(0.06, min(1.0, size_frac))
            if radius < 0.35:
                continue
            cxp = rx * cell + cell / 2
            cyp = ry * cell + cell / 2
            if color:
                r, g, b = rgb_px[rx, ry]
                fill = f"rgb({r},{g},{b})"
            else:
                fill = accent
            cls = ' class="dot"' if animate else ""
            parts.append(f'<circle{cls} cx="{cxp:.1f}" cy="{cyp:.1f}" r="{radius:.2f}" fill="{fill}"/>')
        parts.append("</g>")

    if circle:
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def write_text_mode(bright, cols, rows, mode, out_prefix):
    b_px = bright.load()
    chars_ascii = " .:-=+*#%@"
    lines = []
    for ry in range(rows):
        line = []
        for rx in range(cols):
            v = b_px[rx, ry] / 255.0
            if mode == "binary":
                line.append("0" if v > 0.5 else "1")
            elif mode == "ascii":
                idx = int((1 - v) * (len(chars_ascii) - 1))
                line.append(chars_ascii[idx])
            elif mode == "braille":
                line.append("⣿" if v < 0.5 else "⠂")
        lines.append("".join(line))
    Path(f"{out_prefix}.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_prefix}.txt")


def main():
    args = parse_args()
    out_prefix = args.out
    Path(out_prefix).parent.mkdir(parents=True, exist_ok=True)

    img, has_alpha = load_and_prepare(args.image, args.square, args.focus)
    bright, rgb, alpha, cols, rows = brightness_grid(img, has_alpha, args.cols, args.equalize, args.detail)

    if args.mode != "dots":
        write_text_mode(bright, cols, rows, args.mode, out_prefix)
        return

    if args.color:
        svg = build_svg(bright, rgb, alpha, cols, rows, True, args.invert, args.circle,
                         args.animate, args.reveal, args.reveal_time, args.reveal_fade,
                         args.reveal_dir, args.accent)
        path = f"{out_prefix}.svg"
        Path(path).write_text(svg, encoding="utf-8")
        print(f"wrote {path}  ({cols}x{rows} dots)")
    else:
        for theme, accent in (("dark", args.accent), ("light", args.accent)):
            svg = build_svg(bright, rgb, alpha, cols, rows, False, args.invert, args.circle,
                             args.animate, args.reveal, args.reveal_time, args.reveal_fade,
                             args.reveal_dir, accent)
            path = f"{out_prefix}-{theme}.svg"
            Path(path).write_text(svg, encoding="utf-8")
            print(f"wrote {path}  ({cols}x{rows} dots)")


if __name__ == "__main__":
    main()
