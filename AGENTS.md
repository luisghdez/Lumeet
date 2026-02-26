# AGENTS.md

## Cursor Cloud specific instructions

### Overview

Lumeet is a recruitment dashboard + AI video generation platform with two services:

| Service | Tech | Port | Run command |
|---|---|---|---|
| Frontend | React 18 + Vite + Tailwind CSS | 5173 | `npm run dev` (from repo root) |
| Backend API | Python 3 + FastAPI + Uvicorn | 8000 | `uvicorn api:app --reload --port 8000` (from `backend/`) |

The Vite dev server proxies `/api` requests to the backend on port 8000 (configured in `vite.config.js`).

### Running services

- **Frontend**: `npm run dev` from repo root. Serves at `http://localhost:5173`.
- **Backend**: `cd backend && uvicorn api:app --reload --port 8000`. Serves at `http://localhost:8000`. Swagger docs at `/docs`.
- Both should run simultaneously for full functionality.

### Testing

- **Backend tests**: `python3 -m pytest backend/tests/ -v` (76 tests, all local, no API keys needed). Tests generate synthetic videos via FFmpeg.
- **Frontend build check**: `npm run build` (no dedicated lint or test script; the build step validates compilation).

### External API keys (for pipeline execution only)

The video generation pipeline needs `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `FAL_KEY` environment variables. These are **not** required for running the dev servers, UI, or tests — only for actual video generation jobs.

### Caveats

- Python packages install to `~/.local` (user install). Ensure `~/.local/bin` is on `PATH` (it is set in `~/.bashrc` for this environment).
- FFmpeg and ffprobe are system dependencies required by backend pipeline modules and tests.
- No ESLint or Prettier is configured; there is no dedicated lint script.
- No lockfile exists for npm — `npm install` is used (not pnpm/yarn).
