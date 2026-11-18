Spoteye {VERSION} for Windows (64-bit)
=====================================

Paste a Spotify track or playlist link, get tagged audio files.
Spotify is used for the track list and tags; the audio comes from YouTube Music.


START
-----
1. Unzip this folder somewhere you can write to, for example:
       %LOCALAPPDATA%\Programs\Spoteye
   Do NOT put it in "Program Files": the "Update yt-dlp" button needs to replace bin\yt-dlp.exe.
2. Double-click Spoteye.exe. A console window opens and your browser shows the app.
   Windows SmartScreen may warn on the first run: click "More info" -> "Run anyway".
3. To quit, close the console window.


FIRST-RUN SETUP (in the browser)
--------------------------------
1. Create an app at https://developer.spotify.com/dashboard
   (your Spotify account needs Premium), and add this Redirect URI:
       http://127.0.0.1:8765/callback
2. Paste the app's Client ID into Spoteye and save.
   (If this build came with a Client ID, skip steps 1-2: ask the person who
   shared it to add your Spotify e-mail under User Management in their app.)
3. Click "Sign in with Spotify" and approve in the browser.
   Spotify signs you out after 6 months; Spoteye reminds you to sign in again.

Spotify only lets apps read playlists you own or collaborate on. For someone
else's playlist: in Spotify, "Add to other playlist" -> "New playlist", then use that.


WHERE THINGS ARE
----------------
Downloads:      %USERPROFILE%\Music\Spoteye (change it in Settings)
App data:       %LOCALAPPDATA%\Spoteye  (settings, sign-in, history, logs\spoteye.log)
Bundled tools:  bin\ffmpeg.exe, bin\deno.exe, bin\yt-dlp.exe

To uninstall: delete this folder and %LOCALAPPDATA%\Spoteye.


IF DOWNLOADS START FAILING
--------------------------
YouTube changes often. Open Settings -> "Update yt-dlp" first.
"Bot check" errors: export cookies.txt from a browser where you're logged in to
YouTube and set its path under Settings -> Cookies file.


QUALITY
-------
"best" keeps the original YouTube Music stream (Opus ~160 kbps, or AAC 256 kbps
with YouTube Music Premium cookies). "mp3-320" is for compatibility only: it is
never better than the source.


LEGAL
-----
For personal use. Spoteye does not break Spotify's DRM: it reads metadata from
Spotify and downloads publicly available audio from YouTube Music, which may be
against YouTube's terms of service. Respect copyright where you live.

Spoteye is free software under the GNU GPL v3 (LICENSE.txt). Third-party
licenses are in the licenses\ folder (Python packages, FFmpeg, Deno, yt-dlp).
