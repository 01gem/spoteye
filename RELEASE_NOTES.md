# Spoteye 1.1.0

**What's new**
- Live per-track progress: download %, size, speed and time left, plus the matching, waiting,
  converting and tagging phases, with a live summary next to the counts.
- The selected job is kept in the address (`#job=<id>`), so a reload reopens it.

Paste a Spotify track or playlist link, get tagged audio files (audio from YouTube Music). Windows 10/11, 64-bit.

**Install:** unzip to `%LOCALAPPDATA%\Programs\Spoteye` (not Program Files) and run `Spoteye.exe`.
SmartScreen may warn on first run: More info -> Run anyway.

**First run:** create an app at https://developer.spotify.com/dashboard (Spotify Premium needed),
add the Redirect URI `http://127.0.0.1:8765/callback`, paste the Client ID into Spoteye, and sign in.
Spotify only returns tracks for playlists you own or collaborate on.

**Bundled:** yt-dlp 2026.10.26, Deno 2.9.8, FFmpeg n9.0.2 (LGPL build). If downloads fail later: Settings -> Update yt-dlp.

**SHA-256** (Spoteye-1.1.0-win64.zip): `<filled in after build>`

Licensed GPL-3.0-or-later. Third-party licenses are in the zip's `licenses\` folder; source code for the bundled
Python packages is available from https://pypi.org at the versions listed in `licenses\python\THIRD_PARTY.md`.
Personal use only; downloading from YouTube may break YouTube's terms of service.
