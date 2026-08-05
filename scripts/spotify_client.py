"""Wraps Spotify Web API access for Phase 1's raw data collection.

Owns OAuth setup, pagination, rate-limit retry handling and pacing, and one
method per raw endpoint needed (liked tracks, playlists, playlist items,
top tracks, recently played, single artist, single album, current user
profile).
"""

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import time
from spotipy.exceptions import SpotifyException


class SpotifyClient:
    """Authenticated Spotify Web API client with pagination and retry support.

    One instance owns one authenticated connection (self.sp) plus the raw
    fetch methods built on top of it, so a future multi-user version can
    hold one SpotifyClient per user rather than a single shared connection.
    """

    def __init__(self):
        """Loads credentials and builds an authenticated spotipy client."""
        load_dotenv()
        auth_manager = SpotifyOAuth(
            scope="user-library-read playlist-read-private user-top-read user-read-recently-played"
        )
        self.sp = spotipy.Spotify(auth_manager=auth_manager)

    def item_collector(self, results):
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
            current = self._call_with_retry(lambda: self.sp.next(current))
            items.extend(current["items"])
        return items

    def get_me(self):
        """Fetches the current authenticated user's Spotify profile.

        Returns:
            The user's profile object, including their Spotify user ID.
        """
        return self.sp.current_user()

    def get_liked_tracks(self):
        """Fetches every track in the current user's Liked Songs.

        Returns:
            List of raw liked-track items, across all pages.
        """
        return self.item_collector(self.sp.current_user_saved_tracks())

    def get_playlists(self):
        """Fetches every playlist the current user owns or follows.

        Returns:
            List of raw playlist objects, across all pages.
        """
        return self.item_collector(self.sp.current_user_playlists())

    def get_playlist_items(self, playlist_id):
        """Fetches every track in a single playlist.

        Args:
            playlist_id: Spotify ID of the playlist to fetch tracks for.

        Returns:
            List of raw track items in that playlist, across all pages.
        """
        return self.item_collector(self.sp.playlist_items(playlist_id))

    def get_top_tracks(self, time_range):
        """Fetches the current user's top tracks for one time range.

        Args:
            time_range: one of "short_term", "medium_term", "long_term".

        Returns:
            List of top-track objects for that time range, across all pages.
        """
        return self.item_collector(
            self.sp.current_user_top_tracks(time_range=time_range)
        )

    def get_recently_played(self):
        """Fetches the current user's recently played tracks.

        Returns:
            List of raw recently-played items, across all pages.
        """
        return self.item_collector(self.sp.current_user_recently_played())

    def get_artist(self, artist_id):
        """fetches a full artist object

        Args:
            artist_id: The artist ID

        Returns:
            The full artist object
        """        
        return self._call_with_retry(lambda: self.sp.artist(artist_id))

    def get_album(self, album_id):
        """Fetches full album object

        Args:
            album_id: The Spotify album ID

        Returns:
            The full album object
        """
        return self._call_with_retry(lambda: self.sp.album(album_id))

    def _call_with_retry(self, api_call):
        """Tries to run the API call and if 429 error is hit, sleeps for however long
        we are timed out before trying again

        Args:
            api_call: The API call being tried

        Returns:
            The API call being tried
        """
        time.sleep(0.1)
        try:
            return api_call()
        except SpotifyException as e:
            if e.http_status == 429:
                time.sleep(int(e.headers.get("Retry-After", 1)))
                return api_call()
            raise
