import qobuz
import minim
client = qobuz.PrivateAPI()  # Authenticates via username/password internally
client.create_playlist(name="Test123", tracks=[...])  # Hypothetical method (check documentation)