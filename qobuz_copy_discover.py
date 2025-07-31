import qobuz
from qobuz_dl.bundle import Bundle
import dotenv
import os
import re
import asyncio
import json
import datetime

def get_user_favorites(user, fav_type, raw=False):
    """
    Returns all user favorites

    Parameters
    ----------
    user: dict
        returned by qobuz.User
    fav_type: str
        favorites type: 'tracks', 'albums', 'artists'
    limi
    """
    limit = 500
    offset = 0
    favorites = []
    while True:
        favs = user.favorites_get(fav_type=fav_type, limit=limit, offset=offset)
        if raw:
            if len(favs[fav_type]["items"]) == 0:
                break
            for _f in favs[fav_type]["items"]:
                favorites.append(_f)
        else:
            if not favs:
                break
            favorites += favs
        offset += limit
    return favorites

def load_spotify_tracks(filename="discover_weekly_tracks.json"):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def create_playlist(user, name, description=None, is_public=0, is_collaborative=0):
    """
    Create a new playlist for the user.

    Parameters
    ----------
    user: qobuz.User
        Authenticated Qobuz user object
    name: str
        Name of the new playlist
    description: str, optional
        Description for the playlist
    is_public: int, optional
        1 to make the playlist public, 0 otherwise
    is_collaborative: int, optional
        1 to make the playlist collaborative, 0 otherwise
    """
    try:
        playlist = user.playlist_create(
            name=name,
            description=description,
            is_public=is_public,
            is_collaborative=is_collaborative
        )
        print(f"Playlist '{name}' created successfully! (ID: {playlist.id})")
        return playlist
    except Exception as e:
        print(f"Failed to create playlist '{name}': {e}")
        return None



async def get_ids_from_json_tracks_async():
    """
    Fetches tracks from Spotify Discover Weekly and searches for them on Qobuz.
    Returns a list of Qobuz track IDs.
    """
    tracks = await get_discover_weekly_tracks()
    qobuz_ids = []
    for track in tracks:
        title = track['track']
        artist = track['artist']
        # Search Qobuz for the track
        try:
            results = qobuz.Track.search(f"{title} {artist}", limit=1)
            if results:
                qobuz_ids.append(results[0].id)
        except Exception as e:
            print(f"Error searching Qobuz for '{title}' by '{artist}': {e}")
    return qobuz_ids

def get_ids_from_json_tracks():
    """
    Synchronous wrapper for get_ids_from_json_tracks_async.
    """
    return asyncio.run(get_ids_from_json_tracks_async())

def get_ids_from_json_tracks(user,tracks):
    """
    Loads tracks from spotify_discover.py, searches for them on Qobuz, and returns a list of Qobuz Track objects.
    """
    qobuz_tracks = []
    for track in tracks:
        title = track['track']
        artist = track['artist']
        try:
            results = qobuz.Track.search(f"{title} {artist}", limit=1)
            if results:
                qobuz_tracks.append(results[0])
        except Exception as e:
            print(f"Error searching Qobuz for '{title}' by '{artist}': {e}")
    return qobuz_tracks


# Multi-account Qobuz support
def get_qobuz_accounts():
    env = os.environ
    account_pattern = re.compile(r'QOBUZ_USER_(\d+)')
    accounts = []
    for key in env:
        match = account_pattern.match(key)
        if match:
            idx = match.group(1)
            user = env.get(f'QOBUZ_USER_{idx}')
            pw = env.get(f'QOBUZ_PASS_{idx}')
            if user and pw:
                accounts.append({'idx': idx, 'user': user, 'pw': pw})
    return accounts

def main():
    bundle = Bundle()
    app_id = bundle.get_app_id()
    secrets = "\n".join(bundle.get_secrets().values())
    print(f"App ID: {app_id}")
    print(f"Secrets (the first usually works):{secrets}")
    accounts = get_qobuz_accounts()
    if not accounts:
        print("No Qobuz accounts found in environment. Please check your .env file.")
        return
    for account in accounts:
        idx = account['idx']
        print(f"\n=== Processing Qobuz account {idx} ({account['user']}) ===")
        secrets_list = secrets.split('\n')
        user_obj = None
        for secret in secrets_list:
            try:
                qobuz.api.register_app(app_id, secret)
                user_obj = qobuz.User(account['user'], account['pw'])
                print("Successfully logged in!")
                break
            except Exception as e:
                print(f"Failed to register with secret {secret}: {e}")
        if not user_obj:
            print(f"Could not authenticate Qobuz account {idx}. Skipping.")
            continue
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        playlist_name = f"Spotify Discover Weekly {timestamp} ({idx})"
        playlist = create_playlist(user_obj, playlist_name, "Spotify Discover Weekly Copy")
        if playlist:
            tracks = load_spotify_tracks()
            qobuz_tracks = get_ids_from_json_tracks(user_obj, tracks)
            print(f"Adding {len(qobuz_tracks)} tracks to the playlist...")
            playlist.add_tracks(qobuz_tracks, user_obj)

if __name__ == '__main__':
    try:
        main()
    except IOError as e:
        raise e
