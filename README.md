# pvorg-web

The web app of PP Video Organizer: browse video + gallery combinations, filter
them, and organize your library, from a local server in your browser.

**What the app does and how it looks is specified in [docs/SPEC.md](docs/SPEC.md)**,
shared unchanged with pvorg-native (macOS), pvorg-android and
pvorg-electron (Electron desktop). This README covers only building,
running and developing the web app.

## Layout

| Path | What |
|---|---|
| `backend/` | FastAPI server: scans the library, generates previews, writes `pvorg.json`, serves the API, media and the built frontend |
| `frontend/` | React + TypeScript single-page app (Vite) |
| `qa/` | Playwright screenshot tour and end-to-end checks (dev only) |
| `scripts/` | Command-line utilities and the fixture-library generator |

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- `ffmpeg` and `ffprobe` on `PATH` (contact sheets, sprites, metadata)

## Set up

```bash
cd backend
uv venv .venv
uv pip install -r requirements-dev.txt   # or requirements.txt, without the test tools

cd ../frontend
npm install
npm run build                            # type-checks, then builds into frontend/dist
```

## Run

```bash
cd backend
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. The server also serves the built frontend.

| Environment variable | Default | Purpose |
|---|---|---|
| `PVORG_CONFIG` | `~/pvorg.json` | The library's configuration file (SPEC §1.1) |
| `PVORG_CACHE_DIR` | `~/.cache/pvorg-web` | Downsized thumbnails, and the videos whose seek-preview sprite failed (retried once deleted); safe to delete |
| `PVORG_PORT` | `8000` | Port for `main.run()` and the Vite dev proxy target |

## Develop

Run the backend with reload, and Vite for the frontend (it proxies `/api` to
`PVORG_PORT`):

```bash
cd backend && .venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8000
cd frontend && npm run dev               # http://127.0.0.1:5173
```

To work against a synthetic library instead of your own:

```bash
scripts/make-fixture.sh /tmp/pvorg-web-fixture
cd backend && PVORG_CONFIG=/tmp/pvorg-web-fixture/pvorg.json .venv/bin/uvicorn main:app --port 8000
```

## Verify

```bash
cd backend && .venv/bin/python -m pytest -W error   # data rules, incl. the native compatibility sequence
cd frontend && npm run build                        # tsc -b + vite build
cd qa && npm install && npm run tour                # screenshots + end-to-end checks
```

`npm run tour` needs a built frontend and the backend venv. It never touches
`~/pvorg.json`: it builds a fixture template once (`/tmp/pvorg-web-template`),
copies it to `/tmp/pvorg-web-run` for each run, starts the backend on port
8765 against that copy, and writes screenshots of every page and state, in
Light and Dark at 1440×900 and 390×844, to `/tmp/pvorg-web-tour`. It exits
non-zero if a check fails or the browser logs any error or warning.

Options: `--out DIR`, `--only desktop-dark` (one viewport and theme),
`--no-e2e`. It uses Playwright's Chromium; if it isn't installed yet, run
`npx playwright install chromium` in `qa/` once.

## Utility scripts

Each reads `$PVORG_CONFIG` (or `~/pvorg.json`), or `--config PATH`.

```bash
backend/.venv/bin/python scripts/validate_filenames.py   # report names that don't follow studio-cast-title
backend/.venv/bin/python scripts/cleanup_orphans.py      # remove contact sheets and sprites with no video
backend/.venv/bin/python scripts/cleanup_pvorg.py        # preview stale pvorg.json entries; --yes removes them
backend/.venv/bin/python scripts/generate_tgp.py         # (re)generate contact sheets
backend/.venv/bin/python scripts/generate_sprites.py     # (re)generate seek-preview sprites and VTT
backend/.venv/bin/python scripts/reencode_videos.py      # re-encode to H.264 MP4 with fast start (keeps .bak backups)
```
