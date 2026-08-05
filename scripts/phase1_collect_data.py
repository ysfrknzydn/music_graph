"""TODO: one-line summary.

TODO: longer description.
"""

from spotify_client import SpotifyClient
from data_cache import DataCache
from spotipy.exceptions import SpotifyException


class ArtistCollector:
    """Collects every unique artist referenced across a set of tracks.

    Given raw track data from any/all of the four Spotify sources, finds
    every unique artist ID referenced, then fetches (and caches) the full
    artist object for each one via SpotifyClient/DataCache.
    """

    def __init__(self, client, cache):
        """Stores the collaborators this collector fetches/caches through.

        Args:
            client: a SpotifyClient, used to fetch artist data.
            cache: a DataCache, used to cache each fetched artist.
        """
        self.client = client
        self.cache = cache

    def collect_artist_ids(self, tracks):
        """Finds every unique artist ID referenced across a list of tracks.

        Args:
            tracks: flat list of already-unwrapped track objects (each with
                an "artists" list directly on it, not nested under a
                source-specific wrapper key).

        Returns:
            Set of unique artist IDs referenced across all given tracks.
        """
        id_set = set()
        for track in tracks:
            for artist in track["artists"]:
                id_set.add(artist["id"])
        return id_set

    def fetch_all(self, tracks):
        """Fetches (and caches) the full artist object for every artist
        referenced across the given tracks, one artist at a time.

        Args:
            tracks: flat list of already-unwrapped track objects, same
                shape collect_artist_ids expects.

        Returns:
            List of full artist objects, one per unique artist referenced.
        """
        artist_list = []
        for artist_id in self.collect_artist_ids(tracks):
            filename = f"artist_{artist_id}.json"
            artist_list.append(
                self.cache.load_or_fetch(
                    filename, lambda: self.client.get_artist(artist_id)
                )
            )
        return artist_list


# TODO (later, same pattern as ArtistCollector): AlbumCollector, playlists-list
# fetch, /me fetch — see docs/todo.md's Phase 1 section for full scope.


if __name__ == "__main__":
    client = SpotifyClient()
    user_id = client.get_me()["id"]

    cache = DataCache("data", user_id)

    liked_tracks = cache.load_or_fetch(
        "liked_tracks.json", lambda: client.get_liked_tracks()
    )

    playlists = cache.load_or_fetch("playlists.json", lambda: client.get_playlists())

    playlist_tracks = []
    for playlist in playlists:
        print(playlist["name"])
        try:
            tracks = cache.load_or_fetch(
                f'playlist_{playlist["id"]}.json',
                lambda: client.get_playlist_items(playlist["id"]),
            )
            playlist_tracks.extend(tracks)
        except SpotifyException:
            print(f"skipping playlist (couldn't access tracks): {playlist['name']}")

    short_term_tracks = cache.load_or_fetch(
        "short_term_tracks.json", lambda: client.get_top_tracks("short_term")
    )
    medium_term_tracks = cache.load_or_fetch(
        "medium_term_tracks.json", lambda: client.get_top_tracks("medium_term")
    )
    long_term_tracks = cache.load_or_fetch(
        "long_term_tracks.json", lambda: client.get_top_tracks("long_term")
    )
    top_tracks = short_term_tracks + medium_term_tracks + long_term_tracks

    recent_tracks = cache.load_or_fetch(
        "recent_tracks.json", lambda: client.get_recently_played()
    )

    liked_tracks_list = [item["track"] for item in liked_tracks]
    playlist_tracks_list = [item["item"] for item in playlist_tracks]
    recent_tracks_list = [item["track"] for item in recent_tracks]
    top_tracks_list = [item for item in top_tracks]
    all_tracks_list = (
        liked_tracks_list + playlist_tracks_list + recent_tracks_list + top_tracks_list
    )

    artist_collector = ArtistCollector(client, cache)
    artists = artist_collector.fetch_all(all_tracks_list)
