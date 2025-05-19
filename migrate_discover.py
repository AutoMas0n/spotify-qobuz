import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
import os
import json
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from http.server import BaseHTTPRequestHandler
import urllib.parse as urlparse
from urllib.parse import parse_qs

from savify.savify_scheduler import playlist_exists,get_discover_weekly_date,archive_discover_weekly,create_new_playlist

# Load environment variables from .env file
load_dotenv()

# Configuration (store these securely in environment variables)
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = "http://127.0.0.1:8080"
TOKEN_FILE = ".spotify_token"
SOURCE_PLAYLIST_PUBLIC_URL = "https://open.spotify.com/playlist/37i9dQZEVXcQtPyCIvdJFH?si=JjoR7HFvTiaH7hFrHrkH7w"

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        query = urlparse.urlparse(self.path).query
        params = parse_qs(query)
        code = params.get('code', [None])[0]
        if code:
            self.server.code = code
            self.wfile.write(b"Authorization successful! You can close this window.")
        else:
            self.wfile.write(b"Authorization failed.")


def get_refresh_token():
    """Initial one-time setup to get refresh token"""
    from requests.auth import HTTPBasicAuth
    
    auth_url = f"https://accounts.spotify.com/authorize?response_type=code&client_id={CLIENT_ID}&scope=playlist-read-private&redirect_uri={REDIRECT_URI}"
    print(f"Perform ONE-TIME setup:\n1. Visit this URL in your browser:\n{auth_url}")
    print("2. After redirect, paste the full callback URL here:")
    callback_url = input("Paste URL here: ").split('?code=')[1]
    code = callback_url.split('&')[0]

    # Exchange code for refresh token
    response = requests.post(
        'https://accounts.spotify.com/api/token',
        auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI
        },
        timeout=10
    )
    tokens = response.json()
    with open(TOKEN_FILE, 'w') as f:
        json.dump(tokens, f)
    return tokens['refresh_token']

def refresh_access_token():
    """Get new access token using refresh token"""
    with open(TOKEN_FILE) as f:
        tokens = json.load(f)
    response = requests.post(
        'https://accounts.spotify.com/api/token',
        auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
        data={
            'grant_type': 'refresh_token',
            'refresh_token': tokens['refresh_token']
        },
        timeout=10
    )
    return response.json()['access_token']

def archive_discover_weekly_task():
    auth_manager = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=["playlist-read-private", "playlist-modify-private"]
    )

    spotify_client = spotipy.Spotify(auth_manager=auth_manager)
    user_id = spotify_client.current_user()["id"]
    # Check for duplicates
    if playlist_exists(spotify_client, user_id):
        print(f"Playlist for the week of {get_discover_weekly_date()} already exists. Skipping...")
        return

    # Create and archive
    new_playlist = create_new_playlist(spotify_client, user_id)
    archive_discover_weekly(spotify_client, user_id, new_playlist, SOURCE_PLAYLIST_PUBLIC_URL)
    print(f"Archived Discover Weekly for the week of {get_discover_weekly_date()}")

def main():
    # Check for existing token
    if not os.path.exists(TOKEN_FILE):
        get_refresh_token()
    
    # Get access token
    refresh_access_token()
    archive_discover_weekly_task()


if __name__ == "__main__":
    main()