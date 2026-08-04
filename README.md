# Music Graph

A graph of my Spotify library — songs as nodes, edges drawn from shared
artists, genres, albums, and playlist co-occurrence. Inspired by a video
that visualized all of Wikipedia as a graph using igraph, Leiden community
detection, and a deliberate, opinionated definition of what counts as a
meaningful link.

## Status

Early / exploratory. Phase 0 is done: pulled data from the Spotify Web API
and found **7,990 unique tracks** across Liked Songs, playlists, top
tracks, and recently played — the number that determines what's realistic
for later layout/rendering phases. Local JSON caching is in place so
re-runs don't re-hit the API. See `todo.md` for detailed, current progress
and next steps, or `project_plan.pdf` for the full original architecture
plan.

**Scale target**: the finished graph should handle at least 20,000 nodes
robustly — well above today's actual 7,990 — so it keeps working as the
library grows rather than needing another scale-driven rework later.

## Setup

Requirements: Python 3, a Spotify account, and a registered Spotify
Developer app (free, at [developer.spotify.com](https://developer.spotify.com)).

1. Clone the repo and set up a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Register a Spotify Developer app with redirect URI
   `http://127.0.0.1:8888/callback`, and grab its Client ID and Client Secret.
3. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```
4. Run the current script:
   ```bash
   python3 scripts/phase0_count_tracks.py
   ```

## Roadmap

0. Count tracks across the library to size the dataset
1. Cache raw data locally
2. Build a clean per-track node table
3. Compute edge signals (shared artist / genre / album / playlist)
4. Turn signals into weighted edges
5. Build the graph and detect communities (Leiden, via `python-igraph`)
6. Layout (Gephi)
7. Static render
8. Interactive explorer (`pyvis`, optionally `sigma.js`)

Full detail and current status in `todo.md`.

## Cost

Free — Spotify's API, the Python libraries used, Gephi, and GitHub Pages
hosting are all free at this project's scale.
