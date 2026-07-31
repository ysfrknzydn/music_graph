# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Personal project building a graph of the user's Spotify library — songs as
nodes, edges by shared artist/genre/album/playlist co-occurrence. Inspired
by a Wikipedia-graph visualization video that used igraph + Leiden
community detection. Full architecture plan (tooling choices, cost
breakdown, all 9 phases) lives at
`/Users/yusuf/.claude/plans/pure-spinning-toast.md`; current status lives
in `todo.md` at the repo root.

**The user is implementing this themselves.** Default mode when assisting:
review their code, explain concepts/bugs, answer questions — don't write
or edit their project code unless they explicitly ask for that specific
fix in that turn. See `todo.md`'s "Standing preferences" section for more.

## Setup & running

```bash
source venv/bin/activate
python3 scripts/phase0_count_tracks.py
```

Requires a `.env` file (gitignored, not committed) with
`SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI` — see
`.env.example` for the expected keys. Requires a registered Spotify
Developer app with redirect URI `http://127.0.0.1:8888/callback`.

No test suite, linter, or build step exists yet — this is a single-script
exploratory phase.

## Current state

Phase 0 of 9 (full roadmap in `todo.md`) — `scripts/phase0_count_tracks.py`
counts unique tracks across Liked Songs, playlists, top tracks (3 ranges),
and recently played, to size the dataset before later phases (graph
construction, layout, rendering). **Read `todo.md` before resuming work**
— it tracks exactly what's done, blocked, and left to do, kept current
each session.

## Architecture notes (current script)

- `item_collector(results)` is the core reusable pattern: takes a first
  page from any paginated spotipy call, walks all subsequent pages via
  `current['next']` / `sp.next(current)`, and returns a flat list of raw
  items. All four data sources go through this helper.
- Spotify's playlist items endpoint (`playlist_items()`) wraps each entry
  under the key `'item'`, not `'track'` — inconsistent with
  `current_user_saved_tracks()` / `current_user_recently_played()` (which
  use `'track'`) and `current_user_top_tracks()` (unwrapped, `item['id']`
  directly). Don't assume nesting is consistent across endpoints without
  checking real returned data.
- Some playlists 403 on `playlist_items()` even though they're listed by
  `current_user_playlists()` (Spotify-owned algorithmic playlists,
  licensing-restricted ones) — wrapped in `try`/`except SpotifyException`
  to skip and continue rather than crash.
- No local caching yet (planned next, see `todo.md`) — every run re-hits
  the live Spotify API for all four sources, which is slow and can
  trigger long rate-limit lockouts (~24h observed) if run repeatedly
  while debugging.
