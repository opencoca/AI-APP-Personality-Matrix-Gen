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

- [ ] **End-to-end validation**: Run full pipeline against Sage AI Labs channel (4 videos, known corpus) #testing #critical
  - [ ] `discover` → 4 videos in index.md
  - [ ] `sample` → all 4 marked `selected`
  - [ ] `fetch` → 4 transcripts fetched with live MCP
  - [ ] `analyze` → analysis.md with all 4 sections populated
  - [ ] `profile` → profile.md with confidence scores + draft system prompt
  - [ ] `status` → shows 4 fetched, 0 pending

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

### Homebrew Release #deployment

- [ ] **Publish v0.1.0**: Tag release, fill SHA256, create tap repo
  - [ ] `make release VERSION=0.1.0` → bump `__version__`, commit, tag
  - [ ] Generate tarball SHA256 from tagged release
  - [ ] Run `brew update-python-resources Formula/yt-analyst.rb` to fill resource hashes
  - [ ] Create `Startr/homebrew-tools` tap repo (or confirm existing tap)
  - [ ] Copy formula to tap and test: `brew tap Startr/tools && brew install yt-analyst`
  - [ ] Verify `yt-analyst --help` works post-install

## Backlog

- [ ] **`--output-dir` flag**: Alias for `--cache-dir`, more intuitive for installed users
- [ ] **`status --all`**: List all cached channel slugs, not just one
- [ ] **Analysis v2 — named entities**: Person names and org names via regex heuristics
- [ ] **Profile diff**: Compare two `profile.md` files to show voice evolution over time
- [ ] **`KANBAN.canvas` setup**: Run TodoScope against this repo and verify board layout

## Bugs

_No known bugs. Use `# BUG:` inline tags in source to flag defects._

## Completed

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
