# Spoteye

Paste a Spotify track or playlist link and get properly tagged audio files on your disk.

Spoteye reads the track list and metadata from the Spotify Web API, finds each song on
**YouTube Music** (ISRC first, then a fuzzy title/artist/duration match), downloads the audio with
yt-dlp, and tags it with the Spotify metadata and cover art. Playlists get their own folder with
numbered files, an `.m3u8` playlist and a `_missing.txt` for anything that couldn't be found.

It runs locally on Windows: a FastAPI backend with a React UI on `http://127.0.0.1:8000`, plus a
CLI. Personal use only; see the [legal note](#legal-note).

**Setup, requirements and troubleshooting: [SETUP.md](SETUP.md)** (Windows release and running from source).

## Features

- Track and playlist links; live progress in the browser; Stop / Resume; job history.
- **Pick match** for wrong or missing tracks (top candidates, or paste a YouTube link) and
  **Attach file** to add audio you got elsewhere.
- Playlists keep their folder across re-downloads; existing files are skipped.
- **Open folder** / **Show in folder** in Windows Explorer.
- Windows release with FFmpeg, Deno and yt-dlp bundled, and a built-in yt-dlp updater.

## Audio quality, honestly

YouTube Music only serves **lossy** streams, so no preset beats the source. FLAC/WAV output is not
offered: it would only be a bigger copy of the same lossy audio.

| Preset | What you get |
|---|---|
| `best` (default) | The original stream, no re-encode: Opus ~130-160 kbps, or AAC 256 kbps with YouTube Music Premium cookies |
| `aac256` | AAC 256 kbps `.m4a`; marked **upscaled** when re-encoded from a weaker source |
| `mp3-320` | MP3 for devices that need it; always **upscaled**, not better than `best` |
| `mp3-v0` | MP3 VBR V0, smaller than 320 with the same audible quality |

## CLI reference

From `backend` with the venv active; `python cli.py <command> --help` lists every option.

| Command | What it does |
|---|---|
| `serve [--port 8000] [--no-browser]` | Run the web UI and API |
| `login` | Sign in to Spotify (again every 6 months) |
| `info URL` / `match URL` | Show Spotify metadata / YouTube Music matches with scores |
| `download URL [--preset ...] [--out DIR] [--limit N] [--workers N] [--accept-review] [--rematch]` | Create and run a job |
| `jobs` / `job ID` / `missing ID` | Recent jobs / one job's tracks / what wasn't downloaded |
| `resume ID` / `stop ID` / `forget ID` | Retry pending and failed tracks / mark stopped / remove from history |
| `attach URL FILE [--job ID] [--copy] [--force]` | File your own audio under a Spotify track |

Tests: `python -m pytest` (backend) and `npm run build` (frontend type check + build).

## Build a release

From the repo root (needs the backend venv, Node 20+, and internet for the tool downloads):

```powershell
.\build.ps1 [-ClientId <id>] [-RefreshTools] [-SkipTests] [-SkipSmoke]
```

Produces `release\Spoteye-<VERSION>-win64.zip` and its `.sha256` (version from `VERSION`).
`-ClientId` ships a default Spotify Client ID; add each user under *User Management* in your
Spotify app.

## Project structure

```
spoteye/
├── SETUP.md                  setup, requirements, troubleshooting
├── start.ps1                 one-command start from source
├── build.ps1, VERSION        Windows release build
├── packaging/                license collector, README shipped in the zip
├── backend/
│   ├── cli.py                CLI entry point (Typer); spoteye_main.py for the packaged app
│   ├── spoteye.spec          PyInstaller spec
│   ├── app/
│   │   ├── main.py           FastAPI app; serves frontend/dist at /
│   │   ├── config.py         paths and settings (.env)
│   │   ├── commands/         CLI commands
│   │   ├── services/         Spotify, matcher, downloader, transcoder, tagger, jobs, reports
│   │   └── web/              API routers, job queue, SSE events, settings, security
│   └── tests/                pytest suite (no network)
└── frontend/src/             React + Tailwind UI
```

## Legal note

Spoteye is a personal project for personal use, licensed under the GNU GPL v3 or later ([LICENSE](LICENSE)).

- It does **not** download or decrypt anything from Spotify and does not bypass Spotify's DRM;
  it only reads metadata through the official Spotify Web API.
- The audio comes from YouTube. Downloading from YouTube may violate
  [YouTube's Terms of Service](https://www.youtube.com/t/terms); you are responsible for how you
  use this tool.
- Respect copyright: only keep music you have the right to, and don't share the files.
