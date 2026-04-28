# TODO — yt-analyst

> **Convention** — Sections below map to kanban columns. Inline source-code
> tags use the same vocabulary so items stay cross-referenced between this
> file and the codebase. `KANBAN.canvas` is generated locally by TodoScope
> and is gitignored — do not commit it.
>
> | Column      | Markdown section             | Inline tag  |
> |-------------|------------------------------|-------------|
> | Backlog     | `## Backlog`                 |             |
> | TODO        | `## TODO`                    | `# TODO:`   |
> | In Progress | `## In Progress`             | `# FIXME:`  |
> | Bugs        | `## Bugs`                    | `# BUG:`    |
> | Done        | `- [x]` items / `## Completed` | —         |
>
> `# DEPRECATED:` tags should be tracked as TODO items for removal at the
> stated version.

## In Progress

- [ ] **Conservative fetch defaults** — current defaults (3-8s delay, 25/session) are too aggressive and trigger IP-level YouTube bans that block browser access too #critical
  - [ ] New defaults: 15-45s delay, max 10/session, 3-5 min burst pause
  - [ ] Current aggressive values become `--fast` flag (opt-in, clearly documented as ban-risk)
  - [ ] Update `--help` text to warn about IP bans

- [ ] **MCP cookie updater — hot-swap without restart** #critical
  - [ ] Add `/cookies/reload` endpoint or file-watch on `/app/cookies.txt` to MCP server so cookies can be updated without restarting the container (avoids URL churn)
  - [ ] Update `scripts/refresh-yt-cookies.py` to `docker cp` a Netscape `cookies.txt` and call reload endpoint instead of restarting
  - [ ] Document the new flow in `docs/mcp-cookie-refresh.md`
  - [ ] Coordinate with MCP server repo (or merge since project is ours)

## TODO

### Testing & QA #testing

- [ ] **Unit test coverage**: Expand `cmd_analyze` and `cmd_profile` edge cases
  - [ ] Empty transcript body
  - [ ] Single-transcript analysis (no cross-video theme detection)
  - [ ] Profile fail-fast when analysis.md is missing

- [ ] **Large-channel test**: Validate sampling strategy against 50+ video channel
  - [ ] Confirm recency + popularity + random blend selects ≤50 videos
  - [ ] Confirm `skipped` status applied to remainder

- [ ] **MCP connectivity test**: `fetch-one` against live server with known video
  - [ ] Verify transcript stored as markdown with YAML frontmatter
  - [ ] Verify poka-yoke skips re-fetch on second run


## Backlog

- [ ] **WireGuard inside MCP Docker container**: macOS VPN clients (NordVPN) break cloudflared's WebSocket via kernel-level traffic intercept. Run WireGuard client inside container so cloudflared exits from a clean server IP, avoiding the local VPN conflict. Document as alternative to native MCP server.

- [ ] **Whisper fallback for caption-less channels**: When MCP returns `unavailable`, optionally download audio and transcribe locally via `whisper` CLI — enables channels like @casey that have captions disabled
  - [ ] Add `--whisper` flag to `fetch` to opt in
  - [ ] `yt-dlp --extract-audio` → temp file → `whisper` → parse output → store as transcript
  - [ ] Document as optional dep (not required for normal use)

- [ ] **LLM-based punctuation tier 2**: For transcripts that BERT can't fully resolve (very low-density, long monologues), add an opt-in LLM cleanup path via the existing `enrich` infrastructure. Re-uses `YT_ANALYST_LLM_*` env vars.

- [ ] **YouTube transcript-panel scraping**: Parse `ytInitialData` → `engagementPanels` → `transcriptSearchPanelRenderer` to grab transcripts that channels (e.g. @casey) have disabled at the caption track level but YouTube still indexes for search.

- [ ] **`--output-dir` flag**: Alias for `--cache-dir`, more intuitive for installed users
- [ ] **`status --all`**: List all cached channel slugs, not just one
- [ ] **Analysis v2 — named entities**: Person names and org names via regex heuristics
- [ ] **Profile diff**: Compare two `profile.md` files to show voice evolution over time
- [ ] **TodoScope board verify**: Run TodoScope locally against this repo and confirm the board layout matches expectations (`KANBAN.canvas` is gitignored — local only)

### Homebrew Release #deployment

- [ ] **Publish v0.1.0**: Tag release, fill SHA256, create tap repo
  - [ ] `make release VERSION=0.1.0` → bump `__version__`, commit, tag
  - [ ] Generate tarball SHA256 from tagged release
  - [ ] Run `brew update-python-resources Formula/yt-analyst.rb` to fill resource hashes
  - [ ] Confirm `Startr/homebrew-tools` tap repo or similar 
  - [ ] Copy formula to tap and test: `brew tap Startr/tools && brew install yt-analyst` or similar
  - [ ] Verify `yt-analyst --help` works post-install
  - [ ] Add Homebrew install section back to `README.md` as recommended path

## Bugs

_No known bugs. Use `# BUG:` inline tags in source to flag defects._

## Completed

### 2026-04-28 — LLM enrichment, BERT cleanup, library index

- [x] **Cross-channel `INDEX.md`**: `report` command (auto-runs at end of `analyze`) builds a sortable library index with Channels table, Variation Index ranked by Top-100 coverage, Quick Profile cards, and a markdown footnote glossary explaining every column term
- [x] **Obsidian/SilverBullet wiki link interlinking**: every report has a top-of-file nav breadcrumb (`[[INDEX|← Channel Library]] · [[slug/profile|...]] · ...`) that resolves cleanly in Obsidian and SilverBullet; `_nav_links()` helper auto-skips the current file and missing siblings
- [x] **Vocabulary Distribution analysis** (Zipf shape): total unique vocab, hapax/dis/tris counts, top-N cumulative coverage (20/50/100/500), ASCII rank-frequency bar chart for top 20 words
- [x] **Thematic concentration metric**: `recurring_themes_count` — words appearing in ≥50% of transcripts. Caught what vocab metrics missed (e.g. W3WFocus has moderate Top-100 coverage but 481 recurring themes — political vocabulary saturating every video)
- [x] **Three-dimensional Variation Index** in INDEX.md: lexical (Top-100), long-tail (Hapax %), thematic (Themes count) with auto-interpretation labels per channel
- [x] **Markdown footnote glossary** in INDEX.md: every column header (Tx, Words, Unique, Grade, TTR, Top-100, Hapax, Themes, Confidence, Buckets) has a `[^id]` footnote with caveats and interpretation guidance
- [x] **Playlist URL discover**: `discover` auto-detects URLs with `list=` parameter, uses playlist title for slug, stores `playlist_id` and `source_url` in frontmatter
- [x] **`clean` command — BERT punctuation restoration**: optional `[punct]` extra installs `deepmultilingualpunctuation`; restores sentence boundaries on low-density auto-captions; writes `{video_id}.cleaned.md` siblings (originals untouched); `analyze`/`profile`/`enrich` auto-prefer cleaned versions; idempotent
- [x] **Pin transformers <5** in `[punct]` extra (deepmultilingualpunctuation uses legacy `grouped_entities` pipeline kwarg, removed in transformers 5.x)
- [x] **End-to-end fix validation**: About That (CBC) Grade dropped from 17.1 → 7.6 after BERT cleanup, confirming the punctuation artifact theory

### 2026-04-27 — Sampling strategies, buckets, thematic heuristics, LLM enrichment

- [x] **`sample --strategy {blend|latest|top|random}`**: explicit strategy selection; non-blend strategies auto-fork into `<slug>-<strategy>/` cache directories so runs are isolated and comparable
- [x] **Obsidian-friendly `index.md`**: body becomes a Markdown table of every video with status, views, words, and `[[transcripts/VIDEO_ID|Title]]` wiki links to fetched transcripts; sorted fetched → selected → pending → skipped → failed
- [x] **Duration-bucketed analysis**: every `analyze` walks `("all", "shorts", "mid", "long")` (< 5 min / 5–36 min / ≥ 36 min) and writes `analysis-{bucket}.md` + `profile-{bucket}.md` per bucket with content; empty buckets skipped silently
- [x] **Bucket fallback for missing duration**: `_bucket_for()` falls back to ~150 wpm word-count estimate when `duration_seconds` is absent
- [x] **Thematic Signals analysis section**: 7 new heuristic dimensions with per-1k-word rates and three-tier intensity labels — Fear/threat, Urgency, Hype/superlatives, Promotional CTAs, Authority citations, Imperative directives, Comparative framing
- [x] **Cross-bucket `compare.md`**: auto-runs at end of `analyze` (when ≥3 buckets exist); also `compare` standalone command; surfaces >2× divergences between buckets and a "funnel hypothesis" section flagging shorts-as-promotional-teaser patterns
- [x] **`enrich` command — LLM-derived themes/intent/stance**: opt-in OpenAI-compatible chat completions via `requests`, no SDK; works with OpenAI, Anthropic, Ollama, LM Studio, Sage.is, Groq, etc.; cost-transparent (prints estimated tokens, prompts before calling); writes `themes{-bucket}.md` with Core Themes / Primary Intent / Narrative Arc / Stance / Audience / Cross-bucket Note sections; documented in `docs/llm-enrich.md` with provider examples
- [x] **Live validation across 9 channels**: atmoio, NateBJones, Van Neistat (top 20), Casey Neistat (top + latest), tech-nomics, AI In Context, W3WFocus, About That (CBC playlist) — surfaced real signature differences (e.g. AI In Context shorts have 4.2× promotional density of mid; W3WFocus has 5.6/1k fear language vs CBC's About That at 3.3/1k on same subjects)

- [x] **End-to-end validation**: Full pipeline validated against @atmoio channel (5 transcripts)
  - [x] `discover` → 49 videos, slug correctly derived from `@handle` URL
  - [x] `sample` → all 49 marked `selected` (≤50 cap confirmed)
  - [x] `fetch` → 5 real transcripts fetched, 6 members-only correctly flagged `failed`
  - [x] `analyze` → `analysis.md` populated from 5 transcripts
  - [x] `profile` → `profile.md` with confidence scores + draft system prompt
  - [x] `status` → correct counts reported

- [x] **Bug fix — `cmd_discover` slug**: `@handle` URLs returned `unknown-channel` because yt-dlp flat-playlist entries don't carry channel metadata; fixed with URL regex fallback

- [x] **Bug fix — MCP error masking**: Server returns `200` + error string for gated/unavailable videos; added content guard (`"Error:"` / `"Could not retrieve"`) to mark as `failed` instead of storing junk transcript

- [x] **MCP cookie refresh tooling**: `scripts/refresh-yt-cookies.py` + `docs/mcp-cookie-refresh.md`
  - [x] Reads fresh YouTube cookies from Zen browser profile (sqlite)
  - [x] Recreates Docker container with fresh cookies + correct `--public-mcpo` CMD
  - [x] Waits for new Cloudflare tunnel URL and patches `.env` automatically

### 2026-04-26 — Initial scaffolding and full 5-phase implementation

- [x] **Initial implementation**: Full 5-phase pipeline, greenfield
  - [x] `yt_analyst/cli.py` — single-module CLI, pure stdlib analysis (~500 lines)
  - [x] `yt_analyst/__init__.py` — package with `__version__`
  - [x] `scripts/yt-analyst.py` — thin wrapper for direct invocation
  - [x] `pyproject.toml` — setuptools, entry point, ruff config, Homebrew-ready
  - [x] `Makefile` — Startr-standard variables + UV targets + `make release`
  - [x] `Formula/yt-analyst.rb` — Homebrew formula template with caveats
  - [x] `tests/test_cli.py` — unit tests for core utilities (frontmatter, slugify, FK, cosine)
  - [x] `.gitignore` — comprehensive Python + project-specific excludes
  - [x] `TODO.md` — aligned to TodoScope conventions
  - [x] `.todoscope-exclude.csv` — scanner exclude paths
