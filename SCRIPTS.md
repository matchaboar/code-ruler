# Scripts

## `start.sh`

One-command launcher that starts everything needed to run Code Ruler:

1. Starts a Postgres container via **podman** (skips if already running)
2. Installs/syncs Python dependencies with `uv sync`
3. Builds the frontend (`npm install` + `npm run build`)
4. *(optional)* Runs linter (`ruff check`) and unit tests (`pytest`)
5. Launches the Rule Viewer UI at `http://127.0.0.1:8000`

```bash
./start.sh           # just launch
./start.sh --check   # lint + test, then launch
```

### Prerequisites

- [podman](https://podman.io/) installed
- [uv](https://github.com/astral-sh/uv) installed
- [Node.js / npm](https://nodejs.org/) installed
- A valid `.env` file (copy from `.env.example` and fill in credentials)

---

## `scripts/generate_video.py`

Generates an animated video from a code rule using Minimax Image-to-Video. Renders the rule as a dark-themed PNG with BAD/GOOD code examples, then submits it to the Minimax I2V API for animation.

```bash
uv run scripts/generate_video.py
```

Output files are written to `output/`:
- `rule_preview.png` — the first-frame image (1280×720)
- `rule_video.mp4` — the animated video

Edit the `CandidateRule` in the script to change the rule being visualized.

### Prerequisites

- `MINIMAX_API_KEY` set in `.env` (get one from [minimax.io](https://platform.minimax.io/))
- Video generation takes 1–3 minutes (the script polls until complete)
