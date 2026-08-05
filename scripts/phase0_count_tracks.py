"""
Counts all songs relevant to the account.

A helper script that counts all songs that are relevant to the account (liked songs, playlist songs,
recent songs, and top songs). This is so we can get a scope on how many nodes will be in the eventual graph.
"""

import os
import json
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

# load in the spotify API and initialize spotipy
load_dotenv()

auth_manager = SpotifyOAuth(
    scope="user-library-read playlist-read-private user-top-read user-read-recently-played"
)
sp = spotipy.Spotify(auth_manager=auth_manager)


def item_collector(results):
    """Takes in information about songs, traverses through the set, and returns each item in the set.

    Args:
        results: first-page paging object returned by a spotipy call (e.g. sp.current_user_saved_tracks())

    Returns:
        each item in the set
    """
    current = results
    items = []
    items.extend(current["items"])
    while current["next"] != None:
        current = sp.next(current)
        items.extend(current["items"])
    return items


def load_or_fetch(filepath, fetch_fn):
    """
    if a JSON holding the info already exists, return what is inside, if not, write songs to the JSON

    Args:
        filepath: The file that may or may not exist
        fetch_fn: The fetch function

    Returns:
        The cached or freshly fetched data
    """
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)
    else:
        result = fetch_fn()
        with open(filepath, "w") as w:
            json.dump(result, w)
            return result


def fetch_all_playlist_tracks():
    """
    Iterates through all playlists and collects their tracks

    Returns:
        All tracks across all playlists
    """
    playlists = item_collector(sp.current_user_playlists())
    playlist_tracks = []
    for playlist in playlists:
        print(playlist["name"])
        try:
            tracks = load_or_fetch(
                f'data/playlist_{playlist["id"]}.json',
                lambda: item_collector(sp.playlist_items(playlist["id"])),
            )
            playlist_tracks.extend(tracks)
        except SpotifyException:
            print(f"skipping playlist (couldn't access tracks): {playlist['name']}")
    return playlist_tracks


liked_tracks = load_or_fetch(
    "data/liked_tracks.json", lambda: item_collector(sp.current_user_saved_tracks())
)

playlist_tracks = load_or_fetch("data/playlist_tracks.json", fetch_all_playlist_tracks)

short_term = load_or_fetch(
    "data/short_term.json",
    lambda: item_collector(sp.current_user_top_tracks(time_range="short_term")),
)
medium_term = load_or_fetch(
    "data/medium_term.json",
    lambda: item_collector(sp.current_user_top_tracks(time_range="medium_term")),
)
long_term = load_or_fetch(
    "data/long_term.json",
    lambda: item_collector(sp.current_user_top_tracks(time_range="long_term")),
)
top_tracks = short_term + medium_term + long_term

recent_tracks = load_or_fetch(
    "data/recent_tracks.json", lambda: item_collector(sp.current_user_recently_played())
)

liked_tracks_set = {item["track"]["id"] for item in liked_tracks}
playlist_tracks_set = {item["item"]["id"] for item in playlist_tracks}
recent_tracks_set = {item["track"]["id"] for item in recent_tracks}
top_tracks_set = {item["id"] for item in top_tracks}
all_tracks_set = (
    liked_tracks_set | playlist_tracks_set | recent_tracks_set | top_tracks_set
)

print("liked songs count: " + str(len(liked_tracks_set)))
print("playlist songs count: " + str(len(playlist_tracks_set)))
print("recent songs count: " + str(len(recent_tracks_set)))
print("top songs count: " + str(len(top_tracks_set)))
print("all songs count: " + str(len(all_tracks_set)))
