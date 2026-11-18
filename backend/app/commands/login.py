"""`login`: sign in to Spotify in the browser (Spotify ends a sign-in after about 6 months)."""

from __future__ import annotations

from spotipy.oauth2 import SpotifyOauthError

from app.commands import app, console, fail
from app.config import load_settings
from app.models import to_local
from app.services import spotify_auth
from app.services.spotify_client import SpotifyConfigError


@app.command()
def login() -> None:
    """Sign in to Spotify (opens a browser). Needed once, then again about every 6 months."""
    try:
        spotify_auth.login(load_settings())
    except (SpotifyConfigError, SpotifyOauthError) as exc:
        raise fail(str(exc)) from exc
    expires = spotify_auth.sign_in_expires_at()
    assert expires is not None  # login() just wrote it
    console.print(f"Signed in. Spotify will ask again around {to_local(expires):%Y-%m-%d}.")
