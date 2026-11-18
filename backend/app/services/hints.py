"""Fix-it wording that depends on how Spoteye runs: from source (dev commands) or as the
packaged Spoteye.exe (buttons in the app, or reinstall). Every user-facing hint lives here, so
tests/test_hints.py can check that the packaged texts never name a dev command.
"""

from __future__ import annotations

from app.config import IS_FROZEN

CLI: str = "Spoteye.exe" if IS_FROZEN else "python cli.py"
REINSTALL: str = "reinstall Spoteye."

HINTS: dict[str, tuple[str, str]] = {  # key: (from source, packaged)
    "need_token": (
        "Spotify sign-in needed: run  python cli.py info <any spotify url>  once in the terminal.",
        'Spotify sign-in needed: click "Sign in with Spotify" in Spoteye.',
    ),
    "expired": (
        "Spotify sign-in expired (Spotify limits sign-ins to 6 months). Run: python cli.py login",
        'Spotify sign-in expired (Spotify limits sign-ins to 6 months). Click "Sign in with Spotify" '
        "in Spoteye.",
    ),
    "no_client_id": (
        "SPOTIFY_CLIENT_ID is not set. Copy backend/.env.example to backend/.env and fill it in.",
        "No Spotify Client ID yet: add it in Spoteye's setup card or Settings.",
    ),
    "bot_check": (
        "YouTube bot check. Export cookies.txt from a browser where you're logged in to "
        "YouTube and set COOKIES_FILE in backend/.env.",
        "YouTube bot check. Export cookies.txt from a browser where you're logged in to "
        "YouTube and set it under Settings → YouTube cookies file.",
    ),
    "http_403": (
        "YouTube refused the download (403). Update yt-dlp: pip install -U yt-dlp",
        "YouTube refused the download (403). Update yt-dlp: Settings → Update yt-dlp.",
    ),
    "need_deno": (
        "yt-dlp needs Deno: winget install DenoLand.Deno, then restart the server.",
        f"yt-dlp needs Deno, which comes in Spoteye's bin folder: {REINSTALL}",
    ),
    "no_ffmpeg": (
        "FFmpeg not found: winget install Gyan.FFmpeg",
        f"FFmpeg is missing from Spoteye's bin folder: {REINSTALL}",
    ),
    "ffmpeg_path": (
        "FFmpeg not found on PATH. Install with: winget install Gyan.FFmpeg",
        f"FFmpeg is missing from Spoteye's bin folder: {REINSTALL}",
    ),
    "ytdlp_library": (
        "yt-dlp runs as a library here: update it with pip install -U yt-dlp",
        f"bin\\yt-dlp.exe is missing: {REINSTALL}",
    ),
    "ui_missing": (
        "UI not built: cd ..\\frontend; npm run build (the API still works at /docs)",
        f"The web UI is missing from this Spoteye folder: {REINSTALL}",
    ),
}


def hint(key: str, frozen: bool = IS_FROZEN) -> str:
    """The source or packaged wording of a hint."""
    source, packaged = HINTS[key]
    return packaged if frozen else source
