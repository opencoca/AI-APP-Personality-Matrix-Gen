# yt-analyst

YouTube channel transcript archiver and voice/personality profiler for [Sage.is](https://sage.is) agent personas.

`yt-analyst` walks a creator's channel (or any playlist) through a multi-phase pipeline — **discover → sample → fetch → (clean) → analyze → profile** — and produces an empirically-grounded **personality matrix**: vocabulary, structure, tone, thematic signals, voice profile, and a draft system prompt for a Sage.is agent. Outputs are pure Markdown with YAML frontmatter and Obsidian-friendly wiki links so the whole research library is browsable as a vault.

---

## Installation

Requires Python 3.10+ and [`uv`](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/Startr/AI-APP-Personality-Matrix-Gen.git
cd AI-APP-Personality-Matrix-Gen
make setup
```

Optional extras:

```bash
uv pip install -e ".[punct]"   # BERT-based transcript punctuation restoration
uv pip install -e ".[dev]"     # pytest + ruff
```

---

## Configuration

### MCP transcript server

Used by `fetch` to reach the YouTube transcript API. Credentials load in priority order:

| Source | Keys |
|---|---|
| Project `.env` (highest) | `YT_ANALYST_MCP_URL`, `YT_ANALYST_MCP_TOKEN` |
| `~/.config/vault/secrets` | same |
| `~/.config/yt-analyst/mcp.yaml` (lowest) | `url`, `token` |

For local development, point at a Docker MCP server (`http://localhost:8000`) — see [docs/mcp-cookie-refresh.md](docs/mcp-cookie-refresh.md) for the cookie-refresh workflow.

### LLM enrichment (opt-in)

The `enrich` command works with **any OpenAI-compatible chat completions endpoint** — OpenAI, Anthropic (compat layer), Ollama, LM Studio, Sage.is gateway, etc. Configure via env vars:

| Env var | Default | Purpose |
|---|---|---|
| `YT_ANALYST_LLM_URL` | `https://api.openai.com/v1` | Base URL |
| `YT_ANALYST_LLM_KEY` | (required) | Bearer token |
| `YT_ANALYST_LLM_MODEL` | `gpt-4o-mini` | Model name |

See [docs/llm-enrich.md](docs/llm-enrich.md) for provider-specific examples.

---

## Quickstart

One-shot full pipeline:

```bash
uv run yt-analyst run https://www.youtube.com/@SomeCreator --strategy top --max 20 --clean
```

That chains **discover → sample → fetch → clean → analyze → profile** with conservative defaults (15-45s delay, 3-5 reqs / 120-180s pause). Drop `--clean` to skip BERT punctuation restoration. Stops cleanly on the first failed step — resume from there with the individual command if needed.

### Manual control (per-step)

```bash
uv run yt-analyst discover https://www.youtube.com/@SomeCreator
uv run yt-analyst sample some-creator --strategy top --max 20
uv run yt-analyst fetch some-creator-top --max 20 --delay 15-45 --session-pause 3-5,120-180
uv run yt-analyst clean some-creator-top                        # optional, requires [punct] extra
uv run yt-analyst analyze some-creator-top                      # auto-runs compare + report
uv run yt-analyst profile some-creator-top
```

Every report cross-links to siblings via Obsidian wiki links. Open `scripts/yt-cache/INDEX.md` to browse the whole library.

---

## Commands

### `run` — One-shot full pipeline

```bash
yt-analyst run <URL-or-slug> [--strategy STRAT] [--max N] [--delay MIN-MAX] \
    [--session-pause N-M,S-T] [--clean]
```

Chains **discover → sample → fetch → (clean) → analyze → profile** in one invocation.

- Detects URL vs existing slug (skips discover when given a slug — useful for resuming or re-running with different params)
- Conservative defaults: `--max 20 --delay 15-45 --session-pause 3-5,120-180`
- `--clean` opt-in BERT pass between fetch and analyze
- Auto-fork into `<slug>-<strategy>/` when strategy is non-blend
- Each step logs `━━━ [N/total] Step ━━━` for visibility
- Hard-stops on first failed step (you can resume with the individual command)

### `discover` — Enumerate a channel or playlist

```bash
yt-analyst discover https://www.youtube.com/@Channel
yt-analyst discover "https://www.youtube.com/playlist?list=PLAYLIST_ID"
yt-analyst discover "https://www.youtube.com/watch?v=VIDEO_ID&list=PLAYLIST_ID"
```

Auto-detects playlist URLs (any URL with `list=`) and uses the playlist title for the slug. Channel metadata is captured into `index.md` with a Markdown table of every video, sorted by status, with wiki links to the cached transcript files.

> **Quote URLs in shell** — `&` is a shell metacharacter.

### `sample` — Select which videos to fetch

```bash
yt-analyst sample <slug>                              # blend (default)
yt-analyst sample <slug> --strategy top --max 20      # top by view count
yt-analyst sample <slug> --strategy latest --max 20   # most recent
yt-analyst sample <slug> --strategy random --max 20   # random
```

| Strategy | Behavior |
|---|---|
| `blend` (default) | 15 most recent + top fill by view count + random fill to `--max`. Modifies the slug's index in place. |
| `latest` / `top` / `random` | **Auto-forks** into `<slug>-<strategy>/` so each run is isolated and comparable side-by-side. |

For channels with ≤50 videos, `blend` simply selects every eligible video.

### `fetch` — Download transcripts via MCP (humanized)

```bash
yt-analyst fetch <slug> --max 20 --delay 15-45 --session-pause 3-5,120-180
```

Aggressive defaults (3–8s delay, 25/session) **trigger YouTube IP bans** that block your browser too. The conservative settings above are recommended for any sustained run. Optional flags: `--business-hours`, `--force-retry`. Already-fetched transcripts are skipped on disk (poka-yoke).

### `clean` — BERT punctuation restoration (optional)

```bash
yt-analyst clean <slug>           # only cleans low-density transcripts
yt-analyst clean <slug> --force   # re-clean even if cleaned siblings exist
```

YouTube auto-captions sometimes arrive without sentence boundaries (whole transcripts read as one 311-word run-on, breaking Flesch-Kincaid). The `clean` command runs `deepmultilingualpunctuation` (BERT-based) and writes `{video_id}.cleaned.md` siblings. Originals are never modified. `analyze` automatically prefers the cleaned versions.

Requires the `[punct]` extra (`uv pip install -e ".[punct]"`). Idempotent — re-runs skip already-cleaned transcripts.

### `analyze` — Full linguistic analysis (offline)

```bash
yt-analyst analyze <slug>
```

Buckets transcripts by video duration and writes a per-bucket analysis:
- `analysis.md` — all transcripts (canonical)
- `analysis-shorts.md` — videos < 5 min
- `analysis-mid.md` — videos 5–36 min
- `analysis-long.md` — videos ≥ 36 min

Empty buckets are skipped. Each `analysis.md` has six sections:

| Section | What it captures |
|---|---|
| **Vocabulary Fingerprint** | Flesch-Kincaid grade, type-token ratio, top content words, filler words |
| **Vocabulary Distribution** | Total unique vocab, hapax/dis/tris counts, top-N coverage, ASCII bar chart |
| **Script Structure** | Opening/closing patterns, topic-shift frequency |
| **Personality Matrix** | Recurring themes (≥50% transcripts), praise/criticism vocab, self-reference ratio |
| **Tone & Register** | Passive voice rate, humor signals, dominant audience-address mode |
| **Thematic Signals** | Per-1k-word rates: fear, urgency, hype, promotional CTAs, authority citations, imperatives, comparative framing |

Auto-runs `compare` (when ≥3 buckets exist) and `report` (refreshes the cross-channel `INDEX.md`).

### `profile` — Voice profile + draft system prompt

```bash
yt-analyst profile <slug>
```

Produces `profile.md` (and per-bucket variants) with:
- Voice signature in plain English
- **Relevance** score (recency 40% + topic diversity 30% + format diversity 30%)
- **Accuracy** score (sample size 40% + consistency 35% + transcript quality 25%)
- Confidence notes
- Draft system prompt ready to drop into a Sage.is agent

### `compare` — Cross-bucket divergences

```bash
yt-analyst compare <slug>   # standalone; also auto-runs at end of analyze
```

When a channel has multiple buckets (e.g. shorts + mid + long), generates `compare.md` with side-by-side metrics and **flags >2× divergences** between buckets. Surfaces patterns like "shorts have 4.2× the promotional density of long" — useful for spotting fear-based funnel structures (high-promo shorts → high-fear long-form).

### `report` — Refresh cross-channel library

```bash
yt-analyst report
```

Builds `scripts/yt-cache/INDEX.md` — the cross-channel library index with:
- Channels table: transcripts, words, unique vocab, **Grade**, TTR, Top-100 coverage, Hapax %, Themes count, confidence, buckets
- **Variation Index** ranked by repetitiveness with three-dimensional read (vocab + thematic concentration)
- Quick Profile cards with sibling-report links
- Markdown footnote glossary explaining every column

Auto-runs at the end of `analyze`. Open INDEX.md in Obsidian or SilverBullet for a navigable research vault.

### `enrich` — LLM-derived themes (opt-in)

```bash
yt-analyst enrich <slug>                           # uses 'all' bucket
yt-analyst enrich <slug> --bucket long --yes       # specific bucket, skip prompt
```

Sends concatenated transcripts (capped at 80k chars by default, `--max-chars` overrides) to your configured OpenAI-compatible LLM and writes `themes.md` (or `themes-{bucket}.md`) with six sections: Core Themes, Primary Intent, Narrative Arc, Stance / Worldview, Audience, and (per-bucket only) a Cross-bucket Note.

Cost-transparent — prints estimated tokens and prompts before calling.

### `status` and `fetch-one`

```bash
yt-analyst status <slug>           # fetched/selected/pending/failed counts + confidence
yt-analyst fetch-one VIDEO_ID      # fetch a single transcript (no rate limiting)
```

---

## Output dimensions explained

`INDEX.md` carries footnotes for every metric. The headline ones:

- **Grade** — Flesch-Kincaid US grade level. Run `clean` if a channel's grade looks implausibly high (auto-caption artifact).
- **TTR** — Type-Token Ratio. Lexical variety. Corpus-size sensitive — only fair for similar-size comparisons.
- **Top-100 coverage** — % of speech covered by the 100 most-frequent content words. **Better cross-channel comparison than TTR**. Higher = more formulaic.
- **Hapax %** — Share of unique vocab used exactly once. Long-tail diversity. Casey's vlogs (low) vs Van Neistat's stories (high).
- **Themes count** — Number of words appearing in ≥50% of transcripts. Catches **thematic concentration** that vocabulary metrics miss (e.g. political channels hammering the same names/issues).

Three independent dimensions of variation: lexical (Top-100), long-tail (Hapax), thematic (Themes). A channel can be moderate on one and extreme on another — that's the point.

---

## Cache layout

```
scripts/yt-cache/
├── INDEX.md                       # cross-channel library (auto-refreshed)
├── <slug>/
│   ├── index.md                   # video index + Obsidian-linked table
│   ├── analysis.md                # canonical (all transcripts)
│   ├── analysis-shorts.md         # bucket: < 5 min
│   ├── analysis-mid.md            # bucket: 5–36 min
│   ├── analysis-long.md           # bucket: ≥ 36 min
│   ├── profile.md                 # canonical voice profile
│   ├── profile-{bucket}.md        # per-bucket profiles
│   ├── compare.md                 # cross-bucket comparison (auto)
│   ├── themes.md                  # LLM-derived (only if `enrich` was run)
│   └── transcripts/
│       ├── VIDEO_ID.md            # fetched transcript
│       └── VIDEO_ID.cleaned.md    # BERT-restored sibling (only if `clean` was run)
└── <slug>-top/                    # auto-forked strategy variants
    └── ...                        # same structure as parent
```

Override the cache root with `--cache-dir PATH` on any command. The whole tree is gitignored — it's research output, not source.

---

## Browsing in Obsidian / SilverBullet

Every report has a top-of-file navigation breadcrumb linking to siblings:

```markdown
[[INDEX|← Channel Library]] · [[slug/profile|Voice Profile]] · [[slug/analysis|Full Analysis]] · [[slug/compare|Bucket Comparison]] · ...
```

The cross-channel `INDEX.md` is the entry point — click any channel to dive in, click "← Channel Library" from any report to jump back.

---

## Development

```bash
make test            # pytest
make test_verbose
make test_coverage   # → htmlcov/
make lint            # ruff check
make format          # ruff format --fix
```

Cut a release:

```bash
make release VERSION=0.2.0   # bumps __version__, prints git tag steps
```

---

## License

[AGPL-3.0-or-later](LICENSE)
