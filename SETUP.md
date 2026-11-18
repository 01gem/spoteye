# Spoteye setup guide

Spoteye turns a Spotify track or playlist link into tagged audio files. Spotify provides the track
list and tags; the audio comes from YouTube Music. This guide covers the Windows release
(Part 1) and running from source for development (Part 2).

---

## Part 1: Windows release

### Requirements

| Requirement | Details |
| --- | --- |
| Windows | Windows 10 or 11, 64-bit |
| Disk space | About 0.5 GB for the app, plus room for your music |
| Spotify account | **Premium** is required by Spotify for developer apps |
| Spotify developer app | Free; you create it once (step 3). Or use someone else's app if they add you (see the note in step 3) |
| Internet + a web browser | Spoteye runs in your browser at `http://127.0.0.1:8000` |
| Optional: YouTube cookies | Only if downloads hit YouTube "bot check" errors (see Troubleshooting) |

You do **not** need Python, Node, FFmpeg or anything else: FFmpeg, Deno and yt-dlp are bundled.

### 1. Download and check the zip

1. Download `Spoteye-<version>-win64.zip` (and the `.sha256` file) from the GitHub release.
2. Optional, to check that the download is intact, in PowerShell:

   ```powershell
   Get-FileHash .\Spoteye-1.0.0-win64.zip -Algorithm SHA256
   ```

   The hash must match the one in the release notes / the `.sha256` file.

### 2. Unzip and start

1. Unzip to a folder you can write to, for example `%LOCALAPPDATA%\Programs\Spoteye`.
   Do **not** use `C:\Program Files`: the built-in yt-dlp updater needs to write to the app folder.
2. Double-click `Spoteye.exe`.
   - Windows SmartScreen may say it protected your PC: click **More info** -> **Run anyway**.
   - A console window opens (that is the app running) and your browser opens Spoteye.
   - To quit, close the console window.

### 3. Create your Spotify app (one time)

1. Go to <https://developer.spotify.com/dashboard> and log in with your Spotify **Premium** account.
2. Click **Create app** and fill in:
   - **App name / description:** anything, e.g. "Spoteye".
   - **Redirect URI:** exactly `http://127.0.0.1:8765/callback` (click **Add**).
   - **APIs used:** tick **Web API**.
   - Accept the terms and click **Save**.
3. Open the app's **Settings** and copy the **Client ID** (32 characters, letters a-f and digits).

> **Using a friend's app instead:** a Spotify developer app allows up to 5 users. The app owner can add
> your Spotify e-mail under **User Management** in their dashboard. If their Client ID is built into
> your copy of Spoteye, skip to step 5.

### 4. Enter the Client ID

In Spoteye's **setup card** (top of the page), paste the Client ID and click **Save**.
You can change it later under **Settings** (gear icon).

### 5. Sign in to Spotify

Click **Sign in with Spotify**, approve in the browser tab that opens, and come back to Spoteye.
The setup card disappears when you're signed in.

Spotify signs you out **6 months** after you sign in. Spoteye warns you 2 weeks before; click
**Sign in with Spotify** again when it does.

### 6. Download something

1. Paste a Spotify track or playlist link and click **Preview** to see the tracks and the folder they
   will go to.
2. Pick a quality preset and click **Download**. Progress updates live.
3. Click **Open folder** when it finishes.

| Preset | Result |
| --- | --- |
| `best` (recommended) | The original YouTube Music stream, no re-encoding (Opus ~130-160 kbps, `.opus`) |
| `aac256` | `.m4a` AAC 256 kbps |
| `mp3-320` | `.mp3` for old players/cars; not better quality than `best` |
| `mp3-v0` | `.mp3`, smaller than 320 with the same audible quality |

**Playlists:** Spotify only lets apps read playlists you **own or collaborate on**. For anyone else's
playlist, in Spotify use **Add to other playlist -> New playlist**, then paste the link of your copy.

**Missing tracks:** for tracks marked *not found* or *review*, use **Pick match** to choose the right
YouTube Music song (or paste a YouTube link), or **Attach file** to add a file you got elsewhere.
Each playlist folder also gets a `_missing.txt` and a `.m3u8` playlist file.

### Where things are

| What | Where |
| --- | --- |
| Your music | `%USERPROFILE%\Music\Spoteye` (change it in Settings) |
| Settings, sign-in, history, logs | `%LOCALAPPDATA%\Spoteye` (`logs\spoteye.log` for troubleshooting) |
| Bundled tools | `bin\` in the app folder (`ffmpeg.exe`, `deno.exe`, `yt-dlp.exe`) |

### Updating and uninstalling

- **Downloads suddenly fail:** Settings -> **Update yt-dlp** (YouTube changes often; this usually fixes it).
- **New Spoteye version:** close Spoteye, delete the old app folder, unzip the new one in its place.
  Your settings, sign-in and history stay in `%LOCALAPPDATA%\Spoteye`.
- **Uninstall:** delete the app folder and `%LOCALAPPDATA%\Spoteye`. Your music folder is untouched.

### Troubleshooting

| Message or problem | Fix |
| --- | --- |
| "Set a Spotify Client ID in Settings first" | Do steps 3-4 |
| Sign-in page says the redirect URI is invalid | The Redirect URI in your Spotify app must be exactly `http://127.0.0.1:8765/callback` |
| "Spotify only returns tracks for playlists you own…" | Copy the playlist to your library (see Playlists above) |
| "Spotify sign-in expired" | Click **Sign in with Spotify** |
| "Can't reach Spotify" | Check your internet connection, then retry |
| "YouTube bot check" | Export `cookies.txt` (Netscape format) from a browser where you're logged in to YouTube, then set it under Settings -> Cookies file. See [yt-dlp's cookie FAQ](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp) |
| "YouTube refused the download (403)" | Settings -> Update yt-dlp |
| "Spoteye is already running" | It opened the existing window's page; use that one |
| Nothing opens / the console closes at once | Check `%LOCALAPPDATA%\Spoteye\logs\spoteye.log` |

---

## Part 2: running from source (developers)

### Requirements

| Tool | Version | Install |
| --- | --- | --- |
| Python | 3.12 or newer (developed on 3.14) | `winget install Python.Python.3.14` |
| Node.js | 20 or newer | `winget install OpenJS.NodeJS.LTS` |
| FFmpeg | any recent build with libmp3lame + libopus | `winget install Gyan.FFmpeg` |
| Deno | 2.x (yt-dlp needs it for YouTube) | `winget install DenoLand.Deno` |
| Git | any | `winget install Git.Git` |
| Spotify app | as in Part 1, step 3 | |

### Install

```powershell
git clone https://github.com/01gem/spoteye.git
cd spoteye\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env      # then edit .env
npm --prefix ..\frontend ci
```

`.env` keys (in `backend\.env`; all except the Client ID are optional):

| Key | Default | Meaning |
| --- | --- | --- |
| `SPOTIFY_CLIENT_ID` | (none) | Your Spotify app's Client ID |
| `SPOTIFY_REDIRECT_URI` | `http://127.0.0.1:8765/callback` | Must match the Spotify app |
| `OUTPUT_DIR` | `D:\Music\Spoteye` | Where music is saved |
| `COOKIES_FILE` | (none) | Path to a YouTube `cookies.txt` |
| `DB_PATH` | `backend\spoteye.db` | Job history database |
| `MAX_WORKERS` | `3` | Parallel downloads (1-8) |
| `MATCH_RETRY_DAYS` | `14` | Retry "not found" matches after this many days |

### Run

```powershell
python cli.py login              # first time: Spotify sign-in in the browser
cd ..; .\start.ps1               # builds the UI if needed, serves on http://127.0.0.1:8000
```

Dev mode with hot reload, in two terminals:

```powershell
# backend (venv active)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
# frontend
npm --prefix frontend run dev    # http://localhost:5173
```

Tests: `python -m pytest` in `backend`. Build a release: `.\build.ps1` in the repo root
(see README "Build a release").
