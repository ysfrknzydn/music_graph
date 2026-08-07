# Music Graph — Project TODO

Living status doc. Read this first when picking the project back up, in any
session, any amount of time later.

## Resume point — start here next session (as of 2026-08-06)

**Blocked on**: a third Spotify rate-limit lockout, hit 2026-08-06 ~20:48
EDT, during a full `phase1_collect_data.py` run. Timeline this round:

1. 2026-08-05 ~00:02: first `ArtistCollector` lockout (`Retry-After: 83316s`,
   ~23.1h) — see gotchas below for full detail.
2. 2026-08-06, before the full run: verified the window had cleared with a
   single live `client.get_artist()` call on an uncached artist ID — it
   succeeded cleanly.
3. 2026-08-06 ~20:48: ran the full `phase1_collect_data.py`. It got through
   all playlist fetching, then into `ArtistCollector.fetch_all()` — **599
   artist calls succeeded** (cached artist count went 597 → 1,196) before
   hitting `Your application has reached a rate/request limit. Retry will
   occur after: 86236 s` (~23.95h). Manually interrupted with Ctrl+C.
   Earliest safe retry: **~2026-08-07 20:45 EDT**.

**Key correction, 2026-08-06**: the single-call verification in step 2 was
necessary but not sufficient — it only proves the limiter isn't tripped at
that instant, not that sustained volume (hundreds of calls in a row) is
safe. The limit is almost certainly a rolling window across the whole app,
which a single call can't detect. The `0.1s` pacing in `_call_with_retry`
held for 599 consecutive calls before failing, so it's not obviously wrong
either, but it's clearly not sufficient on its own for a ~2,368-call batch —
either the delay needs to increase, or the loop needs to check for/back off
before a full-window's worth of calls accumulates. (An earlier note here
also wrongly treated the 2026-07-31 incident's "3 days to clear" as evidence
`Retry-After` itself is unreliable — that was actually just a weekend gap
with no retry attempt, not a measured duration. `Retry-After` appears to be
the accurate signal both times it's been tested.)

**Do not touch the script again — not even a single test call — before the
2026-08-07 ~20:45 EDT window above.**

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

**Next steps, in order** — supersedes the old "just re-run with more
pacing" plan; see "Final genre-collection plan, decided 2026-08-06" under
Phase 1 below for the full reasoning:

1. Add `current_user_top_artists()` (3 calls, one per time range) as a new
   source in `ArtistCollector`/`__main__` — free, zero-risk, returns
   Spotify's own authoritative `genres` field directly for whatever artists
   show up there. Do this regardless of anything else below.
2. Build a small MusicBrainz lookup path (new class, e.g. `MusicbrainzClient`
   — user's call on exact shape) that, for each remaining artist, takes one
   of their tracks' `external_ids.isrc` (already sitting in the cached raw
   track JSON — no new Spotify calls needed to get it), looks up the
   recording via MusicBrainz's ISRC endpoint, and pulls genre tags from the
   resolved artist-credit. Pace at ~1 req/sec (MusicBrainz's documented
   limit); no API key needed, just a descriptive `User-Agent` header per
   their etiquette rules. Tag every artist's genre with its source
   (`spotify_top_artists` / `musicbrainz` / `spotify_direct`) so nothing
   from a non-Spotify source is silently indistinguishable from verified
   data — ties into Phase 2's already-planned provenance columns.
3. Whatever MusicBrainz can't resolve (no ISRC hit, or too obscure to be
   catalogued) falls back to the original plan: `SpotifyClient.get_artist()`
   per remaining ID, budgeted across multiple days via the existing
   per-artist caching (run until the quota trips, resume the next day — see
   "Third rate-limit lockout" gotcha). This remainder should be
   substantially smaller than the full 1,769 artists still outstanding as of
   2026-08-06, but exact size is unknown until step 2 actually runs.
4. Once genre coverage is as complete as steps 1-3 get it: fill in
   `phase1_collect_data.py`'s module docstring — intentionally left as
   `TODO` until the file's full scope is built out.
5. Build `AlbumCollector`, same pattern as `ArtistCollector`.
   `SpotifyClient.get_album()` is already built and ready to use — no
   batching/chunking this time, that lesson's already learned. Same
   quota-wall risk applies here too (unconfirmed whether albums share a
   bucket with artists) — worth watching for the same ~600-call ceiling
   rather than assuming it's artist-specific.
6. Still open from Phase 1's original scope, not yet built: actually
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

### Final genre-collection plan, decided 2026-08-06

Context: three separate rate-limit/quota lockouts (2026-07-31, 2026-08-05,
2026-08-06 — full detail in gotchas below) made it clear that finishing
genre collection via `SpotifyClient.get_artist()` alone means spreading
~1,769 remaining artist fetches (2,965 total unique, 1,196 cached as of
2026-08-06) across several days, since it's a per-developer-account quota
wall, not something pacing can fix. Researched alternatives properly before
committing to one — see "Next steps" above for the resulting plan. Summary
of what was ruled in/out and why:

- **`current_user_top_artists()`** — free, zero risk, not currently called
  anywhere in this project even though `current_user_top_tracks()` is.
  Returns full Spotify Artist objects (genres included) directly. Doing
  this regardless of what else gets built.
- **Last.fm API** — evaluated and **rejected as a genre source**. It's fast
  (5 req/s documented limit, no daily quota) and free, but: (1) Spotify's
  Artist object exposes no MusicBrainz ID or any other cross-reference ID,
  so matching against Last.fm can only be done by artist *name string*, not
  ID; (2) Last.fm's own support forum confirms it cannot reliably
  distinguish two different artists sharing a name — they share a page —
  and its own suggested fix (matching by `mbid`) has confirmed bugs
  returning the wrong artist even when an mbid is supplied, and isn't
  available to us anyway since Spotify gives no mbid; (3) academic research
  on Last.fm's genre tags documents real, non-trivial noise (e.g. blues
  tracks tagged "zydeco"/"cajun"/"swing", disco tagged "80s"/"pop"/"funk") —
  serious enough that papers using Last.fm tags as ground truth only do so
  after cross-dataset aggregation, not from a single artist's raw tag list.
  Given the explicit priority of not letting bad data into the graph, this
  didn't clear the bar.
- **MusicBrainz, via ISRC lookup — chosen instead of Last.fm.** Genre-tag
  noise is actually comparable to Last.fm's (MusicBrainz "genres" are the
  same underlying upvoted/downvoted folksonomy mechanism, and MusicBrainz's
  own docs admit incomplete coverage, especially non-Western genres) — so
  this is *not* a genre-content-quality upgrade. The real win is
  **identity correctness**: Spotify's Track object includes
  `external_ids.isrc` (confirmed against Spotify's API reference), already
  sitting in the raw cached track JSON for free since tracks are cached
  whole. MusicBrainz supports recording lookup by ISRC, resolving to an
  exact artist-credit — no name-guessing, so no same-name-artist collision
  risk. That directly targets the actual failure mode of concern (wrong
  artist's data silently attached to a node), even though the genre-label
  noise itself is a separate, still-present risk shared with Last.fm and,
  to a lesser extent, with Spotify's own genre field. Real caveat: ISRC
  coverage in MusicBrainz isn't complete, particularly for obscure/indie
  tracks — expect a residual fallback set.
- **Multiple developer accounts / Client IDs to dodge the quota** —
  considered and rejected. Spotify's 2026-07-23 quota update explicitly
  moved counting to be *per developer account* rather than per-app, closing
  that loophole. A second Spotify account would technically get a fresh
  quota but risks a Developer ToS violation; not worth the risk for a
  personal project.
- **Unofficial scraping (browser session cookies + account/VPN rotation)**
  — real prior art exists (a GitHub project claiming 13M artists scraped
  this way), but it works by extracting session cookies from logged-in
  accounts and rotating accounts/VPNs specifically to evade Spotify's
  blocking when caught. Not something to replicate — real ToS violation and
  account-ban risk, and ruled out on principle, not just cost/benefit.
- **Precompiled Kaggle/HuggingFace genre datasets** — considered, rejected.
  The well-known ones derive genre from Spotify's now-deprecated
  genre-seed/recommendations search, not the artist's real `genres` field,
  and key by artist name rather than ID — same matching risk as Last.fm,
  plus a less authoritative notion of "genre" than what this project wants.
- **Extended Quota Mode** (would raise Spotify's own limits) — closed off;
  see the "Known constraint" note under Future Direction below. Not
  reachable for a solo project regardless of how this genre problem gets
  solved.

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
- Rate limits can impose very long lockouts (~24h observed via
  `Retry-After`, hit once on 2026-07-31) if hammered with repeated
  full-library re-fetches while debugging. Local caching (`load_or_fetch`,
  see above) is now in place specifically to avoid re-triggering this.
  Note: the 2026-07-31 incident wasn't actually retried until
  2026-08-03 (a weekend gap, not a deliberate wait-and-test), so "cleared by
  2026-08-03" was never a measured lockout duration — don't treat it as
  evidence the stated `Retry-After` window is unreliable (see correction in
  the 2026-08-05 gotcha below and the "Resume point" section at top).
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
- **Third rate-limit lockout, hit 2026-08-06 ~20:48 EDT**: the `time.sleep(0.1)`
  pacing fix added after the second incident was live for this run, and
  still wasn't enough — 599 consecutive `get_artist` calls succeeded (cached
  artist count 597 → 1,196) before `Retry-After: 86236s` (~23.95h) hit.
  Confirms `0.1s` reduces but doesn't eliminate the risk: it's paced enough
  to survive a while, not enough to safely clear a ~2,368-call batch in one
  go. A single isolated test call succeeding earlier the same day (see
  "Resume point" above) did *not* predict this — a lone call can't detect a
  rolling-window limit that only trips under sustained volume. Next attempt
  needs a larger delay (exact value not yet chosen) before re-running the
  full batch. Earliest retry: 2026-08-07 ~20:45 EDT.
- **Correction, 2026-08-06 — this is likely a quota wall, not a rate limit,
  so pacing alone can't fix it**: researched directly against Spotify's own
  docs. Spotify runs two separate limiting systems: the classic rolling
  30-second rate limit (what pacing/backoff protects against), and a
  **quota system** specific to Development Mode apps, added/updated
  2026-07-23, counted per developer account and grouped into per-endpoint
  "quota buckets" with undisclosed limits — explicitly documented as
  "different from rate limits," distinguishable via a `"reason":
  "QUOTA_EXCEEDED"` field in the 429 body (not currently visible in this
  project's logs, since spotipy's own low-level retry consumes the raw
  response before `SpotifyException` ever bubbles up — see the 2026-08-05
  gotcha above). This fits the observed data much better than a rate limit
  would: 0.1s pacing changed nothing about the ~599-600 call ceiling, which
  is what you'd expect from a fixed quota budget (pacing only affects the
  30s rate limit, not a separate quota counter) and not what you'd expect
  from throttling (slower pacing should let more total calls through before
  tripping, not the same count). Practical implication: no delay value
  "solves" this — it only changes how long it takes to hit the same wall.
  The actual fix is budgeting the remaining artist fetches (1,769 as of
  2026-08-06) across multiple days (run until it trips, resume the next day
  — already free via existing per-artist caching), not tuning `time.sleep()`
  further. Sources:
  [Quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes),
  [Web API quota updates for Development Mode (blog)](https://developer.spotify.com/blog/2026-07-23-web-api-quota-updates).
- **Cheap partial mitigation, found 2026-08-06 — `current_user_top_artists()`
  is unused and returns genres for free**: `phase1_collect_data.py` only
  calls `current_user_top_tracks()` (3 time ranges), whose track objects
  carry *simplified* artist sub-objects (id/name only, no genres) — that's
  why every artist needs a follow-up `/artists/{id}` call today. Spotify's
  API reference confirms the sibling endpoint, `Get User's Top Items` with
  `type=artists` (i.e. `current_user_top_artists()`, not currently called
  anywhere in this project), returns full Artist objects — genres,
  followers, popularity, images — directly, in ~3 cheap paginated calls
  total (one per time range), no per-ID fetch needed. Likely (not confirmed)
  in a different quota bucket than `/artists/{id}` catalog calls, since it's
  a different API surface (personalization vs. catalog), meaning it may
  still work even while the artists bucket is cooling down. Worth adding as
  a fifth source in `ArtistCollector`/`__main__` before falling back to
  individual per-ID fetches — shrinks the long-tail count, doesn't
  eliminate it (playlist/liked-song artists that never appear in top
  artists still need individual fetches; full-library genre coverage is a
  fundamentally bigger ask than what "top items"-only apps like Receiptify
  need). Source: [Get User's Top Items reference](https://developer.spotify.com/documentation/web-api/reference/get-users-top-artists-and-tracks).

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
- **Known constraint, corrected 2026-08-06 — this direction is much less
  reachable than previously assumed**: earlier notes here said Development
  Mode caps at "25 registered users" and that sharing more widely "requires
  applying for Extended Quota Mode." Checked directly against Spotify's own
  docs this session:
  - Development Mode's actual authenticated-user cap is **5 users**, not 25.
    The "25" number is a different, unrelated limit — the max number of
    Client IDs (i.e. separate apps) allowed per developer account, raised
    from a lower number in a 2026-07-23 quota-system update. Don't conflate
    the two.
  - Far more importantly: **as of May 2025, Spotify only accepts Extended
    Quota Mode applications from registered businesses/organizations with
    proof of revenue and at least 250,000 Monthly Active Users** — individual
    developers can no longer apply at all, regardless of how good the app
    is. This isn't a matter of applying early; it's currently a closed door
    for a solo personal project. Apps like Receiptify/stats.fm that serve
    many public users almost certainly got production access before this
    policy tightened, not through any technique available to a new
    individual developer today.
  - Net effect: the "public website where others connect their own Spotify
    accounts" idea below is not dead, but its ceiling is Development Mode's
    5-user cap unless/until this project becomes a registered business
    clearing Spotify's 250k-MAU bar — worth knowing now rather than
    discovering it after building the backend/database work described
    below. Sources:
    [Quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes),
    [Extended Quota application requirements (community)](https://community.spotify.com/t5/Spotify-for-Developers/development-mode-to-extended-quota-mode/td-p/7345683).

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
