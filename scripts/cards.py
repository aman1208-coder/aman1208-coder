#!/usr/bin/env python3
"""
cards.py — draw a stat card and a set of project cards as static SVGs,
committed into the repo instead of loaded from someone else's server.

Pulls stars / forks / language live from the GitHub REST API when it runs,
so the numbers track reality on whatever schedule the workflow uses —
without depending on a shared third-party server that can 503 on you.

Usage:
    python scripts/cards.py --user YOUR_USERNAME --out assets
"""
import argparse
import html
import json
import os
import urllib.request
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Generate self-hosted stat + project card SVGs.")
    p.add_argument("--user", required=True)
    p.add_argument("--out", default="assets")
    p.add_argument("--projects", default="assets/projects.json")
    return p.parse_args()


def gh_headers():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("METRICS_TOKEN")
    headers = {"User-Agent": "cards.py", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers, bool(token)


def gh_get(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def fetch_user_totals(username, headers):
    repos, page = [], 1
    while True:
        batch = gh_get(f"https://api.github.com/users/{username}/repos?per_page=100&page={page}", headers)
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    stars = sum(r.get("stargazers_count", 0) for r in repos)
    forks = sum(r.get("forks_count", 0) for r in repos)
    public_repos = len([r for r in repos if not r.get("fork")])
    return {"stars": stars, "forks": forks, "public_repos": public_repos}


def fetch_repo(username, repo, headers):
    try:
        return gh_get(f"https://api.github.com/repos/{username}/{repo}", headers)
    except Exception as e:
        print(f"warning: couldn't fetch {username}/{repo} ({e}); using placeholder values", flush=True)
        return {}


def stat_card_svg(username, totals, has_token, six_tiles_extra=None, theme="dark"):
    is_dark = theme == "dark"
    bg = "#0d1117" if is_dark else "#ffffff"
    border = "#30363d" if is_dark else "#d0d7de"
    text = "#c9d1d9" if is_dark else "#24292f"
    accent = "#39D353"
    W, H = 460, 150 if not six_tiles_extra else 190

    tiles = [
        ("★ Stars", totals["stars"]),
        ("Forks", totals["forks"]),
        ("Public Repos", totals["public_repos"]),
    ]
    if six_tiles_extra:
        tiles += [
            ("Contributions", six_tiles_extra.get("contributions", "—")),
            ("Current Streak", six_tiles_extra.get("streak", "—")),
            ("Longest Streak", six_tiles_extra.get("longest_streak", "—")),
        ]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="12" fill="{bg}" stroke="{border}"/>',
        f'<text x="24" y="34" font-family="JetBrains Mono, monospace" font-size="15" font-weight="700" '
        f'fill="{text}">{html.escape(username)}</text>',
        f'<text x="24" y="52" font-family="JetBrains Mono, monospace" font-size="10" fill="{border}">'
        f'{"live totals" if has_token else "live totals (basic — add METRICS_TOKEN for streaks)"}</text>',
    ]

    cols = 3
    tile_w = (W - 48) / cols
    for i, (label, value) in enumerate(tiles):
        row, col = divmod(i, cols)
        x = 24 + col * tile_w
        y = 72 + row * 58
        parts.append(f'<text x="{x:.0f}" y="{y:.0f}" font-family="JetBrains Mono, monospace" '
                     f'font-size="20" font-weight="700" fill="{accent}">{value}</text>')
        parts.append(f'<text x="{x:.0f}" y="{y+16:.0f}" font-family="JetBrains Mono, monospace" '
                     f'font-size="10" fill="{text}">{html.escape(label)}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def project_card_svg(repo_meta, override_desc, theme="dark"):
    is_dark = theme == "dark"
    bg = "#0d1117" if is_dark else "#ffffff"
    border = "#30363d" if is_dark else "#d0d7de"
    text = "#c9d1d9" if is_dark else "#24292f"
    subtext = "#8b949e" if is_dark else "#57606a"
    accent = "#39D353"
    W, H = 420, 150

    name = repo_meta.get("name", "repo")
    desc = override_desc or repo_meta.get("description") or ""
    stars = repo_meta.get("stargazers_count", 0)
    forks = repo_meta.get("forks_count", 0)
    lang = repo_meta.get("language") or "—"

    # naive word-wrap for the description into up to 3 lines
    words = desc.split()
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if len(trial) > 46:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    lines = lines[:3]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="12" fill="{bg}" stroke="{border}"/>',
        f'<text x="20" y="32" font-family="JetBrains Mono, monospace" font-size="16" font-weight="700" '
        f'fill="{accent}">{html.escape(name)}</text>',
    ]
    y = 54
    for line in lines:
        parts.append(f'<text x="20" y="{y}" font-family="JetBrains Mono, monospace" font-size="11" '
                     f'fill="{text}">{html.escape(line)}</text>')
        y += 16

    parts.append(f'<text x="20" y="{H-18}" font-family="JetBrains Mono, monospace" font-size="10" '
                 f'fill="{subtext}">⬤ {html.escape(lang)}   ★ {stars}   ⑂ {forks}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def main():
    args = parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    headers, has_token = gh_headers()

    try:
        totals = fetch_user_totals(args.user, headers)
    except Exception as e:
        print(f"warning: couldn't reach GitHub API ({e}); writing zeroed stat card", flush=True)
        totals = {"stars": 0, "forks": 0, "public_repos": 0}

    for theme in ("dark", "light"):
        svg = stat_card_svg(args.user, totals, has_token, theme=theme)
        (out / f"stats-{theme}.svg").write_text(svg, encoding="utf-8")
        print(f"wrote {out / f'stats-{theme}.svg'}")

    proj_path = Path(args.projects)
    if not proj_path.exists():
        print(f"no {proj_path} found — skipping project cards")
        return

    projects = json.loads(proj_path.read_text(encoding="utf-8")).get("projects", [])
    for proj in projects:
        repo = proj["repo"]
        meta = fetch_repo(args.user, repo, headers)
        meta.setdefault("name", repo)
        for theme in ("dark", "light"):
            svg = project_card_svg(meta, proj.get("description"), theme=theme)
            path = out / f"card-{repo.lower()}-{theme}.svg"
            path.write_text(svg, encoding="utf-8")
            print(f"wrote {path}")


if __name__ == "__main__":
    main()
