import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import re
import json
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from lxml.html import fromstring
from playwright.async_api import async_playwright

# Load environment variables from .env file
load_dotenv()


# Multi-account configuration
def get_spotify_accounts():
    env = os.environ
    account_pattern = re.compile(r'SPOTIFY_CLIENT_ID_(\d+)')
    accounts = []
    for key in env:
        match = account_pattern.match(key)
        if match:
            idx = match.group(1)
            client_id = env.get(f'SPOTIFY_CLIENT_ID_{idx}')
            client_secret = env.get(f'SPOTIFY_CLIENT_SECRET_{idx}')
            playlist_ids = env.get(f'SPOTIFY_PLAYLIST_IDS_{idx}', '').split(',')
            playlist_ids = [pid.strip() for pid in playlist_ids if pid.strip()]
            playlist_map_raw = env.get(f'SPOTIFY_PLAYLIST_MAP_{idx}', '')
            playlist_map = {}
            for entry in playlist_map_raw.split(','):
                if ':' in entry:
                    name, pid = entry.split(':', 1)
                    name = name.strip()
                    pid = pid.strip()
                    if name and pid:
                        playlist_map[name] = pid
            accounts.append({
                'idx': idx,
                'client_id': client_id,
                'client_secret': client_secret,
                'playlist_ids': playlist_ids,
                'playlist_map': playlist_map
            })
    return accounts

REDIRECT_URI = "http://localhost:8080"

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

def get_spotify_client(client_id, client_secret, token_file):
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,
        scope="playlist-modify-private",
        cache_path=token_file
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
    accounts = get_spotify_accounts()
    if not accounts:
        print("No Spotify accounts found in environment. Please check your .env file.")
        return
    for account in accounts:
        idx = account['idx']
        client_id = account['client_id']
        client_secret = account['client_secret']
        playlist_map = account['playlist_map']
        token_file = f".spotify_token_{idx}"
        print(f"\n=== Processing Spotify account {idx} ===")
        client = get_spotify_client(client_id, client_secret, token_file)
        # Verify authentication
        try:
            client.current_user()
        except spotipy.exceptions.SpotifyException:
            print(f"Authentication failed for account {idx}. Skipping.")
            continue
        async def process_all_playlists():
            for name, playlist_id in playlist_map.items():
                filename = f"{name}_tracks_{idx}.json"
                await save_playlist_tracks_to_json(playlist_id, filename)
        asyncio.run(process_all_playlists())

if __name__ == "__main__":
    main()