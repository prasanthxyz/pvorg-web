# pvorg - Personal Video + Gallery Organizer

Local web application for browsing video + gallery combinations with a FastAPI backend and React frontend.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- `ffmpeg` and `ffprobe`

## Setup

### Backend

```bash
cd backend
uv venv .venv
uv pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
npm run build
```

### Config

Create `~/pvorg.json`:

```json
{
  "videosPath": "/path/to/videos",
  "galleriesPath": "/path/to/galleries",
  "tags": [],
  "videoRelations": {}
}
```

Video filenames must follow a strict lowercase format with no spaces:

`studio-cast1[,cast2,...]-title.ext`

Examples:

- `unknown-unknown-party.time.mp4`
- `studio-cast-title.mp4`

## Run

```bash
cd backend
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Development

Backend:

```bash
cd backend
.venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173).

## UI Pages

- `/` Viewer
- `/config` Filters/configuration
- `/deleter` Video deleter
- `/mapper` Video-gallery mapper
- `/tag-mapper` Video-tag mapper

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `v` | Viewer page |
| `c` | Config page |
| `p` | Toggle TGP / Video |
| `b` | Previous combination |
| `n` | Next combination |
| `Space` | Play / Pause (video mode) |
| `0`-`9` | Seek to 0%-90% |
| `Left` / `Right` | Seek -10s / +10s |

## Utility Scripts

All scripts default to `~/pvorg.json` and support `--config`.

```bash
# Validate video naming
python scripts/validate_filenames.py

# Remove orphan sprite/TGP assets
python scripts/cleanup_orphans.py

# Remove stale videoRelations from pvorg.json
python scripts/cleanup_pvorg.py

# Generate sprite sheets + VTT
python scripts/generate_sprites.py

# Generate TGP contact sheets
python scripts/generate_tgp.py

# Re-encode videos (creates .bak backups)
python scripts/reencode_videos.py
```

## Startup Behavior

On startup/reload, backend runs:

1. Filename scan/validation
2. Config normalization
3. Orphan cleanup
4. Stale pvorg cleanup
5. Preprocessing (TGP + sprite + metadata)

If preprocessing fails, the backend process exits.
