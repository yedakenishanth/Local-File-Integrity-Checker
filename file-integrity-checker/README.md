# Ledger — File Integrity Checker

Two versions of the same idea: hash a folder's files with SHA-256, save that as a baseline, and later detect anything new, changed, or missing.

- **`file_integrity_checker.py`** — desktop GUI (Python + Tkinter)
- **`web/`** — browser version with a live demo hosted on GitHub Pages

## Live demo

**https://YOUR-USERNAME.github.io/file-integrity-checker/web/**
*(replace `YOUR-USERNAME` after you push — see "Enable the live demo" below)*

The web version runs entirely client-side: files are hashed in your browser using the Web Crypto API, and the baseline is stored in `localStorage`. Nothing is uploaded anywhere. Because of browser security restrictions, it can't read full OS file paths or arbitrary background changes to disk — you re-select the folder each time you want to audit it.

## Desktop version

### Requirements
- Python 3.8+
- Tkinter (`sudo apt install python3-tk` on Linux if it's not already present)

No external dependencies.

### Usage
```bash
python3 file_integrity_checker.py
```
1. **Browse** to the folder you want to monitor.
2. Click **"1. Create Baseline"** to hash every file and save a snapshot.
3. Later, click **"2. Run Integrity Check"** to re-scan and compare against that snapshot.
4. Review the color-coded log: new, modified, deleted, or unreadable files.

### Features
- Recursive SHA-256 hashing, read in 8KB chunks
- Background-thread scanning so the UI doesn't freeze on large folders
- Unreadable files (permissions, etc.) are reported distinctly, not misflagged as "modified"
- Confirms before overwriting an existing baseline
- Automatically excludes its own baseline file from the scan

## Web version

### Run it locally
No build step — it's a static page.
```bash
cd web
python3 -m http.server 8000
# open http://localhost:8000
```
(A plain `file://` open also works in most browsers, but a local server avoids edge cases with the folder picker.)

### Enable the live demo (GitHub Pages)
After pushing this repo to GitHub:
1. Go to your repo → **Settings → Pages**
2. Under **Source**, choose **Deploy from a branch**
3. Branch: `main`, folder: `/ (root)` — or `/web` if your GitHub Pages settings allow choosing a subfolder
4. Save. GitHub gives you a URL like `https://YOUR-USERNAME.github.io/file-integrity-checker/`
5. If you deployed from root, your demo is at `.../web/`; update the link at the top of this README to match

### How it works
- `webkitdirectory` on a file input lets you pick a whole folder
- Each file is hashed with `crypto.subtle.digest('SHA-256', ...)`
- The baseline (`{ relativePath: hash }`) is saved to `localStorage`
- On audit, the current scan is diffed against the baseline both ways: new/changed files, and baseline entries no longer present
- Each file gets a small generated "fingerprint" bar code, drawn from its own hash bytes

## Push this repo to GitHub

```bash
git init
git add .
git commit -m "Add file integrity checker (desktop + web)"
gh auth login
gh repo create file-integrity-checker --public --source=. --push
```

Then follow "Enable the live demo" above to turn on Pages.

## License

MIT (or update to whatever you prefer).
