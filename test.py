import sys
import qobuz
from qobuz_dl.bundle import Bundle
import dotenv

def main():
    bundle = Bundle()
    app_id = bundle.get_app_id()
    secrets = "\n".join(bundle.get_secrets().values())

    print(f"App ID: {app_id}")
    print(f"Secrets (the first usually works):{secrets}")

    print("Registering app with Qobuz...")
    secrets_list = secrets.split('\n')
    for secret in secrets_list:
        try:
            qobuz.api.register_app(app_id, secret)
            user = dotenv.dotenv_values(".env")
            if user.get("QOBUZ_USER") and user.get("QOBUZ_PASS"):
                user = qobuz.User(user["QOBUZ_USER"], user["QOBUZ_PASS"])
            else:
                print("No Qobuz credentials found in .env file. Please set QOBUZ_USER and QOBUZ_PASS.")
                return
            # Attempt to login with the provided credentials
            print(f"Successfully logged in!")
            break  # Exit loop if registration is successful
        except Exception as e:
            print(f"Failed to register with secret {secret}: {e}")    
        qobuz.api.register_app(app_id, secrets[0])
    tracks = get_user_favorites(user, "tracks")
    print(tracks)
    for track in tracks:
        print(f"Track: {track.title}")    

def get_user_favorites(user, fav_type, raw=False):
    '''
    Returns all user favorites

    Parameters
    ----------
    user: dict
        returned by qobuz.User
    fav_type: str
        favorites type: 'tracks', 'albums', 'artists'
    limi
    '''
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


if __name__ == '__main__':
    try:
        main()
    except IOError as e:
        raise e
