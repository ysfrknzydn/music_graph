# Music Graph — Project TODO

Living status doc. Read this first when picking the project back up, in any
session, any amount of time later.

## Where things live

- Full architecture plan (why decisions were made, all tooling choices, cost
  breakdown): `/Users/yusuf/.claude/plans/pure-spinning-toast.md`
- Repo: https://github.com/ysfrknzydn/music_graph (public)
- Local path: `/Users/yusuf/Desktop/projects/music_graph`
- Spotify Developer app: named "Music Graph", redirect URI
  `http://127.0.0.1:8888/callback`
- Current working script: `scripts/phase0_count_tracks.py`

## Environment status — done

- Git repo initialized, public on GitHub, pushed.
- `venv/` created; `spotipy` + `python-dotenv` installed; `requirements.txt`
  frozen via `pip freeze`.
- `.env` created (gitignored) with `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`,
  `SPOTIPY_REDIRECT_URI`.
- `.gitignore` covers: `venv/`, `.env`, `__pycache__/`, `*.pyc`, `.DS_Store`,
  `data/`, `.cache` (the last one holds spotipy's cached OAuth token).

## Phase 0 — Find the actual scale (DONE, 2026-08-03)

**Goal**: count unique tracks across Liked Songs + playlists + top tracks
(3 time ranges) + recently played, to know what we're dealing with before
picking a layout algorithm in Phase 6.

**Result — the actual exit condition for Phase 0**:

| Source | Unique tracks |
|---|---|
| Liked Songs | 195 |
| Playlists | 2,577 |
| Top tracks (3 ranges, deduped) | 7,319 |
| Recently played | 49 |
| **All sources, deduped (`all_tracks_set`)** | **7,990** |

Naive sum of the four counts is 10,140; the 2,150-track gap is overlap
between sources (`playlist ∩ top` alone is 1,929 — makes sense, heavily
playlisted songs are also heavily played). Confirmed the large `top_tracks`
number isn't a pagination bug: Spotify's own API reports `total: 7084` for
`long_term` directly in the raw response, checked independently of the
script's own count.

**This number is above the plan's ~5k threshold** ("under ~5k tracks, any
standard force-directed layout is fine, skip DrL") — worth a real look at
Phase 6 rather than assuming the simple case still applies, though 7,990 is
still nowhere near Wikipedia's ~6M-node scale DrL was built for.

**Design target set after Phase 0, 2026-08-03: handle at least 20,000
nodes.** Not today's actual count (7,990) — a forward-looking robustness
target so the graph keeps working as the library grows (more listening,
more playlists) without needing another scale-driven rework later. This
raises the bar past the plan's original "~5k is trivially fine" framing;
Phase 6 (layout) and Phase 8 (interactive explorer performance) should be
evaluated against 20k, not against today's 7,990, before calling either
phase done.

### Done so far, in `scripts/phase0_count_tracks.py`

- OAuth setup: `load_dotenv()` + `SpotifyOAuth` (scopes: `user-library-read
  playlist-read-private user-top-read user-read-recently-played`) + `spotipy.Spotify` client.
- `item_collector(results)` — pagination helper. Captures the first page's
  items, then loops while `current['next']` is not `None`, fetching each
  next page exactly once via `sp.next(current)` and merging items in.
  Returns the full flat list across all pages.
- Fetches all four sources:
  - `liked_tracks` — via `current_user_saved_tracks()`
  - `playlists` → looped, `playlist_tracks` built by collecting each
    playlist's items via `playlist_items(playlist['id'])`
  - `short_term` / `medium_term` / `long_term` — via `current_user_top_tracks()`
    per time range, concatenated into `top_tracks`
  - `recent_tracks` — via `current_user_recently_played()`
- `try`/`except SpotifyException` wraps the per-playlist fetch — some
  playlists (Spotify-owned algorithmic ones, or licensing-restricted ones)
  403 on `playlist_items()` even though they show up in
  `current_user_playlists()`. These get skipped with a printed message
  instead of crashing the script.
- `print(playlist['name'])` added at the top of the playlist loop for
  progress visibility (the loop is slow — one network round-trip per
  playlist, more for playlists with 50+ tracks).
- Real bug found and fixed via debugging: `playlist_items()` (the newer
  "Get Playlist **Items**" endpoint, as opposed to the older "tracks"
  endpoint) wraps each entry under the key **`'item'`**, not `'track'`.
  `liked_tracks` and `recent_tracks` (different endpoints) do still use
  `'track'`. `top_tracks` items are unwrapped entirely (`item['id']`
  directly, no wrapper key at all). `playlist_tracks_set` now correctly
  uses `item['item']['id']`.
- All four sets built (`liked_tracks_set`, `playlist_tracks_set`,
  `recent_tracks_set`, `top_tracks_set`) via set comprehensions, unioned
  into `all_tracks_set`.
- Print statements for each count fixed (`str(len(...))` pattern — an
  earlier version tried to `+` a string and an int directly, which crashes).

### Caching, added this session (in `scripts/phase0_count_tracks.py`)

- `load_or_fetch(filepath, fetch_fn)` — cache-aside helper. Loads
  `filepath` if it exists; otherwise calls `fetch_fn()` (passed as a
  function/lambda, so the fetch only happens on a cache miss), writes the
  result to `filepath` as JSON, and returns it. All six raw fetches route
  through this; cache files live in `data/` (gitignored).
- `fetch_all_playlist_tracks()` additionally nests a **second**
  `load_or_fetch()` call per playlist, keyed by playlist ID
  (`data/playlist_<id>.json`), on top of the outer
  `load_or_fetch('data/playlist_tracks.json', fetch_all_playlist_tracks)`
  wrapping the whole function. Found this was necessary the hard way: a
  transient network timeout crashed the run partway through the ~30-
  playlist loop, and since the outer cache is all-or-nothing, nothing from
  that pass got saved — a retry would've re-fetched every playlist from
  scratch. Per-playlist caching means a retry only re-fetches what didn't
  finish.
- Docstrings added to all three functions (module + `item_collector` +
  `load_or_fetch` + `fetch_all_playlist_tracks`) — see the docstring
  convention note under Standing Preferences below.

### Not blocking, low priority

- Unused `import os` at the top of `phase0_count_tracks.py` — actually now
  *used*, by `load_or_fetch`'s `os.path.exists()` check. No longer stale,
  nothing to clean up here.

## Known Spotify API gotchas learned so far (relevant beyond Phase 0 too)

- Genre only exists on the **artist** object (`/artists`), never per-track —
  must be joined in via a separate artist fetch, relevant again in Phase 2.
- Audio Features, Audio Analysis, Recommendations, and Related Artists
  endpoints are deprecated (Nov 2024) for apps without pre-existing
  extended quota — don't assume they're available without testing first.
- Some playlists 403 on item fetches even though they're listed — must
  catch and skip (see Phase 0 fix above).
- `playlist_items()` wraps entries under `'item'`, not `'track'` — every
  other source used so far wraps under `'track'` or doesn't wrap at all
  (top tracks). Don't assume nesting is consistent across endpoints —
  check real returned data before writing extraction logic.
- Rate limits can impose very long lockouts (~24h observed, hit once on
  2026-07-31, cleared by 2026-08-03) if hammered with repeated full-library
  re-fetches while debugging. Local caching (`load_or_fetch`, see above) is
  now in place specifically to avoid re-triggering this.

## Full phase roadmap (from the approved plan — see plan file for full detail)

0. Find the actual scale — **DONE**, see above (7,990 unique tracks).
1. Raw data collection + local caching for all sources — Phase 0's
   `load_or_fetch` caching covers this informally already; formalize (move
   into its own module? decide when picking this phase up) as an explicit
   Phase 1 step. **Not started.**
2. Build the clean node table — one row per unique track, dedup (ISRC vs.
   track ID decision), genres joined in from artists, provenance flags per
   source. **Not started.**
3. Compute edge signals separately per candidate pair (shared artist /
   genre / album / playlist co-occurrence), stored as separate columns,
   not collapsed into one weight yet. **Not started.**
4. Turn signals into actual edges: combine into one weight, apply a
   threshold or per-node top-k cap, keep these as tunable config values.
   **Not started.**
5. Build the graph in `python-igraph` + run Leiden community detection
   (built into igraph, no separate `leidenalg` package needed). **Not started.**
6. Layout — hand off to Gephi's GUI (ForceAtlas2 etc.); re-evaluate DrL
   given the 20k-node design target (see above) rather than defaulting to
   "skip it," since that default was based on the plan's original ~5k
   assumption. **Not started.**
7. Static render — still in Gephi, color by Leiden community, export a
   high-res PNG/SVG. **Not started.**
8. Interactive explorer — `pyvis` (Python, generates a self-contained
   interactive HTML file, no JavaScript needed); optional stretch upgrade
   to hand-built `sigma.js` later; free hosting via GitHub Pages. **Not started.**

## Standing preferences (for whoever/whatever picks this up)

- User wants to write **all** implementation code themselves. Default mode
  for assistance: review their code, explain bugs conceptually, answer
  questions, walk through logic — don't write or edit their project code
  unless they explicitly ask for that specific fix in that turn.
- User has "some" prior coding experience — skip basic syntax explanations,
  but explain new concepts (OAuth, pagination, sets, graph algorithms,
  etc.) in plain terms, with free resource links where relevant.
- Budget is $0 — every tool/library choice in the plan was picked
  specifically to avoid any paid service. Flag it clearly if a future step
  would require a real cost, and look for a free alternative first.
- Docstring convention (established `scripts/phase0_count_tracks.py`,
  2026-08-03): every script gets a module-level docstring at the top
  (one-line summary + longer description), every function gets a
  Google-style docstring (`Args:` / `Returns:`). User writes the actual
  descriptions; when scaffolding a new file, add empty `TODO` skeletons in
  this same shape rather than a different style.
- **Scale target: 20,000+ nodes** (set 2026-08-03, after Phase 0's actual
  count came in at 7,990). This is deliberately above today's real number
  — it's a robustness target for library growth, not a current-state fact.
  Evaluate every scale-sensitive decision from here on (Phase 6 layout
  algorithm, Phase 8 interactive explorer performance) against 20k, not
  against 7,990.
