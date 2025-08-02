## spotify-qobuz

This project helps you transfer your Spotify Discover Weekly playlist to Qobuz.

## Config

1. Open your discover weekly playlist in spotify and save the playlist, make sure it is publicly accessible
2. Create the file `.env` in the root of this project

```
QOBUZ_USER='<your_qobuz_email>'
QOBUZ_PASS='<your_qobuz_password>'
SPOTIFY_PLAYLIST_MAP='discover_weekly:37i9dQZa7AXcQtPyCIvdJFH' # Change this to your public spotify discover weekly ID
```

## PyEnv Quick start

```bash
source bin/activate
pip install -r requirements.txt
# Follow any playwright instructions
```

**How it works:**
1. Run `spotify_discover.py` to create `discover_weekly_tracks.json` containing your Discover Weekly tracks from Spotify.
2. Run `qobuz_copy_discover.py` to read that JSON and add the tracks to your Qobuz account.

Simple, fast, and effective for keeping your music in sync between Spotify and Qobuz.
