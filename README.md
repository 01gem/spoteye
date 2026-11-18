# Spoteye

Paste a Spotify track or playlist link, get tagged audio files. Personal-use project.

## Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Then open `.env` and fill in `SPOTIFY_CLIENT_ID`.

## Usage

```powershell
python cli.py info <spotify url>
python -m pytest
```
