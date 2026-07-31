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

## Phase 0 — Find the actual scale (IN PROGRESS)

**Goal**: count unique tracks across Liked Songs + playlists + top tracks
(3 time ranges) + recently played, to know what we're dealing with before
picking a layout algorithm in Phase 6.

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

### Still to do for Phase 0

1. **BLOCKED until API rate limit clears.** Hit Spotify's rate limit while
   debugging (message: `Retry will occur after: 84765 s`, ≈ 23.5 hours,
   surfaced during the 2026-07-31 evening session). This is Spotify's
   server-enforced limit, not fixable client-side — don't re-run the
   script against the live API until it clears, or the lockout likely
   extends. If picking this up in a new session, check whether enough
   time has passed (~24h from whenever the limit hit) before testing.
2. **Add local JSON caching before running again** — this is the
   immediate next step once unblocked, both to avoid re-triggering the
   rate limit and because it's good practice generally. Design discussed
   but not yet written:
   - Use the built-in `json` module — `json.dump()` to write a list of
     dicts to a file, `json.load()` to read it back, no conversion needed
     since `item_collector`'s output is already plain lists of dicts.
   - Store cache files in `data/` (already gitignored).
   - Cache-aside pattern: before fetching a source, check if its
     `data/<name>.json` file already exists — if so, load it instead of
     hitting the API; if not, fetch normally, then save the result for
     next time.
   - Applies to all six raw fetches: `liked_tracks`, `playlist_tracks`,
     `short_term`, `medium_term`, `long_term`, `recent_tracks`.
   - **Open decision, not yet made**: write the check/load/save logic six
     times (simple, repetitive), or wrap it in one reusable function that
     takes a filename plus "what to do if there's no cache yet" (DRY, but
     introduces passing a function as a value — a new concept vs. what's
     been written so far). Conversation paused here — pick this back up
     before writing the caching code.
3. Once caching is in place and the rate limit has cleared, run the full
   script and confirm the final output: per-source counts (liked /
   playlist / top / recent) plus one deduped grand total. **That total is
   the actual exit condition for Phase 0** — it determines which layout
   algorithm is realistic in Phase 6 (see the plan file: under ~5k tracks,
   any standard force-directed layout is fine; DrL is unnecessary at
   personal-library scale regardless, most likely).
4. Minor cleanup, not blocking: unused `import os` at the top of
   `phase0_count_tracks.py` can be removed if nothing else ends up needing it.

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
- Rate limits can impose very long lockouts (~24h observed) if hammered
  with repeated full-library re-fetches while debugging. Cache raw API
  responses locally as soon as you're iterating on anything downstream of
  a fetch — don't wait for "officially" reaching Phase 1 to start doing this.

## Full phase roadmap (from the approved plan — see plan file for full detail)

0. Find the actual scale — **IN PROGRESS**, see above.
1. Raw data collection + local caching for all sources — partially
   overlapping with Phase 0's caching add-on above; formalize once Phase 0
   is fully done.
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
6. Layout — hand off to Gephi's GUI (ForceAtlas2 etc.), skip DrL unless
   Phase 0's actual number turns out to be surprisingly large. **Not started.**
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
