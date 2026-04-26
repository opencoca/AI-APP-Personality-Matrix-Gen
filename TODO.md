# TODO — yt-analyst

> **Convention** — Sections below map to kanban columns. Inline source-code
> tags use the same vocabulary so items stay cross-referenced between this
> file and the codebase.
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

- [ ] **`--output-dir` flag**: Alias for `--cache-dir`, more intuitive for installed users
- [ ] **`status --all`**: List all cached channel slugs, not just one
- [ ] **Analysis v2 — named entities**: Person names and org names via regex heuristics
- [ ] **Profile diff**: Compare two `profile.md` files to show voice evolution over time
- [ ] **`KANBAN.canvas` setup**: Run TodoScope against this repo and verify board layout

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

### 2026-04-26 — Live pipeline validation and MCP tooling

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
