import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
import os
import json
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from lxml.html import fromstring
from playwright.async_api import async_playwright

# Load environment variables from .env file
load_dotenv()

# Configuration
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = "http://localhost:8080"
TOKEN_FILE = ".spotify_token"
SOURCE_PLAYLIST_URL = "https://open.spotify.com/playlist/37i9dQZEVXcQtPyCIvdJFH"

async def fetch_playlist_content(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until='networkidle')
        await page.wait_for_timeout(3000)
        content = await page.content()
        await browser.close()
        return content

def scrape_playlist_tracks(html_content):
    parser = fromstring(html_content)
    tracks = []
    
    # Extract track elements
    track_elements = parser.xpath('//div[@data-testid="tracklist-row"]')
    print(f"Found {len(track_elements)} tracks.")
    
    for element in track_elements:
        track_name = element.xpath('.//a[@data-testid="internal-track-link"]/div/text()')
        # Updated XPath: find all <a> with href containing '/artist/' under this track row
        artist_names = element.xpath('.//a[contains(@href, "/artist/")]/text()')
        artist_name = ", ".join(artist_names) if artist_names else ""
        print(f"Track: {track_name}, Artist: {artist_name}")
        
        if track_name and artist_name:
            tracks.append({
                'track': track_name[0],
                'artist': artist_name
            })
    
    return tracks

def get_spotify_client():
    auth_manager = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope="playlist-modify-private",
        cache_path=TOKEN_FILE
    )
    return spotipy.Spotify(auth_manager=auth_manager)

def get_track_uri(client, track_name, artist_name):
    query = f"track:{track_name} artist:{artist_name}"
    results = client.search(q=query, type='track', limit=1)
    if results['tracks']['items']:
        return results['tracks']['items'][0]['uri']
    return None

def get_discover_weekly_date():
    today = datetime.now()
    last_monday = today - timedelta(days=today.weekday())
    return last_monday.strftime("%d-%m-%y")

async def get_discover_weekly_tracks():
    html_content = await fetch_playlist_content(SOURCE_PLAYLIST_URL)
    return scrape_playlist_tracks(html_content)

def archive_playlist(client):
    user_id = client.current_user()['id']
    playlist_name = f"[ARCH] DW {get_discover_weekly_date()}"
    
    # Create new playlist
    new_playlist = client.user_playlist_create(
        user=user_id,
        name=playlist_name,
        public=False,
        description=f"Archived Discover Weekly - {get_discover_weekly_date()}"
    )
    
    # Get track URIs
    raw_tracks = asyncio.run(get_discover_weekly_tracks())
    track_uris = []
    
    for track in raw_tracks:
        uri = get_track_uri(client, track['track'], track['artist'])
        if uri:
            track_uris.append(uri)
    
    # Add tracks to playlist
    if track_uris:
        client.playlist_add_items(new_playlist['id'], track_uris)
        print(f"Successfully archived {len(track_uris)} tracks to {playlist_name}")
    else:
        print("No tracks found to archive")

def main():
    client = get_spotify_client()
    
    # Verify authentication
    try:
        client.current_user()
    except spotipy.exceptions.SpotifyException:
        print("Authentication failed. Please check your credentials.")
        return
    
    archive_playlist(client)

if __name__ == "__main__":
    main()