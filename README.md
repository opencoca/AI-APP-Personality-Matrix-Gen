# yt-analyst

YouTube channel transcript archiver and voice/personality profiler for [Sage.is](https://sage.is) agent personas.

`yt-analyst` runs a five-phase pipeline — discover, sample, fetch, analyze, profile — to build a confidence-scored **personality matrix** from a creator's video transcripts. The output is an empirically-grounded voice profile and draft system prompt ready to power a Sage.is AI agent persona.

---

## Installation

### Development setup

Requires Python 3.10+ and [`uv`](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/Startr/AI-APP-Personality-Matrix-Gen.git
cd AI-APP-Personality-Matrix-Gen
make setup
```

---

## Configuration

`yt-analyst` fetches transcripts via an MCP server. Credentials are loaded in priority order:

| Source | Keys |
|--------|------|
| Project `.env` (highest) | `YT_ANALYST_MCP_URL`, `YT_ANALYST_MCP_TOKEN` |
| `~/.config/vault/secrets` | same |
| `~/.config/yt-analyst/mcp.yaml` (lowest) | `url`, `token` |

Quick global setup:

```bash
echo 'YT_ANALYST_MCP_URL=https://your-tunnel-url.trycloudflare.com' >> ~/.config/vault/secrets
echo 'YT_ANALYST_MCP_TOKEN=your-token-here' >> ~/.config/vault/secrets
```

---

## Usage

### Phase 1 — Discover

Enumerate all videos on a channel and write an `index.md`.

```bash
yt-analyst discover https://www.youtube.com/@YourChannel
# also accepts channel IDs and @handles
```

### Phase 2 — Sample

Select which videos to fetch. For channels with more than 50 videos, applies a smart blend: 15 most recent + up to 30 most popular by view count + random fill up to `--max`.

```bash
yt-analyst sample your-channel-slug
yt-analyst sample your-channel-slug --max 30
```

### Phase 3 — Fetch

Download transcripts via the MCP server with polite rate limiting (3–8 s jitter, session pauses, optional business-hours guard).

```bash
yt-analyst fetch your-channel-slug --mcp-url URL --mcp-token TOKEN

# Fetch a single video without rate limiting
yt-analyst fetch-one VIDEO_ID --mcp-url URL --mcp-token TOKEN
```

Transcripts are stored as Markdown files with YAML frontmatter. A video already on disk is skipped automatically.

### Phase 4 — Analyze

Run offline linguistic analysis against the fetched transcript corpus. No ML frameworks required — pure Python stdlib.

```bash
yt-analyst analyze your-channel-slug
```

Writes `analysis.md` with four sections:

| Section | What it measures |
|---------|-----------------|
| **Vocabulary Fingerprint** | Flesch-Kincaid grade level, type-token ratio, top content words, filler word frequency |
| **Script Structure** | Opening/closing patterns, topic shift frequency |
| **Personality Matrix** | Recurring themes, praise/criticism vocabulary, rhetorical mode, self-reference ratio |
| **Tone & Register** | Formality (passive voice rate), humor signals, audience address style |

### Phase 5 — Profile

Synthesize the analysis into a voice profile with confidence scores and a draft system prompt.

```bash
yt-analyst profile your-channel-slug
```

Writes `profile.md` with:
- Voice characteristics, key vocabulary, structural habits
- **Relevance score** (0.0–1.0): weighted blend of recency, topic diversity, format diversity
- **Accuracy score** (0.0–1.0): weighted blend of sample size, cross-transcript consistency, quality
- Confidence notes (e.g. low sample size warnings, recency gaps)
- Draft system prompt for a Sage.is agent persona

### Utility — Status

```bash
yt-analyst status your-channel-slug
```

Shows fetch progress (fetched / selected / pending / failed) and current confidence scores.

---

## Cache layout

All data lives under `--cache-dir` (default: `scripts/yt-cache/`):

```
scripts/yt-cache/
└── your-channel-slug/
    ├── index.md          # video index with status per entry
    ├── analysis.md       # linguistic analysis output
    ├── profile.md        # voice profile + system prompt
    └── VIDEO_ID.md       # one file per fetched transcript
```

Override the cache root with `--cache-dir PATH` on any command.

---

## Development

```bash
make test            # run pytest
make test_verbose    # verbose output
make test_coverage   # coverage report → htmlcov/
make lint            # ruff check
make format          # ruff format --fix
```

To cut a release:

```bash
make release VERSION=0.2.0
# bumps __version__ in pyproject.toml and yt_analyst/__init__.py
# follow the printed steps to tag and push
```

---

## License

[AGPL-3.0-or-later](LICENSE)
