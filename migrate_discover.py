import requests
import os
import json
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from http.server import BaseHTTPRequestHandler
import urllib.parse as urlparse
from urllib.parse import parse_qs

# Load environment variables from .env file
load_dotenv()

# Configuration (store these securely in environment variables)
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = "http://localhost:8080"
TOKEN_FILE = ".spotify_token"

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


def get_discover_weekly(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    url = 'https://api.spotify.com/v1/me/playlists'
    user_profile = requests.get('https://api.spotify.com/v1/me', headers=headers, timeout=10).json()
    current_user_id = user_profile['id']
    
    while url:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        for playlist in data['items']:
            
            
            # Case-insensitive partial name match and check ownership
            if 'discover weekly' in playlist['name'].lower():
                print(f"Debug: {playlist['name']} [{playlist['owner']['id']}]")  # Keep debug
                # Match either official Spotify version OR your personal copies
                if playlist['name'].lower() == 'discover weekly' and playlist['owner']['id'] == 'spotify':
                    return playlist['id']
        
        url = data.get('next')
    return None

def get_playlist_tracks(access_token, playlist_id):
    headers = {'Authorization': f'Bearer {access_token}'}
    tracks_response = requests.get(tracks_url, headers=headers, timeout=10)
    return tracks_response.json()['items']
    tracks_response = requests.get(tracks_url, headers=headers)
    return tracks_response.json()['items']

def main():
    # Check for existing token
    if not os.path.exists(TOKEN_FILE):
        get_refresh_token()
    
    # Get access token
    access_token = refresh_access_token()
    
    if not access_token:
        print("Failed to get access token")
        return
    
    # Step 3: Find Discover Weekly playlist
    playlist_id = get_discover_weekly(access_token)
    if not playlist_id:
        print("Discover Weekly playlist not found")
        return
    
    # Step 4: Get playlist tracks
    tracks = get_playlist_tracks(access_token, playlist_id)
    
    # Print tracks
    print("\nDiscover Weekly Playlist Tracks:")
    for idx, item in enumerate(tracks, 1):
        track = item['track']
        if track:  # Check if track exists (might be None if unavailable)
            artists = ", ".join([artist['name'] for artist in track['artists']])
            print(f"{idx}. {track['name']} by {artists}")


if __name__ == "__main__":
    main()