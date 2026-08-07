"""TODO: one-line summary.

TODO: longer description.
"""

from spotify_client import SpotifyClient
from data_cache import DataCache
from musicbrainz_client import MusicbrainzClient
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

    def cache_known_artists(self, artists):
        """Writes already-fetched full artist objects straight to cache.

        Args:
            artists: list of full Artist objects already in hand (e.g. from
                SpotifyClient.get_top_artists), not needing a live fetch.
        """
        for artist in artists:
            filename = f"artist_{artist['id']}.json"
            self.cache.load_or_fetch(filename, lambda: artist)

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


class MusicbrainzEnricher:
    """TODO: class docstring."""

    def __init__(self, client, cache):
        """TODO: docstring.

        Args:
            client: a MusicbrainzClient, used to look up genre data.
            cache: a DataCache, used to cache each resolved artist.
        """
        self.client = client
        self.cache = cache

    def build_artist_isrc_map(self, tracks):
        """TODO: docstring.

        Args:
            tracks: TODO.

        Returns:
            TODO — dict of artist_id -> one isrc from a track that artist
            appears on (first one found; tracks with no isrc are skipped).
        """
        isrc_map = {}
        for track in tracks:
            isrc = track.get("external_ids", {}).get("isrc")
            if isrc != None:
                for artist in track["artists"]:
                    if artist["id"] not in isrc_map:
                        isrc_map[artist["id"]] = {"isrc": isrc, "name": artist["name"]}
        return isrc_map

    def _find_matching_artist_id(self, recording, expected_name):
        """Finds the artist-credit entry on a recording matching a name.

        Args:
            recording: a single MusicBrainz recording object (one entry
                from an ISRC lookup's "recordings" list), expected to have
                an "artist-credit" list.
            expected_name: the Spotify artist name to match against,
                compared case-insensitively and whitespace-stripped.

        Returns:
            The matching artist's MusicBrainz ID, or None if no
            artist-credit entry's name matches.
        """
        expected = expected_name.lower().strip()
        for credit in recording["artist-credit"]:
            if credit["artist"]["name"].lower().strip() == expected:
                return credit["artist"]["id"]
        return None

    def enrich(self, tracks, artist_ids):
        """Resolves genre data via MusicBrainz for the given artists.

        For each artist ID, finds one of their tracks' ISRCs, looks up the
        matching MusicBrainz recording, confirms the correct artist via a
        name match (avoiding a wrong-artist mismatch on multi-artist
        tracks), and caches genre data for a confirmed match. Artists with
        no ISRC, no MusicBrainz match, or no genres are left uncached,
        falling through to ArtistCollector.fetch_all's Spotify fallback.

        Args:
            tracks: flat list of already-unwrapped track objects, used to
                build the artist_id -> isrc/name lookup.
            artist_ids: full set of artist IDs to attempt to resolve —
                safe to pass the complete set, since already-cached ones
                are skipped for free via load_or_fetch (same pattern as
                ArtistCollector.fetch_all).
        """
        isrc_map = self.build_artist_isrc_map(tracks)
        for artist_id in artist_ids:
            entry = isrc_map.get(artist_id)
            if not entry:
                continue

            recordings = self.client.get_recording_by_isrc(entry["isrc"])
            if not recordings or not recordings["recordings"]:
                continue

            recording = recordings["recordings"][0]
            mbid = self._find_matching_artist_id(recording, entry["name"])
            if not mbid:
                continue

            genres = self.client.get_artist_genres(mbid)
            if not genres:
                continue

            record = {"id": artist_id, "genres": genres, "source": "musicbrainz"}
            self.cache.load_or_fetch(f"artist_{artist_id}.json", lambda: record)


# TODO (later, same pattern as ArtistCollector): AlbumCollector, playlists-list
# fetch, /me fetch — see docs/todo.md's Phase 1 section for full scope.


if __name__ == "__main__":
    client = SpotifyClient()
    mb = MusicbrainzClient()
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

    short_term_artists = cache.load_or_fetch(
        "short_term_artists.json", lambda: client.get_top_artists("short_term")
    )
    medium_term_artists = cache.load_or_fetch(
        "medium_term_artists.json", lambda: client.get_top_artists("medium_term")
    )
    long_term_artists = cache.load_or_fetch(
        "long_term_artists.json", lambda: client.get_top_artists("long_term")
    )
    top_artists = short_term_artists + medium_term_artists + long_term_artists

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
    artist_collector.cache_known_artists(top_artists)

    enricher = MusicbrainzEnricher(mb, cache)
    artist_ids = artist_collector.collect_artist_ids(all_tracks_list)
    enricher.enrich(all_tracks_list, artist_ids)

    artists = artist_collector.fetch_all(all_tracks_list)
