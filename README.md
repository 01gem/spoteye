# Spoteye

Paste a Spotify track or playlist link and get properly tagged audio files on your disk.

Spoteye reads the track list and metadata from the Spotify Web API, finds each song on
**YouTube Music** (ISRC first, then a fuzzy title/artist/duration match), downloads the audio
with yt-dlp, and tags it with the Spotify metadata and cover art. Playlists land in their own
folder with a numbered file per track, an `.m3u8` playlist and a `_missing.txt` for anything
that could not be found.

It runs locally on Windows: a FastAPI backend with a small React UI on
`http://127.0.0.1:8000`, plus a command-line interface for everything.

Personal use only. Read the [legal note](#legal-note) before using it.

## Audio quality, honestly

The audio comes from YouTube Music, which only serves **lossy** streams. Spotify's own audio is
never touched, and no preset can make a file better than its YouTube source. FLAC/WAV output is
deliberately not offered: it would only be a bigger copy of the same lossy audio.

| Preset | What you get | Re-encoded? | Use it when |
|---|---|---|---|
| `best` (default) | The original stream: Opus, usually ~130-160 kbps (`.opus`), or AAC 256 kbps (`.m4a`) when YouTube Music Premium cookies make that stream available | No, stream copy | You want the best quality YouTube has |
| `aac256` | AAC 256 kbps `.m4a` | Copied when the source already is AAC 256 (Premium cookies); otherwise re-encoded from Opus and marked **upscaled** | Your player doesn't handle Opus (e.g. older Apple devices) |
| `mp3-320` | MP3 320 kbps | Always; marked **upscaled** because the source is below 320 kbps | A device only plays MP3. A compatibility export, **not** better quality than `best` |
| `mp3-v0` | MP3 VBR V0 (~245 kbps) | Always | Same as above, smaller files |

Every re-encode of a lossy source loses a little more. If your player supports Opus, use `best`.

## Requirements

- Windows 10/11 with PowerShell
- Python 3.12+
- Node.js 20+ (only to build the web UI)
- FFmpeg: `winget install Gyan.FFmpeg`
- Deno (yt-dlp needs a JavaScript runtime for YouTube): `winget install DenoLand.Deno`
- A **Spotify Premium** account and your own app in the
  [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) in Development Mode:
  - Redirect URI: `http://127.0.0.1:8765/callback`
  - Under *User Management*, add the Spotify account you sign in with.
- Playlists must be **yours or collaborative**. Development Mode apps can't read Spotify's
  editorial or algorithmic playlists (Discover Weekly, "This Is …", Daily Mix, etc.).
  Copy the tracks into a playlist of your own first.

## Setup

```powershell
cd D:\spoteye\backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

For development, install `pip install -r requirements-dev.txt` instead.

Edit `backend\.env`:

| Key | Required | Default | Meaning |
|---|---|---|---|
| `SPOTIFY_CLIENT_ID` | yes | – | Client ID of your Spotify app |
| `SPOTIFY_REDIRECT_URI` | no | `http://127.0.0.1:8765/callback` | Must match the URI in the Spotify dashboard |
| `OUTPUT_DIR` | no | `D:\Music\Spoteye` | Where downloads go (playlists get a sub-folder) |
| `COOKIES_FILE` | no | – | Path to a `cookies.txt` exported from a browser logged in to YouTube. Helps with bot checks; with YouTube Music Premium it unlocks AAC 256k |
| `DB_PATH` | no | `backend\spoteye.db` | SQLite file for job history and the match cache (relative to `backend\`) |
| `MAX_WORKERS` | no | `3` | Parallel downloads per job |
| `MATCH_RETRY_DAYS` | no | `14` | Cached *not found* / *review* matches older than this are searched again (new uploads appear on YouTube Music over time). Real and hand-picked matches never expire |

Sign in to Spotify (opens a browser; the token is cached in `backend\.cache`):

```powershell
python cli.py login
```

Spotify limits a sign-in to **6 months**. After that the web UI shows a red
"Spotify sign-in expired" banner (amber two weeks before), and the API answers 401: run
`python cli.py login` again.

Build the web UI:

```powershell
cd D:\spoteye\frontend
npm install
npm run build
```

## Running

**One command** (builds the UI the first time, then serves UI + API and opens the browser):

```powershell
D:\spoteye\start.ps1
```

If PowerShell refuses to run scripts, use
`powershell -ExecutionPolicy Bypass -File D:\spoteye\start.ps1` (affects only that run).

**Without the script**, from `backend` with the venv active:

```powershell
python cli.py serve            # http://127.0.0.1:8000, opens a browser tab
python cli.py serve --port 8080 --no-browser
```

API docs are at `http://127.0.0.1:8000/docs`. The server listens on 127.0.0.1 only.

**Dev mode** (hot reload), in two terminals:

```powershell
cd D:\spoteye\backend; .venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
cd D:\spoteye\frontend
npm run dev    # http://localhost:5173, proxies /api to port 8000
```

### In the web UI

- Paste a link, **Preview** (shows where the files will be saved), pick a preset, **Download**.
  A playlist you downloaded before goes back into its existing folder, even if it was renamed
  on Spotify (the CLI prints "Reusing folder"; `--out` turns this off).
- Watch progress live. **Stop** (click twice) halts a job; tracks already downloading finish.
  **Resume** picks it up again; existing files are skipped.
- For a *not found*, *review* or *failed* track: **Pick match** shows the top YouTube Music candidates
  with a Listen link, or paste any YouTube / YouTube Music link. **Attach file** files your own
  audio under that track instead.
- **Open folder** / **Show in folder** open Windows Explorer.
- The trash button removes a job from the history only; files stay on disk.

## CLI reference

Run from `backend` with the venv active: `python cli.py <command> --help` for every option.

| Command | What it does |
|---|---|
| `login` | Sign in to Spotify in the browser (again every 6 months; prints the approximate date) |
| `info URL` | Show Spotify metadata for a track or playlist (also does the first sign-in) |
| `match URL` | Match tracks to YouTube Music and show scores, without downloading |
| `download URL [--preset best\|aac256\|mp3-320\|mp3-v0] [--out DIR] [--limit N] [--workers N] [--accept-review] [--rematch]` | Create a job and download it |
| `jobs` | List the 20 most recent jobs |
| `job ID` | Show every track of a job |
| `resume ID [--accept-review] [--workers N] [--rematch]` | Retry a job's pending and failed tracks |
| `stop ID` | Mark a job stuck at "running" (closed terminal) as stopped; Ctrl+C stops a running CLI job |
| `missing ID` | Print the tracks that were not downloaded (same as `_missing.txt`) |
| `attach URL FILE [--job ID] [--copy] [--force]` | Rename, tag and file your own audio file under a Spotify track |
| `forget ID` | Remove a job from the history (files and match cache stay) |
| `serve [--port 8000] [--no-browser]` | Run the web UI and API |

Tests: `python -m pytest` (backend), `npm run build` (frontend type check + build).

## Troubleshooting

Download errors are shown per track in plain words:

| Message | Fix |
|---|---|
| YouTube bot check | Export `cookies.txt` (e.g. with a "Get cookies.txt" browser extension) from a browser logged in to YouTube, set `COOKIES_FILE` in `backend\.env`, restart the server |
| YouTube refused the download (403) | `pip install -U yt-dlp` in the venv, restart |
| That YouTube Music upload is unavailable | Use **Pick match** to choose another upload |
| yt-dlp needs Deno | `winget install DenoLand.Deno`, then open a new terminal and restart |
| FFmpeg not found | `winget install Gyan.FFmpeg`, then open a new terminal |
| Network problem while downloading | Check the connection and **Resume** the job |

Keep yt-dlp current: `pip install -U yt-dlp` (YouTube changes often; most download errors are
fixed by a newer yt-dlp).

Other problems:

- **"Spotify sign-in needed"**: run `python cli.py login` (or `python cli.py info <any spotify url>`)
  once in a terminal. The server never opens a sign-in browser by itself.
- **"Spotify sign-in expired"** (red banner, API 401, or the same line from any CLI command):
  Spotify ends every sign-in after 6 months. Run `python cli.py login`, then reload the page.
- **"Can't reach Spotify"** (gray notice, API 503, or a one-line CLI error): no connection to
  Spotify right now, or Spotify itself is failing (5xx). Check the internet connection and retry;
  your sign-in is still fine, no login needed. A resumed job that hits this ends as *failed*:
  **Resume** it again once you are back online.
- **"Spotify is rate-limiting requests"** (503): too many requests in a short time. Wait a minute
  and try again.
- **"Spotify error 404: …"** (502): Spotify answered with an error for that link, e.g. the
  playlist or track was deleted.
- **400 "Invalid host header"** or **403 "Cross-site request blocked"**: open the UI at
  `http://127.0.0.1:8000` or `http://localhost:8000`. Other host names and writes from other
  websites are refused on purpose.
- **"Playlist not accessible"**: the playlist is Spotify-owned (editorial/algorithmic), private
  to someone else, or your account isn't added under *User Management* in the dashboard. Copy the
  tracks into a playlist you own.
- **"database is locked"**: another process holds the SQLite file, for example a CLI
  `download` running while the server writes, or a DB viewer with the file open. Close it and
  retry. Keep `DB_PATH` on a local disk, not in a OneDrive/network folder.
- **Header shows cookies off**: fine for most use. Set `COOKIES_FILE` if downloads hit bot checks.
- **"UI not built"** when running `serve`: `cd ..\frontend; npm run build`.

## Project structure

```
spoteye/
├── start.ps1                 one-command start
├── backend/
│   ├── cli.py                CLI entry point (Typer)
│   ├── .env.example
│   ├── app/
│   │   ├── main.py           FastAPI app, health, serves frontend/dist at /
│   │   ├── config.py         settings from .env
│   │   ├── models.py, db.py  SQLModel tables (Job, TrackRecord, MatchCache), SQLite setup
│   │   ├── commands/         CLI commands (info, match, download, jobs, attach, serve)
│   │   ├── services/         Spotify client, matcher, downloader, transcoder, tagger,
│   │   │                     pipeline, job runner/state, reports, friendly errors
│   │   └── web/              API routers (jobs, tracks, stream/SSE, files), job queue, events
│   └── tests/                pytest suite (no network: fake Spotify, matcher and downloader)
└── frontend/
    ├── vite.config.ts        dev server with /api proxy
    └── src/
        ├── App.tsx, api.ts, types.ts, youtube.ts
        ├── hooks/            live job events (SSE), finished reminder, two-click confirm
        └── components/       link form, preview, job view, track rows, match picker, history
```

## Legal note

Spoteye is a personal project for personal use.

- It does **not** download or decrypt anything from Spotify and does not bypass Spotify's DRM.
  It only reads track metadata through the official Spotify Web API.
- The audio comes from YouTube. Downloading from YouTube may violate
  [YouTube's Terms of Service](https://www.youtube.com/t/terms); you are responsible for how you
  use this tool.
- Respect copyright: only download music you have the right to keep (for example, music you
  already own or that is licensed for this use), and don't share the files.
