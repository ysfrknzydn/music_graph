# Music Graph — Project TODO

Living status doc. Read this first when picking the project back up, in any
session, any amount of time later.

## Resume point — start here next session (as of 2026-08-05)

**Blocked on**: a Spotify rate-limit lockout hit 2026-08-05 while testing
`ArtistCollector` live (full detail in the gotchas section below). Spotify's
own stated `Retry-After` on the last request was ~23h, but treat that as a
lower bound, not a guarantee — the prior 2026-07-31 incident took roughly 3
days to fully clear, not 24h. **Do not re-run
`scripts/phase1_collect_data.py` until confident the window has actually
passed** — retrying while still limited risks resetting or extending the
lockout further, which is part of what happened this time.

**What's already built and reviewed, ready to run once unblocked** — all of
Phase 1's fetch pipeline up through artist collection is done:

- `scripts/spotify_client.py` — `SpotifyClient` class, complete. Auth +
  pagination + one method per raw endpoint, including the singular
  `get_artist`/`get_album` (Spotify removed the old batch endpoints — see
  gotchas). `_call_with_retry` both retries on 429 (`Retry-After`-based
  sleep) and paces every call with a `time.sleep(0.1)` up front.
- `scripts/data_cache.py` — `DataCache` class, complete. Cache-aside +
  per-user-ID namespacing (`data/<user_id>/<filename>`).
- `scripts/phase1_collect_data.py` — `ArtistCollector` class, complete.
  Collects every unique artist ID across all tracks, fetches + caches each
  one individually (`artist_<id>.json`), no batching/chunking (removed
  along with the dead `chunk_ids` method once the API change was
  discovered). `__main__` orchestrates: fetches all four track sources
  (liked, playlists w/ per-playlist try/except-skip + per-playlist
  caching, top tracks x3, recently played), normalizes their differing
  wrapper keys into one flat track list, then runs
  `ArtistCollector.fetch_all()`.
- Whatever artists finished fetching before the 2026-08-05 interrupt are
  already cached on disk (`data/<user_id>/artist_<id>.json`) — a resumed
  run will skip those automatically via `load_or_fetch` and only need to
  fetch whatever's left.
- Already checked and ruled out as a failure cause: local files / podcast
  episodes with `null` artist IDs sneaking into the batch. Live debug
  check confirmed all 2,965 unique artist IDs collected were valid
  (`None in ids? False`) — not the source of the 403s hit earlier.

**Next steps, in order**:

1. Confirm the rate-limit window has actually cleared before touching the
   script again — if unsure, wait longer rather than testing early.
2. Re-run `python3 scripts/phase1_collect_data.py` and let it run to full
   completion this time. Watch whether `0.1`s pacing is actually enough
   (no repeated "rate/request limit" messages); if it still trips the
   limiter, the delay needs to increase.
3. Once a full run succeeds: fill in `phase1_collect_data.py`'s module
   docstring — intentionally left as `TODO` until the file's full scope
   (below) is built out.
4. Build `AlbumCollector`, same pattern as `ArtistCollector`.
   `SpotifyClient.get_album()` is already built and ready to use — no
   batching/chunking this time, that lesson's already learned.
5. Still open from Phase 1's original scope, not yet built: actually
   caching the `/me` profile response (currently only `["id"]` is pulled
   out and used for namespacing every run — the full profile object is
   fetched live but never written through `load_or_fetch`); the `json`
   vs. `sqlite3` raw-storage decision (still an open call, see below).

## Where things live

- Repo: https://github.com/ysfrknzydn/music_graph (public)
- Local path: `/Users/yusuf/Desktop/projects/music_graph`
- Spotify Developer app: named "Music Graph", redirect URI
  `http://127.0.0.1:8888/callback`
- Current working scripts: `scripts/phase0_count_tracks.py` (Phase 0,
  done), `scripts/phase1_collect_data.py` + `scripts/spotify_client.py` +
  `scripts/data_cache.py` (Phase 1, in progress — see "Resume point" above)

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

## Phase 1 — Raw data collection (scope finalized 2026-08-04, IN PROGRESS — blocked, see "Resume point" at top)

**Goal**: pull everything worth having once, cache it locally, structured so
future phases — and a possible future multi-user version — don't require
re-fetching. Per the plan doc, this is also the phase that introduces genre
data (artist-level only, never per-track).

**Decided this session — go broad, prune later**: rather than fetching only
what Phase 2's node table strictly needs, fetch adjacent data now even if
some goes unused, since discovering a gap later means a full re-pass through
the API (and risks repeating the rate-limit lockout hit on 2026-07-31).
Concretely:

- **Artists** — ~~`/artists?ids=` batched ≤50 IDs/call~~ **correction,
  2026-08-04**: Spotify's February 2026 API update removed the bulk
  `GET /artists` endpoint entirely (confirmed against Spotify's own
  changelog/migration guide, not just an error message at face value — see
  gotchas below). Replacement is the singular `GET /artists/{id}` — one
  artist per call, no batching. For every unique artist ID seen across all
  four track sources (from each track's *full* `artists` array, not just
  the primary artist), fetch one at a time, one `load_or_fetch` cache file
  per artist ID (`artist_<id>.json`, same resumability pattern as
  per-playlist caching) rather than per-chunk. **Update, 2026-08-05**: this
  design needs a deliberate small delay between each individual fetch call
  too — running it without pacing triggered a real ~23h rate-limit lockout
  (see gotchas below), since ~2,965 sequential calls with no pause blew
  through Spotify's short-term limit almost instantly.
- **Albums** — same correction applies pre-emptively: `GET /albums` (bulk,
  ≤20 IDs/call) is also removed per the same Feb 2026 change, replaced by
  singular `GET /albums/{id}`. Build `AlbumCollector` around one-at-a-time
  fetching + per-album cache files from the start, don't repeat the
  batching design.
- **Playlists list itself** — `sp.current_user_playlists()` is currently
  only looped over inside `fetch_all_playlist_tracks()`, never cached
  directly. Cache it directly too (owner, collaborative flag, description,
  follower count).
- **`added_at`/`added_by`** on playlist and liked-song items — already
  captured for free, since raw items are cached whole, not reduced to IDs.
- **`/me`** — the current user's own profile. Not in the original plan doc;
  needed for the user-ID namespacing decision below.
- **Skip**: Audio Features, Recommendations, Related Artists — confirmed
  deprecated (see gotchas below), not worth re-testing.

**New design decision — namespace cache by user ID**: cache paths move from
flat `data/liked_tracks.json` to `data/<spotify_user_id>/liked_tracks.json`.
No functional difference today (single user), but cheap to do now vs. a real
retrofit later if the multi-user deploy vision (see "Future direction"
below) becomes more than an idea.

**Open decision**: `json` files (current pattern) vs. `sqlite3` for the raw
cache — plan doc flags this as a live choice, not yet decided.

**Verification**: raw cache track count still matches Phase 0's 7,990;
every artist ID referenced has a cached genre list; every album ID
referenced has a cached full album object.

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
- **Spotify's February 2026 API update removed the bulk catalog-fetch
  endpoints** (`GET /artists`, `GET /albums`, `GET /tracks`, and others —
  all the `?ids=`-batched "get several X" endpoints), replaced by singular
  per-item endpoints (`GET /artists/{id}`, `GET /albums/{id}`, etc.).
  Discovered 2026-08-04 when `ArtistCollector`'s batched `/artists?ids=`
  calls 403'd — confirmed via a live test (a single, definitely-valid
  artist ID also 403'd the same way) and verified directly against
  Spotify's own changelog and migration guide, not assumed from the error
  message alone. This invalidates the original plan doc's "batch-fetch up
  to 50 IDs per call" design for both artists and albums — anything
  fetching catalog data going forward (Phase 1's artist/album collectors,
  and anything similar later) needs to be built around one-item-per-call
  fetching with per-item caching, not batching. Sources: [Feb 2026
  changelog](https://developer.spotify.com/documentation/web-api/references/changes/february-2026),
  [migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide).
- **Second rate-limit lockout, hit 2026-08-05**: switching `ArtistCollector`
  to one-artist-per-call (forced by the Feb 2026 removal above) removed all
  natural pacing between requests — nothing paused between the ~2,965
  individual `get_artist` calls, which blew through Spotify's short-term
  rate limit almost immediately. Retry-After escalated call over call (1s →
  1s → ... → 83316s, ~23h) before being manually cancelled. Same failure
  category as the 2026-07-31 incident above. Important mechanism detail:
  the "Your application has reached a rate/request limit" messages come
  from **spotipy's own internal urllib3-level retry/backoff**, not from
  this project's `_call_with_retry` — that custom retry code never even got
  exercised, since the lower-level retry absorbs 429s and sleeps *before*
  a `SpotifyException` ever bubbles up. Lesson: reactive retry-on-429
  handling isn't sufficient once request volume is high (thousands of
  sequential calls) — needs **proactive pacing** (a deliberate small delay
  between calls in `ArtistCollector.fetch_all`'s loop) to avoid tripping
  the limiter in the first place, not just react to it after the fact.
  Mitigated in part by per-artist caching already being in place: whatever
  artists fetched successfully before the interrupt are saved, so a resumed
  run only needs the remainder. Do not re-run immediately after hitting
  this — retrying while still rate-limited risks extending the lockout.

## Full phase roadmap (from the approved plan — see plan file for full detail)

0. Find the actual scale — **DONE**, see above (7,990 unique tracks).
1. Raw data collection + local caching for all sources — scope finalized
   2026-08-04, since revised to single-item fetching (not batching, see
   gotchas) after Spotify's Feb 2026 API change; see "Phase 1 — Raw data
   collection" section above and "Resume point" at top for full detail.
   Module structure resolved: split into `spotify_client.py` (client) +
   `data_cache.py` (cache) + `phase1_collect_data.py` (collectors +
   orchestration), all class-based per the project's OOP preference.
   **IN PROGRESS** — track fetching + `ArtistCollector` done and reviewed,
   blocked on a rate-limit cooldown as of 2026-08-05; `AlbumCollector` not
   yet built.
2. Build the clean node table — one row per unique track, dedup (ISRC vs.
   track ID decision), genres joined in from artists, provenance flags per
   source. Phase 1's broadened scope makes extra columns available (artist
   followers/popularity, album label/popularity, artist/album images) —
   decide which are worth keeping vs. pruning when this phase is actually
   built; images in particular may be useful later for node icons in Phase
   6/8. **Not started.**
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

## Future direction: refresh automation & multi-user deploy (noted 2026-08-04, not scoped yet)

Not part of the numbered phases yet — captured here so Phase 1's design
(especially the user-ID namespacing decision above) doesn't paint the
project into a corner later. Two things got discussed together in
conversation but are architecturally different:

- **Personal daily refresh** — GitHub Actions cron is a reasonable fit
  (same pattern used on past projects). One real wrinkle to solve when this
  is actually built: the OAuth *refresh token* needs to survive across runs
  (each Action run is a fresh VM) — store it as a GH secret and have the
  script rotate it, rather than relying on the local `.cache` file spotipy
  currently manages.
- **Public website where others connect their own Spotify accounts** — a
  different project shape, not just a bigger version of the above: needs a
  real backend (per-visitor OAuth callback handling), a database instead of
  flat JSON cache files (so per-user data doesn't collide), and a scheduler
  that refreshes many users, not just one. Stays $0-feasible via free tiers
  (e.g. Render/Fly/Vercel + Supabase), but is a genuinely separate build,
  not a bullet point on the existing roadmap.
- **Known constraint, will bite later if forgotten**: the Spotify app is
  currently in **Development Mode, capped at 25 registered users**. Sharing
  with more people than that requires Spotify's Extended Quota Mode
  approval — worth applying for early once this direction is actually
  pursued, since approval isn't instant.

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
- **Data collection philosophy** (set 2026-08-04, Phase 1 scoping): prefer
  grabbing adjacent data now over fetching minimally and re-hitting the API
  later — a missed field discovered downstream costs a full re-pass through
  the API and risks repeating the 2026-07-31 rate-limit lockout. Applies
  most directly to Phase 1 but is a general default going forward: when in
  doubt, over-fetch and prune later rather than the reverse.
