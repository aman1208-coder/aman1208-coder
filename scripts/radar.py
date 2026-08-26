#!/usr/bin/env python3
"""
radar.py — draw a radar/spider chart as a theme-paired SVG.

Two modes:
  --data assets/skills.json        draw a radar from hand-entered 0-100 values
  --github USERNAME                draw a radar from real language-byte counts
                                    across the user's public repos (GitHub API)

Always writes a -dark.svg and -light.svg pair so they can sit inside a
<picture> block and remain legible on both GitHub themes.

Usage:
    python scripts/radar.py --data assets/skills.json -o assets/radar
    python scripts/radar.py --github YOUR_USERNAME -o assets/radar-langs \
        --limit 7 --values --curve 0.4 --exclude "shell,makefile,dockerfile,batchfile,procfile"
"""
import argparse
import json
import math
import os
import sys
import urllib.request
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Draw a radar chart as an SVG pair.")
    p.add_argument("--data", help="Path to a JSON file with {title, axes:[{label,value}]}")
    p.add_argument("--github", help="GitHub username: build the radar from real language bytes")
    p.add_argument("-o", "--out", default="assets/radar", help="Output path prefix (no extension)")
    p.add_argument("--limit", type=int, default=7, help="Max axes for the --github mode")
    p.add_argument("--curve", type=float, default=1.0, help="Value scaling exponent (1=linear, 0.4=strong compression)")
    p.add_argument("--values", action="store_true", help="Print the numeric value next to each axis label")
    p.add_argument("--exclude", default="", help="Comma-separated languages to exclude (--github mode)")
    p.add_argument("--title", default=None)
    return p.parse_args()


def fetch_github_languages(username, exclude):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("METRICS_TOKEN")
    headers = {"User-Agent": "radar.py", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def get(url):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())

    repos = []
    page = 1
    while True:
        batch = get(f"https://api.github.com/users/{username}/repos?per_page=100&page={page}&type=owner")
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    excluded = {e.strip().lower() for e in exclude.split(",") if e.strip()}
    totals = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        try:
            langs = get(repo["languages_url"])
        except Exception:
            continue
        for lang, count in langs.items():
            if lang.lower() in excluded:
                continue
            totals[lang] = totals.get(lang, 0) + count

    return totals


def build_axes_from_totals(totals, limit, curve):
    if not totals:
        return []
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    max_val = max(v for _, v in ranked)
    axes = []
    for label, raw in ranked:
        scaled = (raw / max_val) ** curve * 100
        axes.append({"label": label, "value": round(scaled, 1), "raw": raw})
    return axes


def load_axes_from_json(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("title", "Radar"), data["axes"]


def draw_radar_svg(title, axes, theme, values_on, size=420):
    n = len(axes)
    if n < 3:
        raise SystemExit("Need at least 3 axes to draw a radar.")

    pad = 60
    canvas_w = size + pad * 2
    cx, cy = canvas_w / 2, size / 2 + 10
    max_r = size * 0.28

    is_dark = theme == "dark"
    bg = "#0d1117" if is_dark else "#ffffff"
    grid = "#30363d" if is_dark else "#d0d7de"
    text = "#c9d1d9" if is_dark else "#24292f"
    accent = "#39D353"
    fill_opacity = "0.35"

    def point(i, frac):
        angle = -math.pi / 2 + i * (2 * math.pi / n)
        r = max_r * frac
        return cx + r * math.cos(angle), cy + r * math.sin(angle)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {size + 20}" width="{canvas_w}" height="{size + 20}">',
        f'<rect x="0" y="0" width="{canvas_w}" height="{size + 20}" fill="{bg}" rx="14"/>',
        f'<text x="{cx}" y="26" text-anchor="middle" font-family="JetBrains Mono, monospace" '
        f'font-size="16" fill="{text}" font-weight="600">{title}</text>',
    ]

    # grid rings
    for ring in (0.25, 0.5, 0.75, 1.0):
        pts = " ".join(f"{point(i, ring)[0]:.1f},{point(i, ring)[1]:.1f}" for i in range(n))
        parts.append(f'<polygon points="{pts}" fill="none" stroke="{grid}" stroke-width="1"/>')

    # spokes + labels
    for i, axis in enumerate(axes):
        x, y = point(i, 1.0)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{grid}" stroke-width="1"/>')
        lx, ly = point(i, 1.16)
        anchor = "middle"
        if lx < cx - 5:
            anchor = "end"
        elif lx > cx + 5:
            anchor = "start"
        label = axis["label"]
        if values_on:
            label = f"{label} ({axis['value']:.0f})"
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-family="JetBrains Mono, monospace" '
            f'font-size="11" fill="{text}">{label}</text>'
        )

    # data polygon
    data_pts = " ".join(f"{point(i, axis['value'] / 100)[0]:.1f},{point(i, axis['value'] / 100)[1]:.1f}"
                         for i, axis in enumerate(axes))
    parts.append(f'<polygon points="{data_pts}" fill="{accent}" fill-opacity="{fill_opacity}" '
                 f'stroke="{accent}" stroke-width="2"/>')
    for i, axis in enumerate(axes):
        x, y = point(i, axis["value"] / 100)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{accent}"/>')

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    args = parse_args()
    if args.data:
        title, axes = load_axes_from_json(args.data)
    elif args.github:
        try:
            totals = fetch_github_languages(args.github, args.exclude)
        except Exception as e:
            print(f"warning: GitHub API call failed ({e}); this is usually a rate limit — "
                  f"set GITHUB_TOKEN/METRICS_TOKEN. Writing a placeholder radar instead.", file=sys.stderr)
            totals = {}
        axes = build_axes_from_totals(totals, args.limit, args.curve)
        title = args.title or "Language Radar"
        if not axes:
            axes = [{"label": "no data yet", "value": 0} for _ in range(3)]
    else:
        raise SystemExit("Pass either --data <skills.json> or --github <username>")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        svg = draw_radar_svg(title, axes, theme, args.values)
        path = f"{args.out}-{theme}.svg"
        Path(path).write_text(svg, encoding="utf-8")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
