import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

load_dotenv()

auth_manager = SpotifyOAuth(
    scope="user-library-read playlist-read-private user-top-read user-read-recently-played"
)
sp = spotipy.Spotify(auth_manager=auth_manager)

def item_collector(results):
    current = results
    items = []
    items.extend(current['items'])
    while(current['next'] != None):
        current = sp.next(current)
        items.extend(current['items'])
    return items
        
liked_tracks = item_collector(sp.current_user_saved_tracks())

playlists = item_collector(sp.current_user_playlists())
playlist_tracks = []
for playlist in playlists:
    print(playlist['name'])
    try:
        playlist_tracks.extend(item_collector(sp.playlist_items(playlist['id'])))
    except SpotifyException:
        print(f"skipping playlist (couldn't access tracks): {playlist['name']}")

for item in playlist_tracks:
    if 'track' not in item:
        print(item)

short_term = item_collector(sp.current_user_top_tracks(time_range="short_term"))
medium_term = item_collector(sp.current_user_top_tracks(time_range="medium_term"))
long_term = item_collector(sp.current_user_top_tracks(time_range="long_term"))
top_tracks = short_term + medium_term + long_term

recent_tracks = item_collector(sp.current_user_recently_played())

liked_tracks_set = {item['track']['id'] for item in liked_tracks}
playlist_tracks_set = {item['item']['id'] for item in playlist_tracks}
recent_tracks_set = {item['track']['id'] for item in recent_tracks}
top_tracks_set = {item['id'] for item in top_tracks}
all_tracks_set = liked_tracks_set | playlist_tracks_set | recent_tracks_set | top_tracks_set

print("liked songs count: " + str(len(liked_tracks_set)))
print("playlist songs count: " + str(len(playlist_tracks_set)))
print("recent songs count: " + str(len(recent_tracks_set)))
print("top songs count: " + str(len(top_tracks_set)))
print("all songs count: " + str(len(all_tracks_set)))
