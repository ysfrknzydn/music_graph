# Music Graph

A graph of my Spotify library — songs as nodes, edges drawn from shared
artists, genres, albums, and playlist co-occurrence. Inspired by a video
that visualized all of Wikipedia as a graph using igraph, Leiden community
detection, and a deliberate, opinionated definition of what counts as a
meaningful link.

## Status

Early / exploratory. Currently on Phase 0: pulling data from the Spotify
Web API and finding out how large this graph is actually going to be,
before any graph-building or visualization work starts. See `todo.md` for
detailed, current progress and next steps.

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
