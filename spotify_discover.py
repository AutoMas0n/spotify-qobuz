import spotipy
from spotipy.oauth2 import SpotifyOAuth
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

# Support multiple playlist IDs from .env, comma-separated
PLAYLIST_IDS = os.getenv('SPOTIFY_PLAYLIST_IDS', '').split(',')
PLAYLIST_IDS = [pid.strip() for pid in PLAYLIST_IDS if pid.strip()]

# Support mapping playlist IDs to names from .env, format: name1:id1,name2:id2
PLAYLIST_MAP_RAW = os.getenv('SPOTIFY_PLAYLIST_MAP', '')
PLAYLIST_MAP = {}
for entry in PLAYLIST_MAP_RAW.split(','):
    if ':' in entry:
        name, pid = entry.split(':', 1)
        name = name.strip()
        pid = pid.strip()
        if name and pid:
            PLAYLIST_MAP[name] = pid

def get_playlist_url(playlist_id):
    return f"https://open.spotify.com/playlist/{playlist_id}"

async def fetch_playlist_content(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until='networkidle')
        # Correct scroll container selector - verify this matches Spotify's layout
        scroll_container = '.main-view-container'
        await page.wait_for_selector(scroll_container, state='attached')
        element = await page.query_selector(scroll_container)

        # Calculate dynamic scroll parameters
        client_height = await page.evaluate('(element) => element.clientHeight', element)
        scroll_distance = int(client_height * 0.8)  # Scroll 80% of viewport height
        box = await element.bounding_box()

        # Position mouse in scrollable area
        target_x = box['x'] + box['width'] * 0.75
        target_y = box['y'] + box['height'] * 0.75
        await page.mouse.move(target_x, target_y)

        prev_scroll = 0
        current_scroll = 0
        max_attempts = 50
        threshold = 100  # Pixel threshold for considering bottom reached

        for _ in range(max_attempts):
            # Track previous state
            prev_track_count = len(await page.query_selector_all('div[data-testid="tracklist-row"]'))
            prev_scroll = current_scroll

            # Perform scroll
            await page.mouse.wheel(0, scroll_distance)
            # Wait for content load with shorter timeout
            try:
                await page.wait_for_function(
                    f'''() => {{
                        const container = document.querySelector('{scroll_container}');
                        return container.scrollTop > {prev_scroll};
                    }}''',
                    timeout=2000
                )
            except Exception:
                pass

            # Get updated metrics
            current_scroll = await page.evaluate('(element) => element.scrollTop', element)
            total_height = await page.evaluate('(element) => element.scrollHeight', element)
            new_track_count = len(await page.query_selector_all('div[data-testid="tracklist-row"]'))

            # Check termination conditions
            if (current_scroll + client_height + threshold) >= total_height:
                break
            if new_track_count == prev_track_count and abs(current_scroll - prev_scroll) < 50:
                break  # No new content and minimal scrolling

            await page.wait_for_timeout(500)  # Additional short delay

        await page.screenshot(path="playlist_screenshot.png")
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

async def get_playlist_tracks(playlist_id):
    url = get_playlist_url(playlist_id)
    html_content = await fetch_playlist_content(url)
    return scrape_playlist_tracks(html_content)

async def save_playlist_tracks_to_json(playlist_id, filename):
    tracks = await get_playlist_tracks(playlist_id)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(tracks, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(tracks)} tracks to {filename}")

def main():
    client = get_spotify_client()
    # Verify authentication
    try:
        client.current_user()
    except spotipy.exceptions.SpotifyException:
        print("Authentication failed. Please check your credentials.")
        return

    # For each playlist name/id, fetch and save tracks to a mapped JSON file
    async def process_all_playlists():
        for name, playlist_id in PLAYLIST_MAP.items():
            filename = f"{name}_tracks.json"
            await save_playlist_tracks_to_json(playlist_id, filename)
    asyncio.run(process_all_playlists())

if __name__ == "__main__":
    main()