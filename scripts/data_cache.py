"""Describes the DataCache class.

Cache-aside JSON storage for raw Spotify API data, namespaced per user ID,
so multiple users' cached files can't collide under one shared base
directory.
"""

import json
import os


class DataCache:
    """Cache-aside JSON storage, namespaced per user ID.

    Given a base directory and a user ID, stores/loads cache files under
    base_dir/user_id/ so multiple users' cached data can't collide.
    """

    def __init__(self, base_dir, user_id):
        """Sets up this instance's cache folder, creating it if needed.

        Args:
            base_dir: root directory all users' caches live under (e.g. "data").
            user_id: Spotify user ID used to namespace this user's cache files.
        """
        self.base_dir = base_dir
        self.user_id = user_id
        os.makedirs(os.path.join(self.base_dir, self.user_id), exist_ok=True)

    def path_for(self, filename):
        """Builds the full, namespaced path for a cache file.

        Args:
            filename: bare cache file name, e.g. "liked_tracks.json".

        Returns:
            Full path to that file under this user's cache folder.
        """
        return os.path.join(self.base_dir, self.user_id, filename)

    def load_or_fetch(self, filename, fetch_fn):
        """
        if a JSON holding the info already exists, return what is inside, if not, write songs to the JSON

        Args:
            filename: The file that may or may not exist
            fetch_fn: The fetch function

        Returns:
            The cached or freshly fetched data
        """
        if os.path.exists(self.path_for(filename)):
            with open(self.path_for(filename)) as f:
                return json.load(f)
        else:
            result = fetch_fn()
            with open(self.path_for(filename), "w") as w:
                json.dump(result, w)
                return result
