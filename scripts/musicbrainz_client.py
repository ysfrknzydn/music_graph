"""TODO: one-line summary.

TODO: longer description
"""

import requests
import time


class MusicbrainzClient:
    """TODO: class docstring"""

    def __init__(self):
        """TODO: docstring."""
        session = requests.Session()
        session.headers.update(
            {"User-Agent": "MusicGraph/0.1 (https://github.com/ysfrknzydn)"}
        )
        self.session = session

    def get_recording_by_isrc(self, isrc):
        """TODO

        Args:
            isrc: TODO

        Returns:
            TODO
        """
        time.sleep(1)
        response = self.session.get(
            f"https://musicbrainz.org/ws/2/isrc/{isrc}?inc=artist-credits&fmt=json"
        )
        status = response.status_code
        if status == 404:
            return None
        elif status == 200:
            return response.json()
        raise Exception(f"something went wrong. Error code: {status}")

    def get_artist_genres(self, mbid):
        """TODO

        Args:
            mbid: TODO

        Returns:
            TODO
        """
        # TODO: GET /ws/2/artist/{mbid}?inc=genres&fmt=json
        # TODO: same pacing as above
        # TODO: extract and return the genre name list
        time.sleep(1)
        response = self.session.get(
            f"https://musicbrainz.org/ws/2/artist/{mbid}?inc=genres&fmt=json"
        )
        status = response.status_code
        if status == 404:
            return None
        elif status == 200:
            data = response.json()
            genres = data.get("genres", [])
            return [g["name"] for g in genres]
        raise Exception(f"something went wrong. Error code: {status}")
