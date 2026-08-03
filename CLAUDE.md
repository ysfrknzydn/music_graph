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

Phase 0 of 9 (full roadmap in `todo.md`) is functionally complete —
`scripts/phase0_count_tracks.py` runs end to end and found **7,990 unique
tracks** across Liked Songs (195), playlists (2,577), top tracks/all 3
ranges (7,319 unique — Spotify's `total` for `long_term` alone is 7,084,
confirmed against the raw API response, not just the script's own count),
and recently played (49). That number is above the plan's ~5k threshold
for "any layout algorithm is fine, skip DrL" — worth revisiting at Phase
6. **Read `todo.md` before resuming work** — it tracks exactly what's
done, blocked, and left to do, kept current each session.

**Design target (set 2026-08-03, post-Phase 0): handle at least 20,000
nodes**, not just today's actual 7,990 — a forward-looking robustness
target for library growth (more listening, more playlists), not a
current-state fact. Evaluate Phase 6 (layout) and Phase 8 (interactive
explorer performance) against 20k before considering either done.

## Architecture notes (current script)

- `item_collector(results)` is the core reusable pattern: takes a first
  page from any paginated spotipy call, walks all subsequent pages via
  `current['next']` / `sp.next(current)`, and returns a flat list of raw
  items. All data sources go through this helper.
- `load_or_fetch(filepath, fetch_fn)` is the cache-aside helper: loads
  `filepath` if it exists, otherwise calls `fetch_fn()` (passed as a
  function/lambda — the call only happens on a cache miss) and writes the
  result to `filepath` as JSON before returning it. All six raw fetches
  (`liked_tracks`, `playlist_tracks`, `short_term`, `medium_term`,
  `long_term`, `recent_tracks`) route through this; cache files live in
  `data/` (gitignored).
- Playlist fetching (`fetch_all_playlist_tracks()`) nests a **second**
  `load_or_fetch()` call inside its per-playlist loop, keyed by playlist
  ID (`data/playlist_<id>.json`), in addition to the outer
  `load_or_fetch('data/playlist_tracks.json', fetch_all_playlist_tracks)`
  wrapping the whole function. This isn't redundant: the outer cache
  alone is all-or-nothing — a crash partway through the ~30-playlist loop
  (this happened once, from a transient network timeout) would lose all
  progress and re-hit the API for every playlist on retry. The inner
  per-playlist cache makes each playlist's fetch independently
  resumable, so a retry only re-fetches what didn't finish.
- Spotify's playlist items endpoint (`playlist_items()`) wraps each entry
  under the key `'item'`, not `'track'` — inconsistent with
  `current_user_saved_tracks()` / `current_user_recently_played()` (which
  use `'track'`) and `current_user_top_tracks()` (unwrapped, `item['id']`
  directly). Don't assume nesting is consistent across endpoints without
  checking real returned data.
- Some playlists 403 on `playlist_items()` even though they're listed by
  `current_user_playlists()` (Spotify-owned algorithmic playlists,
  licensing-restricted ones) — wrapped in `try`/`except SpotifyException`
  to skip and continue rather than crash. These don't get a cache file
  written, so they're re-checked (not permanently assumed inaccessible)
  on every run.
- Docstring convention (established this session, apply to future
  scripts too): module-level docstring at the top (one-line summary +
  longer description), every function gets a Google-style docstring
  (`Args:` / `Returns:`).
