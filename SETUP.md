# Setup — from this folder to a live profile

This zip already has your portrait, radars, stat card, and project cards
generated once (from your resume + photo) so you can see the result
immediately. Here's how to take it from "files in VS Code" to "live on
github.com/aman1208-coder".

## 0. Open it in VS Code

Unzip this folder, then `File → Open Folder…` and pick it. Open a terminal
inside VS Code (`` Ctrl+` ``) for every command below.

## 1. Look at what you already have

Open `preview.html` right-click → **Open with Live Server** (or just double
click it) to see every generated asset before anything touches GitHub.

## 2. Create the magic repo

On GitHub: **New repository**, name it **exactly** `aman1208-coder` (your
username), Public, no README (this folder already has one).

## 3. Point this folder at it

```bash
git init
git branch -M main
git add -A
git commit -m "profile readme"
git remote add origin https://github.com/aman1208-coder/aman1208-coder.git
git push -u origin main
```

## 4. Turn the automation on

In the new repo on GitHub:

1. **Settings → Actions → General → Workflow permissions → Read and write
   permissions → Save.** Without this, the workflows can generate files but
   can't commit them back.
2. **Get a classic token:** [github.com/settings/tokens](https://github.com/settings/tokens)
   → **Generate new token (classic)** → tick `read:user` (and `repo` if you
   want private contributions counted) → copy it.
3. **Settings → Secrets and variables → Actions → New repository secret** →
   name it exactly `METRICS_TOKEN` → paste the token.

   ⚠️ It must be a **classic** token — a fine-grained one won't work with the
   metrics workflow.

## 5. Run the three workflows once by hand

**Actions** tab → you may see a banner to enable workflows on a fresh repo,
click through it → open each workflow (`metrics`, `snake`, `charts-and-cards`)
→ **Run workflow**. First runs take a couple of minutes, `metrics` the
longest.

After that, they run themselves on schedule (metrics every 6h, snake every
12h, charts-and-cards daily) — nothing left to do.

## 6. Make it yours

The generated art gets four seconds of attention; the words get read. Before
you call it done:

- Rewrite the `whoami` bullets in `README.md` — they're written in your
  voice already, but check they're still true next month
- Edit `assets/skills.json` if your self-rating on anything is off
- Add/replace repos in `assets/projects.json` as your portfolio changes —
  four is the max the grid is built for
- Check your profile in **both** GitHub themes (Settings → Appearance) and
  on your phone

## Regenerating locally (optional)

Only needed if you want to preview a change before pushing — the GitHub
Actions do this automatically on their schedule.

```bash
pip install pillow

# portrait (swap me.jpg for your own photo if you replace it)
python scripts/dotify.py me_source.png -o assets/portrait --cols 100 --equalize --detail 0.5 --color --circle
python scripts/dotify.py me_source.png -o assets/portrait-mono --cols 88 --equalize --detail 0.5 --circle

# self-rated radar
python scripts/radar.py --data assets/skills.json -o assets/radar --values

# language radar (needs a token locally or you'll hit GitHub's anonymous rate limit)
export GITHUB_TOKEN=ghp_your_classic_token
python scripts/radar.py --github aman1208-coder -o assets/radar-langs --limit 7 --values --curve 0.4 \
  --exclude "shell,makefile,dockerfile,batchfile,procfile"

# stat + project cards
python scripts/cards.py --user aman1208-coder --out assets
```

## If something breaks

| Symptom | Cause |
|---|---|
| Images broken for everyone but you | Repo is private — make it public |
| Images broken for you too | Not pushed yet — relative paths only resolve on `main` |
| Snake image 404s | Normal until the `snake` workflow finishes its first run |
| `metrics` workflow fails | `METRICS_TOKEN` missing, wrong name, expired, or not classic |
| Workflow runs but nothing changes | Workflow permissions still read-only — step 4.1 |
| Radar/stat card shows zeros | Hit GitHub's anonymous rate limit — add `METRICS_TOKEN` |
| A chart looks invisible | You're viewing the theme it wasn't meant for — check the `<picture>` block has both `source` tags |

## What's in here

```
README.md                    the profile page itself
preview.html                 local viewer for every generated asset
scripts/dotify.py            photo -> dot-matrix portrait SVG
scripts/radar.py             skill radar (from assets/skills.json) + live language radar
scripts/cards.py             self-hosted stat card + project cards, live from the GitHub API
assets/skills.json           your self-rated radar values — edit this
assets/projects.json         which repos get a project card — edit this
assets/*.svg                 already-generated output, ready to push as-is
.github/workflows/           metrics.yml, snake.yml, radar.yml — the automation
.gitattributes                keeps line endings sane so the workflows don't choke
```
