import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
SPOTIFY_EMAIL = os.getenv('SPOTIFY_EMAIL')
SPOTIFY_PASSWORD = os.getenv('SPOTIFY_PASSWORD')
CHROME_DRIVER_PATH = '/path/to/chromedriver'  # Update this

def get_discover_weekly_api(access_token):
    """API-based approach with error handling"""
    try:
        # Try official API first
        headers = {'Authorization': f'Bearer {access_token}'}
        
        # Search Spotify's public catalog
        search_response = requests.get(
            'https://api.spotify.com/v1/search?q=Discover+Weekly&type=playlist&limit=1',
            headers=headers
        ).json()
        
        if 'playlists' in search_response:
            for playlist in search_response['playlists']['items']:
                if playlist['name'] == 'Discover Weekly' and playlist['owner']['id'] == 'spotify':
                    return playlist['id']
        
        # Fallback to user playlists
        url = 'https://api.spotify.com/v1/me/playlists'
        while url:
            response = requests.get(url, headers=headers)
            data = response.json()
            for playlist in data['items']:
                if 'discover weekly' in playlist['name'].lower():
                    return playlist['id']
            url = data.get('next')
        
        return None
    
    except Exception as e:
        print(f"API failed: {str(e)}")
        return None

def get_discover_weekly_web():
    """Web scraping fallback using Selenium"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in background
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    driver = webdriver.Chrome(executable_path=CHROME_DRIVER_PATH, options=options)
    
    try:
        driver.get('https://accounts.spotify.com/en/login')
        
        # Login
        email_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'login-username')))
        email_field.send_keys(SPOTIFY_EMAIL)
        
        password_field = driver.find_element(By.ID, 'login-password')
        password_field.send_keys(SPOTIFY_PASSWORD)
        
        login_button = driver.find_element(By.ID, 'login-button')
        login_button.click()
        
        # Navigate to Discover Weekly
        WebDriverWait(driver, 10).until(
            EC.url_contains('https://open.spotify.com'))
        
        driver.get('https://open.spotify.com/playlist/37i9dQZEVXcJZyENOWUFo7')
        
        # Wait for page load
        time.sleep(3)
        
        # Extract playlist ID from URL
        current_url = driver.current_url
        if '/playlist/' in current_url:
            return current_url.split('/playlist/')[-1].split('?')[0]
            
        return None
    finally:
        driver.quit()

def main():
    # First try API method
    access_token = "your_api_access_token"  # Get this from your existing auth flow
    api_playlist_id = get_discover_weekly_api(access_token)
    
    if api_playlist_id:
        print(f"Found via API: {api_playlist_id}")
        return
    
    # Fallback to web scraping
    print("Falling back to web scraping...")
    web_playlist_id = get_discover_weekly_web()
    
    if web_playlist_id:
        print(f"Found via web: {web_playlist_id}")
    else:
        print("Discovery Weekly not found")

if __name__ == "__main__":
    main()