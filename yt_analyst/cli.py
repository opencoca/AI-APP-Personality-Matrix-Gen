"""yt-analyst: YouTube channel transcript archiver and voice profiler."""

from __future__ import annotations

import argparse
import collections
import copy
import datetime
import json
import math
import os
import pathlib
import random
import re
import subprocess
import sys
import time
from typing import Optional

import requests
import yaml

from yt_analyst import __version__

# ─── Constants ────────────────────────────────────────────────────────────────

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "not",
    "no", "nor", "so", "yet", "both", "either", "neither", "each", "few",
    "more", "most", "other", "some", "such", "only", "same", "than", "too",
    "very", "just", "about", "above", "after", "again", "against", "all",
    "also", "am", "any", "because", "before", "between", "during", "here",
    "how", "if", "into", "it", "its", "itself", "me", "my", "myself",
    "now", "once", "our", "out", "own", "re", "s", "she", "he", "her",
    "him", "his", "them", "then", "there", "these", "they", "this",
    "those", "through", "under", "until", "up", "us", "we", "what", "when",
    "where", "which", "while", "who", "whom", "why", "you", "your", "yours",
    "that", "their", "theirs", "t", "d", "ll", "m", "o", "ve", "y",
    "let", "get", "got", "going", "go", "come", "came", "think", "know",
    "see", "look", "want", "need", "make", "made", "say", "said",
    "tell", "told", "take", "took", "give", "gave", "put", "use", "used",
    "find", "found", "keep", "kept", "start", "started", "show", "showed",
    "work", "worked", "mean", "means", "try", "tried", "call", "called",
    "really", "like", "well", "back", "even", "still", "way", "much",
    "right", "thing", "things", "people", "time", "year", "day",
    "part", "place", "case", "week", "number", "point",
    "water", "room", "area", "money", "story", "fact", "month", "lot",
    "new", "good", "high", "old", "great", "big", "small", "large",
    "national", "possible", "public", "early", "free", "long", "little",
    "ever", "never", "already", "around", "actually", "sort", "kind", "bit",
    "um", "uh", "okay", "ok", "yeah", "yes", "oh", "ah", "alright",
    "i", "cant", "dont", "wont", "isnt", "arent", "wasnt", "werent",
    "hasnt", "havent", "hadnt", "didnt", "doesnt",
}

FILLER_WORDS = [
    "you know", "kind of", "sort of", "i mean", "you see",
    "basically", "actually", "literally", "like", "right", "um", "uh",
]

PRAISE_WORDS = {
    "love", "important", "critical", "brilliant", "excellent", "amazing",
    "great", "fantastic", "powerful", "essential", "remarkable", "incredible",
    "beautiful", "perfect", "best", "wonderful", "fascinating", "impressive",
    "transformative", "revolutionary", "genius", "innovative",
}

CRITICISM_WORDS = {
    "wrong", "bad", "problem", "fail", "failed", "failure", "terrible",
    "awful", "broken", "flawed", "mistake", "error", "poor", "weak",
    "dangerous", "misleading", "harmful", "waste", "disappointing", "overrated",
    "broken", "useless", "absurd", "ridiculous",
}

# Fear / threat / risk language — high counts indicate fear-driven framing
FEAR_WORDS = {
    "extinction", "threat", "danger", "dangerous", "doom", "catastrophe",
    "catastrophic", "risk", "crisis", "collapse", "unsafe", "attack",
    "weapon", "war", "destroy", "destroyed", "killing", "kill", "scary",
    "terrifying", "horror", "alarming", "warning", "lose", "losing",
    "uncontrolled", "exterminate",
}

# Time-pressure / urgency markers
URGENCY_WORDS = {
    "now", "urgent", "urgently", "immediately", "asap", "today",
    "deadline", "race", "rush", "quickly", "fast", "soon", "must",
    "before", "behind", "catching",
}

# Hype / superlative excitement — separate from PRAISE_WORDS which is more general
HYPE_WORDS = {
    "revolutionary", "breakthrough", "unprecedented", "historic",
    "mind-blowing", "insane", "unbelievable", "shocking", "wild", "crazy",
    "astonishing",
}

# Promotional CTAs (regex patterns — phrases, not single words)
PROMOTION_PATTERNS = [
    r"full video( link)?( above| below| in (the )?description)?",
    r"watch (the )?(full|whole|entire) (video|episode)",
    r"link in (the )?(description|bio|comments)",
    r"\bsubscribe\b", r"smash (that|the) (like|subscribe)",
    r"if you enjoyed", r"check out (my|our|the) (channel|other)",
    r"more (videos|on this|like this)", r"click (below|here|the link)",
    r"hit the bell", r"join (my|our|the) (channel|community)",
]

# Authority / citation patterns
AUTHORITY_PATTERNS = [
    r"according to", r"research (shows|suggests|indicates)",
    r"(a |the )?study (found|shows|says|suggests)",
    r"scientists (say|believe|warn)", r"experts (agree|warn|say)",
    r"data (shows|suggests)", r"the report (says|finds)",
    r"published in", r"peer[- ]reviewed",
]

# Imperatives (you-directed directives)
IMPERATIVE_PATTERNS = [
    r"\byou should\b", r"\byou must\b", r"\byou need to\b",
    r"\byou have to\b", r"\bremember to\b", r"\bdon'?t (forget|miss)\b",
]

# Comparative framing
COMPARATIVE_PATTERNS = [
    r"\bbetter than\b", r"\bworse than\b", r"\bunlike\b",
    r"\bcompared to\b", r"\binstead of\b", r"\bversus\b",
    r"\bbefore and after\b",
]

FORMAT_KEYWORDS = {
    "presentation": ["presentation", "talk", "keynote", "lecture", "seminar", "speech"],
    "interview": ["interview", "conversation", "chat", "discussion", "dialogue"],
    "tutorial": ["tutorial", "how to", "howto", "guide", "learn", "course", "lesson"],
    "livestream": ["live", "stream", "livestream", "q&a", "qa", "ama"],
    "essay": ["essay", "analysis", "deep dive", "breakdown", "review", "take"],
    "vlog": ["vlog", "day in", "week in", "my life", "update", "behind the scenes"],
}


# ─── Config ───────────────────────────────────────────────────────────────────

_ENV_KEY_MAP = {
    "YT_ANALYST_MCP_URL": "mcp_url",
    "YT_ANALYST_MCP_TOKEN": "mcp_token",
}


def _parse_dotenv(path: pathlib.Path) -> dict:
    """Parse a .env-format file. Handles KEY=VALUE, ignores comments and blanks."""
    result: dict = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return result


def load_mcp_config() -> dict:
    """Load MCP server config from multiple sources.

    Priority order (highest wins):
    1. Project .env in CWD                      — local overrides
    2. ~/.config/vault/secrets                  — global vault (.env format)
    3. scripts/.yt-analyst-mcp.yaml (CWD)       — legacy dev config
    4. ~/.config/yt-analyst/mcp.yaml            — legacy installed config

    .env / vault keys: YT_ANALYST_MCP_URL, YT_ANALYST_MCP_TOKEN
    """
    config: dict = {}

    # Legacy YAML configs — lowest priority; first match wins
    for path in [
        pathlib.Path.home() / ".config" / "yt-analyst" / "mcp.yaml",
        pathlib.Path.cwd() / "scripts" / ".yt-analyst-mcp.yaml",
    ]:
        if path.exists():
            try:
                loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                config.update(loaded)
                break
            except Exception:
                pass

    # Global vault (~/.config/vault/secrets) — overrides legacy YAML
    vault_env = _parse_dotenv(pathlib.Path.home() / ".config" / "vault" / "secrets")
    for env_key, cfg_key in _ENV_KEY_MAP.items():
        if env_key in vault_env:
            config[cfg_key] = vault_env[env_key]

    # Project .env — highest priority, overrides vault
    project_env = _parse_dotenv(pathlib.Path.cwd() / ".env")
    for env_key, cfg_key in _ENV_KEY_MAP.items():
        if env_key in project_env:
            config[cfg_key] = project_env[env_key]

    return config


# ─── Frontmatter ──────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a markdown string. Returns (meta, body)."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    meta = yaml.safe_load(text[4:end]) or {}
    body = text[end + 5:]
    return meta, body


def render_frontmatter(meta: dict, body: str) -> str:
    """Serialize meta dict + body to a markdown string with YAML frontmatter."""
    yaml_str = yaml.dump(
        meta, allow_unicode=True, default_flow_style=False, sort_keys=False
    )
    return f"---\n{yaml_str}---\n\n{body.lstrip()}"


# ─── Paths ────────────────────────────────────────────────────────────────────

def get_cache_root(override: Optional[str] = None) -> pathlib.Path:
    if override:
        return pathlib.Path(override)
    return pathlib.Path.cwd() / "scripts" / "yt-cache"


def channel_cache_dir(slug: str, cache_root: pathlib.Path) -> pathlib.Path:
    d = cache_root / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def index_path(slug: str, cache_root: pathlib.Path) -> pathlib.Path:
    return channel_cache_dir(slug, cache_root) / "index.md"


def transcript_path(slug: str, video_id: str, cache_root: pathlib.Path) -> pathlib.Path:
    t = channel_cache_dir(slug, cache_root) / "transcripts"
    t.mkdir(exist_ok=True)
    return t / f"{video_id}.md"


# Duration buckets (seconds) — used by cmd_analyze/cmd_profile to split a channel
# into shorts/mid/long-form report sets so each tier can be evaluated separately.
# Bounds are [lo, hi); "all" is implicit (every transcript regardless of length).
BUCKET_THRESHOLDS = {
    "shorts": (0, 300),                 # < 5 min  — clips, teasers, micro-content
    "mid":    (300, 2160),              # 5–36 min — typical YouTube essay/vlog
    "long":   (2160, float("inf")),     # ≥ 36 min — long-form documentary/lecture
}


def _bucket_for(duration: float, word_count: int = 0) -> str:
    """Return the bucket name for a video. Falls back to ~150 wpm estimate when duration is missing."""
    if duration <= 0 and word_count > 0:
        duration = (word_count / 150) * 60  # ~150 wpm typical spoken pace
    for name, (lo, hi) in BUCKET_THRESHOLDS.items():
        if lo <= duration < hi:
            return name
    return "long"


def _bucket_suffix(bucket: str) -> str:
    """'all' → '' (canonical filename), other buckets → '-{bucket}'."""
    return "" if bucket == "all" else f"-{bucket}"


def analysis_path(slug: str, cache_root: pathlib.Path, bucket: str = "all") -> pathlib.Path:
    return channel_cache_dir(slug, cache_root) / f"analysis{_bucket_suffix(bucket)}.md"


def profile_path(slug: str, cache_root: pathlib.Path, bucket: str = "all") -> pathlib.Path:
    return channel_cache_dir(slug, cache_root) / f"profile{_bucket_suffix(bucket)}.md"


def _nav_links(slug: str, cache_root: pathlib.Path, current_file: str) -> str:
    """Build a markdown line of Obsidian wiki links to sibling reports in this channel.

    Renders a navigation breadcrumb at the top of each report file so readers can
    jump between profile/analysis/compare/themes/index without leaving their note.
    `current_file` (e.g. 'profile') is excluded from the link list to avoid self-loops.
    """
    chan_dir = channel_cache_dir(slug, cache_root)
    pieces: list[tuple[str, str]] = []  # (filename-without-ext, label)

    if (chan_dir / "index.md").exists() and current_file != "index":
        pieces.append(("index", "Channel Index"))
    if (chan_dir / "profile.md").exists() and current_file != "profile":
        pieces.append(("profile", "Voice Profile"))
    if (chan_dir / "analysis.md").exists() and current_file != "analysis":
        pieces.append(("analysis", "Full Analysis"))
    if (chan_dir / "compare.md").exists() and current_file != "compare":
        pieces.append(("compare", "Bucket Comparison"))
    if (chan_dir / "themes.md").exists() and current_file != "themes":
        pieces.append(("themes", "LLM Themes"))

    # Per-bucket variants — shown only if the current file isn't already that bucket
    for bucket in BUCKET_THRESHOLDS.keys():
        suffix = _bucket_suffix(bucket)
        for kind, label_root in (("analysis", "Analysis"), ("profile", "Profile"), ("themes", "Themes")):
            fname = f"{kind}{suffix}"
            if (chan_dir / f"{fname}.md").exists() and current_file != fname:
                pieces.append((fname, f"{label_root} ({bucket})"))

    links = " · ".join(f"[[{slug}/{name}|{label}]]" for name, label in pieces)
    library = "[[INDEX|← Channel Library]]"
    return f"{library} · {links}\n" if links else f"{library}\n"


# ─── Text & Slug Utilities ────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Convert a channel name to a URL-safe slug."""
    name = name.lower()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-")


def normalize_channel_input(target: str) -> str:
    """Normalize a channel ID, @handle, or URL to a yt-dlp-compatible URL."""
    if target.startswith("http"):
        return target
    if target.startswith("@"):
        return f"https://www.youtube.com/{target}"
    if re.match(r"^UC[a-zA-Z0-9_-]{22}$", target):
        return f"https://www.youtube.com/channel/{target}"
    return f"https://www.youtube.com/@{target}"


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def count_words(text: str) -> int:
    return len(text.split())


def count_syllables(word: str) -> int:
    """Approximate syllable count via vowel-group heuristic with trailing-e correction."""
    word = word.lower().rstrip("e")
    count = len(re.findall(r"[aeiou]+", word))
    return max(1, count)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens with stop words removed."""
    return [w for w in re.findall(r"\b[a-z]+\b", text.lower()) if w not in STOP_WORDS]


def flesch_kincaid_grade(text: str) -> float:
    """Compute Flesch-Kincaid Grade Level."""
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip().split()) >= 3]
    words = re.findall(r"\b[a-z]+\b", text.lower())
    if not sentences or not words:
        return 0.0
    avg_sentence_len = len(words) / len(sentences)
    avg_syllables = sum(count_syllables(w) for w in words) / len(words)
    return (0.39 * avg_sentence_len) + (11.8 * avg_syllables) - 15.59


def cosine_similarity(a: dict[str, int], b: dict[str, int]) -> float:
    """Cosine similarity between two word-frequency dicts. No numpy."""
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    dot = sum(a[k] * b[k] for k in shared)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def window_vectors(tokens: list[str], window: int = 100) -> list[dict[str, int]]:
    """Split token list into fixed-size windows and return frequency dicts."""
    vectors = []
    for i in range(0, len(tokens), window):
        chunk = tokens[i : i + window]
        if len(chunk) >= window // 2:
            vectors.append(dict(collections.Counter(chunk)))
    return vectors


def infer_format(title: str) -> str:
    """Infer video format from title keywords."""
    title_lower = title.lower()
    for fmt, keywords in FORMAT_KEYWORDS.items():
        if any(kw in title_lower for kw in keywords):
            return fmt
    return "unknown"


# ─── Index helpers ────────────────────────────────────────────────────────────

def read_index(slug: str, cache_root: pathlib.Path) -> tuple[dict, str]:
    path = index_path(slug, cache_root)
    if not path.exists():
        return {}, ""
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def write_index(slug: str, meta: dict, body: str, cache_root: pathlib.Path) -> None:
    index_path(slug, cache_root).write_text(render_frontmatter(meta, body), encoding="utf-8")


def _index_body(meta: dict, slug: str = "", cache_root: pathlib.Path = None) -> str:
    videos = meta.get("videos", [])
    fetched = sum(1 for v in videos if v["status"] == "fetched")
    selected = sum(1 for v in videos if v["status"] == "selected")
    total = meta.get("total_videos", len(videos))
    name = meta.get("channel_name", "Channel")

    status_order = {"fetched": 0, "selected": 1, "pending": 2, "skipped": 3, "failed": 4}
    sorted_videos = sorted(videos, key=lambda v: status_order.get(v["status"], 9))

    nav = _nav_links(slug, cache_root, "index") if slug and cache_root else ""

    lines = [
        f"# {name} — Channel Index",
        "",
        nav.rstrip(),
        "",
        f"Discovered {total} videos. {fetched} fetched, {selected} selected.",
        "",
        "| Title | Status | Views | Words |",
        "|-------|--------|-------|-------|",
    ]
    for v in sorted_videos:
        title = v.get("title") or v["id"]
        display = (title[:60] + "…") if len(title) > 60 else title
        status = v["status"]
        views = f"{v['view_count']:,}" if v.get("view_count") else "—"
        words = f"{v['word_count']:,}" if v.get("word_count") else "—"
        if status == "fetched":
            safe = display.replace("|", "\\|")
            title_cell = f"[[transcripts/{v['id']}\\|{safe}]]"
        else:
            title_cell = display
        lines.append(f"| {title_cell} | {status} | {views} | {words} |")

    return "\n".join(lines) + "\n"


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_discover(args) -> None:
    cache_root = get_cache_root(args.cache_dir)
    url = normalize_channel_input(args.target)
    print(f"Discovering videos from: {url}")

    result = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--print-json", "--no-warnings", url],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Error: yt-dlp failed:\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    raw_entries = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        try:
            raw_entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if not raw_entries:
        print("No videos found.", file=sys.stderr)
        sys.exit(1)

    # Playlist mode: when the URL has a `list=` param, treat the playlist as the
    # subject. Use the playlist title for the slug so downstream profile/analysis
    # files belong to the playlist, not whatever channel hosted the first video.
    playlist_id = ""
    m_list = re.search(r"[?&]list=([A-Za-z0-9_-]+)", url)
    if m_list:
        playlist_id = m_list.group(1)
        playlist_title = raw_entries[0].get("playlist_title") or raw_entries[0].get("playlist") or ""
        if playlist_title:
            channel_name = playlist_title
        else:
            channel_name = f"playlist-{playlist_id[:8]}"
        channel_id = raw_entries[0].get("channel_id") or ""
    else:
        channel_name = raw_entries[0].get("channel") or raw_entries[0].get("uploader")
        if not channel_name:
            # yt-dlp flat-playlist entries omit channel on @handle URLs — extract from URL
            m = re.search(r"/@([^/?#]+)", url) or re.search(r"/channel/([^/?#]+)", url)
            channel_name = m.group(1) if m else "unknown-channel"
        channel_id = raw_entries[0].get("channel_id") or ""
    slug = slugify(channel_name)

    new_videos = []
    for v in raw_entries:
        upload = v.get("upload_date") or ""
        date_str = f"{upload[:4]}-{upload[4:6]}-{upload[6:]}" if len(upload) == 8 else upload
        new_videos.append({
            "id": v["id"],
            "title": v.get("title", ""),
            "date": date_str,
            "duration_seconds": v.get("duration") or 0,
            "view_count": v.get("view_count") or 0,
            "status": "pending",
        })

    # Merge: preserve status of entries already in the index
    existing_meta, _ = read_index(slug, cache_root)
    existing_by_id = {v["id"]: v for v in existing_meta.get("videos", [])}
    for v in new_videos:
        if v["id"] in existing_by_id:
            v["status"] = existing_by_id[v["id"]].get("status", "pending")

    meta = {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "discovered": datetime.date.today().isoformat(),
        "total_videos": len(new_videos),
        "videos": new_videos,
    }
    if playlist_id:
        meta["playlist_id"] = playlist_id
        meta["source_url"] = url
    fetched = sum(1 for v in new_videos if v["status"] == "fetched")
    pending = sum(1 for v in new_videos if v["status"] == "pending")
    body = (
        f"# {channel_name} — Channel Index\n\n"
        f"Discovered {len(new_videos)} videos. {fetched} fetched, {pending} pending.\n"
    )
    write_index(slug, meta, body, cache_root)
    print(f"Channel slug: {slug}")
    print(f"Index written: {index_path(slug, cache_root)}")
    print(f"Total videos: {len(new_videos)}")
    return slug


def cmd_sample(args) -> None:
    cache_root = get_cache_root(args.cache_dir)
    slug = args.slug
    strategy = getattr(args, "strategy", "blend")
    target_slug = f"{slug}-{strategy}" if strategy != "blend" else slug

    # Fork parent index into strategy-specific dir on first run
    if strategy != "blend" and not index_path(target_slug, cache_root).exists():
        parent_meta, _ = read_index(slug, cache_root)
        if not parent_meta:
            print(f"No index found for '{slug}'. Run discover first.", file=sys.stderr)
            sys.exit(1)
        fork_meta = copy.deepcopy(parent_meta)
        for v in fork_meta.get("videos", []):
            if v["status"] != "fetched":
                v["status"] = "pending"
        write_index(target_slug, fork_meta, _index_body(fork_meta, target_slug, cache_root), cache_root)
        print(f"  Forked '{slug}' → '{target_slug}'")

    meta, _ = read_index(target_slug, cache_root)
    if not meta:
        print(f"No index found for '{target_slug}'. Run discover first.", file=sys.stderr)
        sys.exit(1)

    videos = meta.get("videos", [])
    max_videos = args.max
    eligible = [v for v in videos if v["status"] in ("pending", "failed")]
    selected_ids: set[str] = set()

    if strategy == "latest":
        for v in sorted(eligible, key=lambda v: v.get("date") or "", reverse=True)[:max_videos]:
            v["status"] = "selected"
            selected_ids.add(v["id"])
        for v in eligible:
            if v["id"] not in selected_ids:
                v["status"] = "skipped"
        selected_count = len(selected_ids)

    elif strategy == "top":
        for v in sorted(eligible, key=lambda v: v.get("view_count") or 0, reverse=True)[:max_videos]:
            v["status"] = "selected"
            selected_ids.add(v["id"])
        for v in eligible:
            if v["id"] not in selected_ids:
                v["status"] = "skipped"
        selected_count = len(selected_ids)

    elif strategy == "random":
        shuffled = eligible[:]
        random.shuffle(shuffled)
        for v in shuffled[:max_videos]:
            v["status"] = "selected"
            selected_ids.add(v["id"])
        for v in eligible:
            if v["id"] not in selected_ids:
                v["status"] = "skipped"
        selected_count = len(selected_ids)

    else:  # blend — original behavior
        if len(videos) <= 50:
            for v in eligible:
                v["status"] = "selected"
            selected_count = len(eligible)
        else:
            for v in sorted(eligible, key=lambda v: v.get("date") or "", reverse=True)[:15]:
                v["status"] = "selected"
                selected_ids.add(v["id"])

            for v in sorted(eligible, key=lambda v: v.get("view_count") or 0, reverse=True):
                if len(selected_ids) >= 30:
                    break
                if v["id"] not in selected_ids:
                    v["status"] = "selected"
                    selected_ids.add(v["id"])

            remaining = [v for v in eligible if v["id"] not in selected_ids]
            random.shuffle(remaining)
            for v in remaining:
                if len(selected_ids) >= max_videos:
                    break
                v["status"] = "selected"
                selected_ids.add(v["id"])

            for v in eligible:
                if v["id"] not in selected_ids:
                    v["status"] = "skipped"

            selected_count = len(selected_ids)

    meta["videos"] = videos
    write_index(target_slug, meta, _index_body(meta, target_slug, cache_root), cache_root)
    print(f"Selected {selected_count} videos for '{target_slug}'.")


def _post_transcript(url: str, token: str, video_id: str) -> tuple[int, str]:
    """POST to MCP transcript endpoint. Returns (status_code, content_or_error)."""
    try:
        resp = requests.post(
            f"{url.rstrip('/')}/get_youtube_transcript",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"video_id": video_id, "format": "clean", "languages": "en"},
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, str):
                content = data
            else:
                content = (
                    data.get("transcript")
                    or data.get("text")
                    or data.get("content")
                    or str(data)
                )
            return 200, content
        return resp.status_code, resp.text
    except requests.exceptions.ConnectionError as e:
        return 0, str(e)


def _is_business_hours() -> bool:
    """True if current UTC time falls within 08:00–22:00 (Atlantic/Azores ≈ UTC)."""
    return 8 <= datetime.datetime.now(datetime.timezone.utc).hour < 22


def cmd_fetch(args) -> None:
    cache_root = get_cache_root(args.cache_dir)
    slug = args.slug
    mcp_cfg = load_mcp_config()
    mcp_url = args.mcp_url or mcp_cfg.get("mcp_url") or ""
    mcp_token = args.mcp_token or mcp_cfg.get("mcp_token") or ""

    if not mcp_url or not mcp_token:
        print(
            "Error: MCP URL and token required.\n"
            "Pass --mcp-url/--mcp-token or create scripts/.yt-analyst-mcp.yaml\n"
            "  (see ~/.config/yt-analyst/mcp.yaml for installed config location)",
            file=sys.stderr,
        )
        sys.exit(1)

    meta, _ = read_index(slug, cache_root)
    if not meta:
        print(f"No index found for '{slug}'.", file=sys.stderr)
        sys.exit(1)

    delay_parts = (args.delay or "3-8").split("-")
    delay_min, delay_max = float(delay_parts[0]), float(delay_parts[-1])
    max_per_session = args.max

    pause_parts = (args.session_pause or "5-8,45-120").split(",")
    pe_min, pe_max = (int(x) for x in pause_parts[0].split("-"))
    pd_min, pd_max = (int(x) for x in pause_parts[1].split("-")) if len(pause_parts) > 1 else (45, 120)

    now = datetime.datetime.now(datetime.timezone.utc)

    def is_retryable(v: dict) -> bool:
        if v["status"] != "failed":
            return False
        if args.force_retry:
            return True
        failed_at = v.get("failed_date") or ""
        if not failed_at:
            return True
        try:
            t = datetime.datetime.fromisoformat(failed_at)
            return (now - t) > datetime.timedelta(hours=24)
        except ValueError:
            return True

    candidates = [
        v for v in meta.get("videos", [])
        if v["status"] == "selected" or is_retryable(v)
    ]
    if not candidates:
        print("Nothing to fetch.")
        return

    request_count = 0
    next_pause_at = random.randint(pe_min, pe_max)

    # Poka-yoke: when N consecutive videos all return "unavailable", that's
    # almost always a systemic problem (stale cookies, IP block, MCP down)
    # rather than every video genuinely lacking captions. Detect and bail with
    # a clear remediation message — and revert the false `failed` markings
    # so the videos retry on next run.
    consecutive_unavailable = 0
    recent_unavailable: list[dict] = []
    SYSTEMIC_UNAVAILABLE_THRESHOLD = 5

    for video in candidates:
        if request_count >= max_per_session:
            print(f"Session limit ({max_per_session}) reached. Run again to continue.")
            break

        if args.business_hours and not _is_business_hours():
            print("Outside business hours. Stopping.")
            break

        video_id = video["id"]
        tx_path = transcript_path(slug, video_id, cache_root)

        # Poka-yoke: file on disk is the canonical source of truth
        if tx_path.exists():
            print(f"  [cached] {video_id} — {video.get('title', '')[:55]}")
            video["status"] = "fetched"
            continue

        print(f"  [fetch]  {video_id} — {video.get('title', '')[:55]}")
        status, content = _post_transcript(mcp_url, mcp_token, video_id)

        if status == 0:
            print(f"Connection error: {content}. Stopping session.", file=sys.stderr)
            write_index(slug, meta, _index_body(meta, slug, cache_root), cache_root)
            sys.exit(1)

        if status == 429:
            print("Rate limited (429). Waiting 120s then retrying...")
            time.sleep(120)
            status, content = _post_transcript(mcp_url, mcp_token, video_id)
            if status == 429:
                print("Still rate limited. Stopping session.", file=sys.stderr)
                write_index(slug, meta, _index_body(meta, slug, cache_root), cache_root)
                sys.exit(1)

        if status >= 500:
            print(f"Server error ({status}). Waiting 60s then retrying...")
            time.sleep(60)
            status, content = _post_transcript(mcp_url, mcp_token, video_id)
            if status >= 500:
                print(f"Still failing ({status}). Marking as failed and continuing.")
                video["status"] = "failed"
                video["error"] = f"HTTP {status}"
                video["failed_date"] = now_iso()
                write_index(slug, meta, _index_body(meta, slug, cache_root), cache_root)
                continue

        if status == 200:
            # MCP returns 200 + error string for gated/unavailable videos
            if content.lstrip().startswith("Error:") or "Could not retrieve a transcript" in content:
                print(f"           ✗ unavailable (members-only or no captions)")
                video["status"] = "failed"
                video["error"] = "unavailable"
                video["failed_date"] = now_iso()
                consecutive_unavailable += 1
                recent_unavailable.append(video)
                write_index(slug, meta, _index_body(meta, slug, cache_root), cache_root)

                if consecutive_unavailable >= SYSTEMIC_UNAVAILABLE_THRESHOLD:
                    # Revert these videos so they retry on next run after the
                    # underlying issue (cookies/IP/MCP) is fixed.
                    for v in recent_unavailable:
                        v["status"] = "selected"
                        v.pop("error", None)
                        v.pop("failed_date", None)
                    write_index(slug, meta, _index_body(meta, slug, cache_root), cache_root)

                    print(
                        f"\n🛑 {consecutive_unavailable} consecutive 'unavailable' responses with no successes.\n"
                        f"   Most YouTube channels have at least some captioned videos, so this is\n"
                        f"   almost always a systemic issue rather than every video lacking captions.\n"
                        f"\n   Common causes & fixes:\n"
                        f"     • Stale cookies   →  python scripts/refresh-yt-cookies.py\n"
                        f"     • IP block        →  try a VPN, different network, or wait\n"
                        f"     • MCP down        →  docker logs youtube-transcribe-server-mcpo\n"
                        f"\n   These {consecutive_unavailable} videos have been reset to 'selected' and will\n"
                        f"   be retried on the next 'fetch {slug}' run after you fix the cause.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                continue

            # Real success — reset the consecutive-failure counter
            consecutive_unavailable = 0
            recent_unavailable = []

            word_ct = count_words(content)
            tx_meta = {
                "video_id": video_id,
                "title": video.get("title", ""),
                "channel": meta.get("channel_name", ""),
                "channel_id": meta.get("channel_id", ""),
                "date": video.get("date", ""),
                "duration_seconds": video.get("duration_seconds", 0),
                "language": "en",
                "transcript_type": "auto-generated",
                "fetched": now_iso(),
                "word_count": word_ct,
            }
            tx_path.write_text(render_frontmatter(tx_meta, content), encoding="utf-8")
            video["status"] = "fetched"
            video["fetched_date"] = now_iso()
            video["word_count"] = word_ct
            print(f"           ✓ {word_ct:,} words")
        else:
            print(f"Unexpected status {status}. Marking as failed.")
            video["status"] = "failed"
            video["error"] = f"HTTP {status}"
            video["failed_date"] = now_iso()

        write_index(slug, meta, _index_body(meta, slug, cache_root), cache_root)
        request_count += 1

        if request_count >= max_per_session:
            break

        time.sleep(random.uniform(delay_min, delay_max))

        if request_count >= next_pause_at:
            pause = random.randint(pd_min, pd_max)
            print(f"  [pause]  reading break ({pause}s)...")
            time.sleep(pause)
            next_pause_at += random.randint(pe_min, pe_max)

    fetched = sum(1 for v in meta["videos"] if v["status"] == "fetched")
    remaining = sum(1 for v in meta["videos"] if v["status"] in ("pending", "selected"))
    print(f"\nSession complete. {fetched} fetched total, {remaining} remaining.")


def cmd_fetch_one(args) -> None:
    mcp_cfg = load_mcp_config()
    mcp_url = args.mcp_url or mcp_cfg.get("mcp_url") or ""
    mcp_token = args.mcp_token or mcp_cfg.get("mcp_token") or ""

    if not mcp_url or not mcp_token:
        print("Error: MCP URL and token required.", file=sys.stderr)
        sys.exit(1)

    video_id = args.video_id
    print(f"Fetching: {video_id}")
    status, content = _post_transcript(mcp_url, mcp_token, video_id)

    if status != 200:
        print(f"Error: HTTP {status}: {content}", file=sys.stderr)
        sys.exit(1)

    # Content guard (parity with cmd_fetch): MCP returns 200 + error string for
    # gated/unavailable videos AND for IP-block conditions. Without this guard
    # we'd happily save the error message as a fake "transcript" — exactly the
    # bug that hid the IP block during William Gallagher debugging.
    if content.lstrip().startswith("Error:") or "Could not retrieve a transcript" in content:
        print(
            f"✗ MCP returned an error string instead of a transcript:\n"
            f"  {content.strip().splitlines()[0][:160]}\n"
            f"  Common causes: stale cookies (refresh-yt-cookies.py), IP block, "
            f"members-only / no-captions video.",
            file=sys.stderr,
        )
        sys.exit(1)

    cache_root = get_cache_root(args.cache_dir)
    out_dir = cache_root / "_single"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{video_id}.md"
    word_ct = count_words(content)
    tx_meta = {"video_id": video_id, "fetched": now_iso(), "word_count": word_ct}
    out_path.write_text(render_frontmatter(tx_meta, content), encoding="utf-8")
    print(f"Saved: {out_path} ({word_ct:,} words)")


# Threshold below which a transcript is considered "needs punctuation cleanup".
# Auto-captions for some channels arrive without sentence boundaries — this wrecks
# Flesch-Kincaid (the whole transcript reads as one giant run-on sentence).
_PUNCT_DENSITY_FLOOR = 1 / 50  # at least 1 sentence-ending mark per 50 words


def _punct_density(body: str) -> float:
    """Return ratio of sentence-ending marks to words."""
    words = len(body.split()) or 1
    marks = body.count(".") + body.count("?") + body.count("!")
    return marks / words


def _cleaned_path(tx_file: pathlib.Path) -> pathlib.Path:
    """Path of the cleaned sibling for a transcript: foo.md → foo.cleaned.md."""
    return tx_file.with_suffix(".cleaned.md")


def cmd_clean(args) -> None:
    """Restore punctuation in low-density transcripts using a BERT model.

    Writes `{video_id}.cleaned.md` siblings; original files are left untouched.
    `cmd_analyze` automatically prefers the cleaned version when present.
    Idempotent — re-runs skip already-cleaned transcripts unless --force.
    """
    try:
        from deepmultilingualpunctuation import PunctuationModel
    except ImportError:
        print(
            "Error: deepmultilingualpunctuation not installed.\n"
            "Install with: uv pip install -e \".[punct]\"\n"
            "(or: uv pip install deepmultilingualpunctuation)",
            file=sys.stderr,
        )
        sys.exit(1)

    cache_root = get_cache_root(args.cache_dir)
    slug = args.slug
    tx_dir = channel_cache_dir(slug, cache_root) / "transcripts"
    if not tx_dir.exists():
        print(f"No transcripts directory for '{slug}'.", file=sys.stderr)
        sys.exit(1)

    # Find candidates: original transcripts (skip *.cleaned.md siblings) where
    # density is below floor and no cleaned sibling exists yet (unless --force).
    candidates: list[tuple[pathlib.Path, dict, str]] = []
    skipped_already_clean = 0
    skipped_dense = 0
    for f in sorted(tx_dir.glob("*.md")):
        if f.name.endswith(".cleaned.md"):
            continue
        cleaned = _cleaned_path(f)
        if cleaned.exists() and not args.force:
            skipped_already_clean += 1
            continue
        meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        if not body.strip():
            continue
        if _punct_density(body) >= _PUNCT_DENSITY_FLOOR and not args.force:
            skipped_dense += 1
            continue
        candidates.append((f, meta, body))

    if skipped_already_clean:
        print(f"  {skipped_already_clean} transcript(s) already cleaned (use --force to redo)")
    if skipped_dense:
        print(f"  {skipped_dense} transcript(s) have sufficient punctuation, skipped")
    if not candidates:
        print(f"Nothing to clean for '{slug}'.")
        return

    print(f"Loading BERT punctuation model (first run downloads ~500MB)...")
    model = PunctuationModel()
    print(f"Cleaning {len(candidates)} transcript(s)...")

    for f, meta, body in candidates:
        before = body.count(".") + body.count("?") + body.count("!")
        # restore_punctuation handles long inputs internally by chunking
        cleaned_body = model.restore_punctuation(body)
        after = cleaned_body.count(".") + cleaned_body.count("?") + cleaned_body.count("!")
        meta["punctuation_status"] = "restored-bert"
        meta["original_sentence_marks"] = before
        meta["restored_sentence_marks"] = after
        _cleaned_path(f).write_text(render_frontmatter(meta, cleaned_body), encoding="utf-8")
        print(f"  {f.name}: {before} → {after} sentence marks")

    print(f"\nDone. Re-run 'analyze {slug}' to use the cleaned transcripts.")


def cmd_analyze(args) -> None:
    cache_root = get_cache_root(args.cache_dir)
    slug = args.slug
    tx_dir = channel_cache_dir(slug, cache_root) / "transcripts"

    if not tx_dir.exists():
        print(f"No transcripts directory for '{slug}'.", file=sys.stderr)
        sys.exit(1)

    # Belt-and-suspenders: scan disk directly, ignore index status
    tx_files = sorted(tx_dir.glob("*.md"))
    if not tx_files:
        print(f"No transcript files in {tx_dir}.", file=sys.stderr)
        sys.exit(1)

    # Prefer cleaned siblings when present — `clean` produces foo.cleaned.md from foo.md
    # so the analysis sees BERT-restored punctuation, fixing FK grade calculation.
    all_transcripts = []
    for tx_file in tx_files:
        if tx_file.name.endswith(".cleaned.md"):
            continue  # cleaned versions handled via their original-file pairing
        cleaned = _cleaned_path(tx_file)
        source = cleaned if cleaned.exists() else tx_file
        meta, body = parse_frontmatter(source.read_text(encoding="utf-8"))
        if body.strip():
            all_transcripts.append({"meta": meta, "body": body})

    if not all_transcripts:
        print("No transcript content found (all files empty?).", file=sys.stderr)
        sys.exit(1)

    # Run analysis once per bucket so each report tier (all/shorts/mid/long) gets its own
    # analysis-{bucket}.md. Empty buckets are skipped silently — no orphan files (poka-yoke).
    for bucket in ("all", *BUCKET_THRESHOLDS.keys()):
        if bucket == "all":
            transcripts = all_transcripts
        else:
            transcripts = [
                t for t in all_transcripts
                if _bucket_for(
                    t["meta"].get("duration_seconds", 0),
                    t["meta"].get("word_count", 0),
                ) == bucket
            ]
        if not transcripts:
            continue
        _analyze_bucket(slug, cache_root, transcripts, bucket)

    # Auto-generate compare.md when there's actually something to compare
    # (need "all" + at least 2 specific buckets for a meaningful comparison).
    existing_buckets = [
        b for b in ("all", *BUCKET_THRESHOLDS.keys())
        if analysis_path(slug, cache_root, b).exists()
    ]
    if len(existing_buckets) >= 3:
        _write_compare(slug, cache_root, existing_buckets)

    # Refresh the cross-channel library index so the new analysis surfaces immediately.
    _write_global_report(cache_root)


def _analyze_bucket(slug: str, cache_root: pathlib.Path, transcripts: list[dict], bucket: str) -> None:
    """Run the full analysis pass on a transcript subset and write analysis-{bucket}.md."""
    label = "all" if bucket == "all" else bucket
    print(f"Analyzing {len(transcripts)} transcript(s) [{label}]...")

    # ── 4a: Vocabulary Fingerprint ──
    all_tokens: list[str] = []
    per_tx_token_sets: list[set[str]] = []
    filler_counts: collections.Counter = collections.Counter()
    all_text = ""

    for t in transcripts:
        body = t["body"]
        all_text += " " + body
        tokens = tokenize(body)
        all_tokens.extend(tokens)
        per_tx_token_sets.append(set(tokens))
        for filler in FILLER_WORDS:
            pattern = r"\b" + re.escape(filler) + r"\b"
            filler_counts[filler] += len(re.findall(pattern, body.lower()))

    word_freq = collections.Counter(all_tokens)
    top_100 = word_freq.most_common(100)
    total_tokens = len(all_tokens)
    ttr = len(set(all_tokens)) / total_tokens if total_tokens else 0.0

    all_words_raw = re.findall(r"\b[a-z]+\b", all_text.lower())
    sentences = [s.strip() for s in re.split(r"[.!?]+", all_text) if len(s.strip().split()) >= 3]
    avg_sentence_len = len(all_words_raw) / len(sentences) if sentences else 0.0
    fk_grade = flesch_kincaid_grade(all_text)
    top_fillers = [(f, c) for f, c in sorted(filler_counts.items(), key=lambda x: -x[1]) if c > 0]

    # ── 4b: Script Structure ──
    opening_patterns: list[str] = []
    closing_patterns: list[str] = []
    total_shifts = 0

    for t in transcripts:
        words = t["body"].split()
        n = len(words)
        if n < 20:
            continue
        window = max(1, n // 10)
        opening = " ".join(words[:window]).lower()
        closing = " ".join(words[-window:]).lower()

        if "?" in opening:
            opening_patterns.append("question-hook")
        if any(kw in opening for kw in ["i was", "i remember", "imagine", "let me tell"]):
            opening_patterns.append("anecdote")
        if any(kw in opening for kw in ["today", "in this video", "going to talk", "going to show"]):
            opening_patterns.append("thesis-statement")
        if not opening_patterns or opening_patterns[-1] not in ("question-hook", "anecdote", "thesis-statement"):
            opening_patterns.append("direct")

        if any(kw in closing for kw in ["subscribe", "follow", "comment below", "check out"]):
            closing_patterns.append("call-to-action")
        if any(kw in closing for kw in ["in summary", "to recap", "in conclusion", "to summarize"]):
            closing_patterns.append("summary")
        if any(kw in closing for kw in ["what do you think", "let me know", "question for you"]):
            closing_patterns.append("open-question")

        vectors = window_vectors(tokenize(t["body"]))
        for i in range(1, len(vectors)):
            if cosine_similarity(vectors[i - 1], vectors[i]) < 0.15:
                total_shifts += 1

    avg_shifts = total_shifts / len(transcripts) if transcripts else 0.0

    # ── 4c: Personality Matrix ──
    threshold = max(1, len(transcripts) * 0.5)
    theme_candidates: collections.Counter = collections.Counter()
    for token_set in per_tx_token_sets:
        for tok in token_set:
            theme_candidates[tok] += 1
    recurring_themes = [
        w for w, c in theme_candidates.items()
        if c >= threshold and w in word_freq
    ]
    # Capture full count BEFORE truncation — that's the thematic-concentration metric
    recurring_themes_total = len(recurring_themes)
    recurring_themes.sort(key=lambda w: -word_freq[w])
    recurring_themes = recurring_themes[:20]

    praise_found = sorted(w for w in word_freq if w in PRAISE_WORDS)
    criticism_found = sorted(w for w in word_freq if w in CRITICISM_WORDS)

    question_count = len(re.findall(r"\?", all_text))
    list_item_count = len(re.findall(r"^[\s]*[-•*]\s", all_text, re.MULTILINE))
    numbered_count = len(re.findall(r"^[\s]*\d+\.\s", all_text, re.MULTILINE))
    self_refs = len(re.findall(r"\b(i|me|my|myself|mine)\b", all_text.lower()))
    ext_refs = len(re.findall(r"\b(they|them|their|it|its|research|studies|experts)\b", all_text.lower()))
    self_ratio = self_refs / (self_refs + ext_refs) if (self_refs + ext_refs) else 0.0

    # ── 4d: Tone & Register ──
    passive_count = len(re.findall(r"\b(is|are|was|were|be|been|being)\s+\w+ed\b", all_text.lower()))
    humor_signals = len(re.findall(r"\b(haha|lol|hilarious|funny|joke)\b|\([^)]{5,50}\)", all_text.lower()))
    you_count = len(re.findall(r"\byou\b", all_text.lower()))
    we_count = len(re.findall(r"\bwe\b", all_text.lower()))
    one_count = len(re.findall(r"\bone\b", all_text.lower()))

    # ── Write analysis.md ──
    total_words = len(all_words_raw)
    date_range = _compute_date_range(transcripts)
    channel = transcripts[0]["meta"].get("channel", slug) if transcripts else slug

    filler_lines = "\n".join(f'- "{f}": {c} occurrences' for f, c in top_fillers[:8]) or "None detected."
    top_30_str = ", ".join(w for w, _ in top_100[:30])
    themes_str = ", ".join(recurring_themes[:15]) if recurring_themes else "Insufficient sample."

    # ── Vocabulary Distribution (Zipfian shape) ──
    # word_freq counts CONTENT tokens (after STOP_WORDS filter via tokenize()), so
    # numbers reflect a creator's content vocabulary, not common-word noise.
    total_unique = len(word_freq)
    sorted_counts = sorted(word_freq.values(), reverse=True)
    hapax_count = sum(1 for c in sorted_counts if c == 1)
    dis_count = sum(1 for c in sorted_counts if c == 2)
    tris_count = sum(1 for c in sorted_counts if c == 3)
    once_pct = (hapax_count / total_unique * 100) if total_unique else 0.0

    # Cumulative coverage: how much of total speech is covered by the top N words
    def _coverage(top_n: int) -> float:
        if not total_tokens or not sorted_counts:
            return 0.0
        return sum(sorted_counts[:top_n]) / total_tokens * 100

    cov_20 = _coverage(20)
    cov_50 = _coverage(50)
    cov_100 = _coverage(100)
    cov_500 = _coverage(500)

    # ASCII bar chart: top 20 words, bar length scaled to max count
    bar_max = top_100[0][1] if top_100 else 1
    chart_lines = []
    for word, count in top_100[:20]:
        bar = "█" * max(1, int((count / bar_max) * 30))
        chart_lines.append(f"{word:<14} {bar} {count}")
    chart_block = "\n".join(chart_lines) if chart_lines else "(no content words found)"

    vocab_section = f"""## Vocabulary Fingerprint

Analyzed {len(transcripts)} transcript(s) totalling {total_words:,} words across {len(sentences):,} sentences.

**Reading level:** Flesch-Kincaid Grade {fk_grade:.1f} ({_fk_label(fk_grade)})
**Average sentence length:** {avg_sentence_len:.1f} words
**Vocabulary richness (type-token ratio):** {ttr:.3f}

**Top content words:** {top_30_str}

**Filler words / verbal tics:**
{filler_lines}

## Vocabulary Distribution

**Total unique content words:** {total_unique:,}
**Total content tokens:** {total_tokens:,}

**Long-tail shape:**
- Used exactly once (hapax): {hapax_count:,} ({once_pct:.1f}% of unique vocab)
- Used twice: {dis_count:,}
- Used three times: {tris_count:,}

**Cumulative coverage** — how much of total content speech is covered by the top N words:
- Top 20 words: {cov_20:.1f}%
- Top 50 words: {cov_50:.1f}%
- Top 100 words: {cov_100:.1f}%
- Top 500 words: {cov_500:.1f}%

**Top 20 by frequency:**

```
{chart_block}
```
"""

    structure_section = f"""## Script Structure

**Opening patterns detected:** {", ".join(sorted(set(opening_patterns))) or "unclear"}
**Closing patterns detected:** {", ".join(sorted(set(closing_patterns))) or "unclear"}
**Average topic shifts per transcript:** {avg_shifts:.1f}
"""

    personality_section = f"""## Personality Matrix

**Recurring themes (in >50% of transcripts):**
{themes_str}

**Values — frequently praised:** {", ".join(praise_found) or "none detected"}
**Values — frequently criticized:** {", ".join(criticism_found) or "none detected"}

**Rhetorical mode:** {question_count} questions, {list_item_count + numbered_count} list items across all transcripts.
**Self-reference ratio:** {self_ratio:.2f} ({_self_ratio_label(self_ratio)})
"""

    tone_section = f"""## Tone & Register

**Formality:** {passive_count} passive constructions ({_formality_label(passive_count, total_words)})
**Humor signals:** {humor_signals} instances (laughter markers, parenthetical asides)
**Audience address:** {you_count} uses of "you" (direct), {we_count} uses of "we" (inclusive), {one_count} uses of "one" (authoritative)
**Dominant mode:** {_dominant_address(you_count, we_count, one_count)}
"""

    # ── 4e: Thematic Signals ──
    # Per-1000-word rates so buckets/channels compare fairly.
    def _rate(count: int) -> float:
        return (count / total_words * 1000) if total_words else 0.0

    fear_count = sum(word_freq.get(w, 0) for w in FEAR_WORDS)
    urgency_count = sum(word_freq.get(w, 0) for w in URGENCY_WORDS)
    hype_count = sum(word_freq.get(w, 0) for w in HYPE_WORDS)

    def _pattern_count(patterns: list[str]) -> int:
        return sum(len(re.findall(p, all_text.lower())) for p in patterns)

    promo_count = _pattern_count(PROMOTION_PATTERNS)
    authority_count = _pattern_count(AUTHORITY_PATTERNS)
    imperative_count = _pattern_count(IMPERATIVE_PATTERNS)
    comparative_count = _pattern_count(COMPARATIVE_PATTERNS)

    fear_top = sorted([w for w in FEAR_WORDS if w in word_freq], key=lambda w: -word_freq[w])[:6]
    urgency_top = sorted([w for w in URGENCY_WORDS if w in word_freq], key=lambda w: -word_freq[w])[:6]
    hype_top = sorted([w for w in HYPE_WORDS if w in word_freq], key=lambda w: -word_freq[w])[:6]

    thematic_section = f"""## Thematic Signals

Rates are per 1,000 words of total transcript content.

**Fear / threat language:** {fear_count} ({_rate(fear_count):.1f}/1k, {_intensity_label(_rate(fear_count), 2, 5)})
  Top: {", ".join(fear_top) or "none"}
**Urgency markers:** {urgency_count} ({_rate(urgency_count):.1f}/1k, {_intensity_label(_rate(urgency_count), 3, 8)})
  Top: {", ".join(urgency_top) or "none"}
**Hype / superlatives:** {hype_count} ({_rate(hype_count):.1f}/1k, {_intensity_label(_rate(hype_count), 1, 3)})
  Top: {", ".join(hype_top) or "none"}
**Promotional CTAs:** {promo_count} ({_rate(promo_count):.1f}/1k, {_intensity_label(_rate(promo_count), 0.5, 2)})
**Authority citations:** {authority_count} ({_rate(authority_count):.1f}/1k, {_intensity_label(_rate(authority_count), 0.3, 1)})
**Imperative directives:** {imperative_count} ({_rate(imperative_count):.1f}/1k, {_intensity_label(_rate(imperative_count), 1, 3)})
**Comparative framing:** {comparative_count} ({_rate(comparative_count):.1f}/1k, {_intensity_label(_rate(comparative_count), 0.5, 2)})
"""

    nav = _nav_links(slug, cache_root, f"analysis{_bucket_suffix(bucket)}")
    title = f"# Analysis: {channel}" + (f" ({bucket})" if bucket != "all" else "")
    body = f"{title}\n\n{nav}\n{vocab_section}\n{structure_section}\n{personality_section}\n{tone_section}\n{thematic_section}"
    an_meta = {
        "subject": channel,
        "channel": channel,
        "bucket": bucket,
        "generated": datetime.date.today().isoformat(),
        "transcripts_analyzed": len(transcripts),
        "date_range": date_range,
        "total_words_analyzed": total_words,
        # Vocab shape — surfaced in compare.md for cross-bucket Zipf comparison
        "total_unique": total_unique,
        "total_tokens": total_tokens,
        "hapax_count": hapax_count,
        "ttr": round(ttr, 4),
        "top_100_coverage_pct": round(cov_100, 2),
        "fk_grade": round(fk_grade, 1),
        # Thematic concentration: # words appearing in ≥50% of transcripts.
        # High count = same handful of subjects hammered across videos.
        "recurring_themes_count": recurring_themes_total,
        # Raw counts for cross-bucket comparison (compare.md reads frontmatter, not body)
        "fear_count": fear_count,
        "urgency_count": urgency_count,
        "hype_count": hype_count,
        "promo_count": promo_count,
        "authority_count": authority_count,
        "imperative_count": imperative_count,
        "comparative_count": comparative_count,
    }
    out = analysis_path(slug, cache_root, bucket)
    out.write_text(render_frontmatter(an_meta, body), encoding="utf-8")
    print(f"  Written: {out.name}")


def _fk_label(grade: float) -> str:
    if grade < 6: return "very accessible"
    if grade < 9: return "accessible"
    if grade < 12: return "standard"
    if grade < 16: return "college-level"
    return "graduate-level"


def _self_ratio_label(r: float) -> str:
    if r > 0.7: return "strongly personal/experiential"
    if r > 0.4: return "balanced personal and external"
    return "primarily evidence/external-focused"


def _formality_label(passive: int, total: int) -> str:
    rate = passive / total * 100 if total else 0
    if rate < 1: return "conversational"
    if rate < 3: return "moderately formal"
    return "formal"


def _dominant_address(you: int, we: int, one: int) -> str:
    m = max(you, we, one)
    if m == you: return "direct (second-person dominant)"
    if m == we: return "inclusive (first-person plural dominant)"
    return "authoritative (impersonal dominant)"


def _intensity_label(rate: float, mod_threshold: float, high_threshold: float) -> str:
    """Three-tier label for per-1k-word rates. Thresholds tuned per dimension."""
    if rate >= high_threshold: return "high"
    if rate >= mod_threshold: return "moderate"
    return "low"


def _compute_date_range(transcripts: list[dict]) -> str:
    dates = [str(t["meta"].get("date", ""))[:7] for t in transcripts if t["meta"].get("date")]
    if not dates:
        return "unknown"
    return f"{min(dates)} to {max(dates)}"


# Dimensions surfaced in compare.md — keep keys aligned with frontmatter fields written
# by _analyze_bucket so the comparison can read them without re-parsing the body.
_COMPARE_DIMENSIONS = [
    ("fear",        "Fear / threat"),
    ("urgency",     "Urgency"),
    ("hype",        "Hype / superlatives"),
    ("promo",       "Promotional CTAs"),
    ("authority",   "Authority citations"),
    ("imperative",  "Imperative directives"),
    ("comparative", "Comparative framing"),
]


def _write_compare(slug: str, cache_root: pathlib.Path, buckets: list[str]) -> None:
    """Write compare.md showing thematic divergences across buckets."""
    rows = []
    for b in buckets:
        meta, _ = parse_frontmatter(analysis_path(slug, cache_root, b).read_text(encoding="utf-8"))
        words = meta.get("total_words_analyzed", 0) or 1
        unique = meta.get("total_unique", 0)
        hapax = meta.get("hapax_count", 0)
        row = {
            "bucket": b,
            "transcripts": meta.get("transcripts_analyzed", 0),
            "words": meta.get("total_words_analyzed", 0),
            "total_unique": unique,
            "ttr": meta.get("ttr", 0.0),
            "hapax_pct": (hapax / unique * 100) if unique else 0.0,
            "top_100_coverage_pct": meta.get("top_100_coverage_pct", 0.0),
        }
        for key, _ in _COMPARE_DIMENSIONS:
            row[f"{key}_per_1k"] = (meta.get(f"{key}_count", 0) / words) * 1000
        rows.append(row)

    # Side-by-side table — one column per bucket
    header = "| Metric | " + " | ".join(r["bucket"] for r in rows) + " |"
    sep = "|" + "---|" * (len(rows) + 1)
    table_lines = [header, sep]
    table_lines.append("| transcripts | " + " | ".join(str(r["transcripts"]) for r in rows) + " |")
    table_lines.append("| words | " + " | ".join(f"{r['words']:,}" for r in rows) + " |")
    table_lines.append("| total unique vocab | " + " | ".join(f"{r['total_unique']:,}" for r in rows) + " |")
    table_lines.append("| TTR | " + " | ".join(f"{r['ttr']:.3f}" for r in rows) + " |")
    table_lines.append("| hapax % of vocab | " + " | ".join(f"{r['hapax_pct']:.1f}%" for r in rows) + " |")
    table_lines.append("| top-100 coverage | " + " | ".join(f"{r['top_100_coverage_pct']:.1f}%" for r in rows) + " |")
    for key, label in _COMPARE_DIMENSIONS:
        cells = " | ".join(f"{r[f'{key}_per_1k']:.2f}" for r in rows)
        table_lines.append(f"| {label} (/1k) | {cells} |")
    table = "\n".join(table_lines)

    # Notable divergences: any pair of non-"all" buckets with >2x ratio on a dimension.
    # Surfaces "shorts have 4× the promo density of long" style insights.
    specific = [r for r in rows if r["bucket"] != "all"]
    divergences = []
    for key, label in _COMPARE_DIMENSIONS:
        for i, a in enumerate(specific):
            for b in specific[i + 1:]:
                a_rate = a[f"{key}_per_1k"]
                b_rate = b[f"{key}_per_1k"]
                if a_rate < 0.1 and b_rate < 0.1:
                    continue  # both negligible
                hi, lo = (a, b) if a_rate >= b_rate else (b, a)
                hi_r, lo_r = (a_rate, b_rate) if a_rate >= b_rate else (b_rate, a_rate)
                if lo_r > 0 and hi_r / lo_r >= 2:
                    divergences.append(
                        f"- **{label}**: `{hi['bucket']}` shows {hi_r/lo_r:.1f}× the rate of `{lo['bucket']}` "
                        f"({hi_r:.2f} vs {lo_r:.2f} per 1k)"
                    )
                elif lo_r == 0 and hi_r > 0.3:
                    divergences.append(
                        f"- **{label}**: present in `{hi['bucket']}` ({hi_r:.2f}/1k) but absent in `{lo['bucket']}`"
                    )
    divergences_section = "\n".join(divergences) if divergences else "_No >2× divergences detected._"

    # Funnel hypothesis: if shorts have high promo + low fear AND long has high fear,
    # this looks like a "shorts as teaser for fear-based long-form" pattern.
    funnel_note = ""
    by_bucket = {r["bucket"]: r for r in rows}
    if "shorts" in by_bucket and "long" in by_bucket:
        s, l = by_bucket["shorts"], by_bucket["long"]
        if s["promo_per_1k"] >= 1 and l["fear_per_1k"] >= 3:
            funnel_note = (
                "\n## Funnel Hypothesis\n\n"
                f"Shorts show high promotional density ({s['promo_per_1k']:.2f}/1k) "
                f"while long-form shows high fear/threat density ({l['fear_per_1k']:.2f}/1k). "
                "This pattern is consistent with using short clips to funnel viewers "
                "toward fear-driven long-form content.\n"
            )

    nav = _nav_links(slug, cache_root, "compare")
    body = (
        f"# Cross-Bucket Comparison: {slug}\n\n"
        f"{nav}\n"
        f"Comparing {len(rows)} buckets: {', '.join(r['bucket'] for r in rows)}.\n"
        f"Rates per 1,000 words.\n\n"
        f"## Metrics\n\n{table}\n\n"
        f"## Notable Divergences\n\n{divergences_section}\n"
        f"{funnel_note}"
    )
    cmp_meta = {
        "slug": slug,
        "generated": datetime.date.today().isoformat(),
        "buckets_compared": [r["bucket"] for r in rows],
    }
    out = channel_cache_dir(slug, cache_root) / "compare.md"
    out.write_text(render_frontmatter(cmp_meta, body), encoding="utf-8")
    print(f"  Written: compare.md")


def cmd_compare(args) -> None:
    """Standalone: regenerate compare.md from existing analysis-*.md files."""
    cache_root = get_cache_root(args.cache_dir)
    slug = args.slug
    existing = [
        b for b in ("all", *BUCKET_THRESHOLDS.keys())
        if analysis_path(slug, cache_root, b).exists()
    ]
    if len(existing) < 2:
        print(
            f"Need at least 2 bucket analyses for '{slug}'. "
            f"Run 'yt-analyst analyze {slug}' first.",
            file=sys.stderr,
        )
        sys.exit(1)
    _write_compare(slug, cache_root, existing)


def _write_global_report(cache_root: pathlib.Path) -> None:
    """Build INDEX.md at cache root: cross-channel summary with Obsidian wiki links.

    Scans all channel subdirs that have a profile.md (i.e., have been analyzed)
    and produces a sortable table + per-channel quick cards. This is the entry
    point for browsing the research collection in Obsidian / SilverBullet.
    """
    rows = []
    if not cache_root.exists():
        print(f"Cache root not found: {cache_root}", file=sys.stderr)
        return

    for chan_dir in sorted(cache_root.iterdir()):
        if not chan_dir.is_dir() or chan_dir.name.startswith("_"):
            continue
        prof = chan_dir / "profile.md"
        if not prof.exists():
            continue
        an = chan_dir / "analysis.md"
        prof_meta, _ = parse_frontmatter(prof.read_text(encoding="utf-8"))
        an_meta = {}
        if an.exists():
            an_meta, _ = parse_frontmatter(an.read_text(encoding="utf-8"))

        # Which buckets have reports?
        buckets_present = [
            b for b in ("shorts", "mid", "long")
            if (chan_dir / f"profile-{b}.md").exists()
        ]
        unique = an_meta.get("total_unique", 0)
        hapax = an_meta.get("hapax_count", 0)
        rows.append({
            "slug": chan_dir.name,
            "channel": prof_meta.get("channel", chan_dir.name),
            "transcripts": prof_meta.get("transcripts_used", 0),
            "words": an_meta.get("total_words_analyzed", 0),
            "unique": unique,
            "ttr": an_meta.get("ttr", 0.0),
            "fk_grade": an_meta.get("fk_grade", 0.0),
            "top100_pct": an_meta.get("top_100_coverage_pct", 0.0),
            "hapax_pct": (hapax / unique * 100) if unique else 0.0,
            "themes_count": an_meta.get("recurring_themes_count", 0),
            "relevance": prof_meta.get("relevance", 0.0),
            "accuracy": prof_meta.get("accuracy", 0.0),
            "generated": prof_meta.get("generated", "—"),
            "buckets": buckets_present,
            "has_compare": (chan_dir / "compare.md").exists(),
            "has_themes": (chan_dir / "themes.md").exists(),
        })

    if not rows:
        print(f"No analyzed channels in {cache_root} — nothing to report.", file=sys.stderr)
        return

    # Sort by transcripts desc (richest research first), then channel name
    rows.sort(key=lambda r: (-r["transcripts"], r["slug"]))

    # Disambiguate any rows that share a display name. This is the poka-yoke
    # backstop for strategy forks (casey-top + casey-latest both have
    # channel_name="casey"), accidental duplicates, or any future fork pattern —
    # we don't enumerate strategy names, we just react to actual collisions.
    name_counts = collections.Counter(r["channel"] for r in rows)
    for r in rows:
        if name_counts[r["channel"]] > 1:
            chan_slug = slugify(r["channel"])
            if r["slug"].startswith(f"{chan_slug}-"):
                # Slug follows {channel}-{suffix} pattern → use clean suffix
                r["channel"] = f"{r['channel']} ({r['slug'][len(chan_slug) + 1:]})"
            else:
                # Fallback: use the slug itself as the disambiguator
                r["channel"] = f"{r['channel']} [{r['slug']}]"

    # Summary table — one row per channel, link goes to channel index.md.
    # Top-100% and Hapax% expose vocabulary variation: high Top-100 = repetitive
    # (formulaic), high Hapax = varied (each video introduces unique nouns).
    # Column headers carry markdown footnote refs ([^id]) — definitions live at
    # the bottom of the body and render in Obsidian/SilverBullet on hover/click.
    table_header = (
        "| Channel | Tx[^tx] | Words[^words] | Unique[^unique] | Grade[^grade] | "
        "TTR[^ttr] | Top-100[^top100] | Hapax[^hapax] | Themes[^themes] | "
        "Confidence[^conf] | Buckets[^buckets] |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"
    )
    table_rows = []
    for r in rows:
        chan_link = f"[[{r['slug']}/index\\|{r['channel']}]]"
        bucket_links = []
        for b in r["buckets"]:
            bucket_links.append(f"[[{r['slug']}/profile-{b}\\|{b}]]")
        bucket_cell = " · ".join(bucket_links) or "—"
        confidence = f"{r['relevance']:.2f} / {r['accuracy']:.2f}"
        table_rows.append(
            f"| {chan_link} | {r['transcripts']} | {r['words']:,} | {r['unique']:,} | "
            f"{r['fk_grade']:.1f} | {r['ttr']:.3f} | {r['top100_pct']:.1f}% | "
            f"{r['hapax_pct']:.1f}% | {r['themes_count']} | {confidence} | {bucket_cell} |"
        )
    table = table_header + "\n" + "\n".join(table_rows)

    # Variation Index — sort by Top-100 coverage descending. High coverage = a
    # small set of words covers most of the speech = repetitive / formulaic.
    # Low coverage = vocabulary spreads across many words = varied / wide-ranging.
    variation_rows = sorted(rows, key=lambda r: -r["top100_pct"])
    variation_header = (
        "| Channel | Top-100[^top100] covers | Hapax[^hapax] % | TTR[^ttr] | Themes[^themes] | Read |\n"
        "|---|---:|---:|---:|---:|---|"
    )
    variation_lines = [variation_header]
    for r in variation_rows:
        chan_link = f"[[{r['slug']}/profile\\|{r['channel']}]]"
        # Lexical lane (Top-100 coverage)
        if r["top100_pct"] >= 45:
            lex = "formulaic vocab"
        elif r["top100_pct"] >= 35:
            lex = "repetitive vocab"
        elif r["top100_pct"] >= 28:
            lex = "moderate vocab"
        else:
            lex = "varied vocab"
        # Thematic lane — high theme count at small corpus is meaningful;
        # at large corpus it means truly persistent core subjects.
        # Thresholds tuned empirically on observed channel mix.
        if r["themes_count"] >= 60:
            thematic = "very narrow themes"
        elif r["themes_count"] >= 30:
            thematic = "focused themes"
        elif r["themes_count"] >= 12:
            thematic = "moderate themes"
        else:
            thematic = "wide-ranging themes"
        variation_lines.append(
            f"| {chan_link} | {r['top100_pct']:.1f}% | {r['hapax_pct']:.1f}% | "
            f"{r['ttr']:.3f} | {r['themes_count']} | {lex}, {thematic} |"
        )
    variation_table = "\n".join(variation_lines)

    # Quick-card section — one paragraph per channel with sibling report links
    cards = []
    for r in rows:
        report_links = [f"[[{r['slug']}/profile\\|Voice Profile]]"]
        if r["has_compare"]:
            report_links.append(f"[[{r['slug']}/compare\\|Bucket Comparison]]")
        if r["has_themes"]:
            report_links.append(f"[[{r['slug']}/themes\\|LLM Themes]]")
        report_links.append(f"[[{r['slug']}/analysis\\|Full Analysis]]")
        cards.append(
            f"### [[{r['slug']}/profile\\|{r['channel']}]]\n\n"
            f"- **{r['transcripts']} transcripts** · {r['words']:,} words · "
            f"{r['unique']:,} unique vocab · TTR {r['ttr']:.3f}\n"
            f"- **Confidence:** relevance {r['relevance']:.2f} · accuracy {r['accuracy']:.2f}\n"
            f"- **Reports:** {' · '.join(report_links)}"
        )

    # Markdown footnote definitions — referenced by column headers above.
    # Both Obsidian and SilverBullet render these as tooltips/click-throughs.
    footnotes = (
        "[^tx]: Number of transcripts analyzed for this channel (after fetch).\n"
        "[^words]: Total words across all analyzed transcripts (raw count, "
        "including common words like 'the' and 'is').\n"
        "[^unique]: Total unique content words after the stopword filter "
        "(strips ~120 common English words like articles, prepositions, "
        "and pronouns to surface meaningful vocabulary).\n"
        "[^grade]: Flesch-Kincaid Grade Level — approximates the US school year "
        "needed to comfortably read the text. Grade 7 ≈ middle school, Grade 12 ≈ "
        "high-school senior, Grade 16+ ≈ college/graduate. Sentence length and "
        "syllable density drive the score; punctuation must be present for it to "
        "be meaningful (run `clean` for low-punctuation transcripts).\n"
        "[^ttr]: Type-Token Ratio — unique content tokens divided by total content "
        "tokens. Range 0–1. Higher = more lexical variety; lower = more repetition. "
        "**Caveat:** TTR is corpus-size sensitive — bigger corpora always show "
        "lower TTR mechanically, so direct cross-channel comparison is unreliable. "
        "Use Top-100 coverage for fairer comparison.\n"
        "[^top100]: Top-100 coverage — what percentage of all content speech is "
        "covered by the channel's 100 most-frequent content words. **Higher = "
        "more formulaic / repetitive** (a small core set dominates); **lower = "
        "broader vocabulary**. More robust than TTR for cross-channel comparison "
        "because it doesn't depend on corpus size.\n"
        "[^hapax]: Hapax percentage — share of the channel's unique vocabulary "
        "that appears exactly once across all transcripts. Hapax legomenon "
        "(Greek: 'said once') signals long-tail vocabulary diversity. High % at "
        "moderate corpus size = each video introduces fresh nouns / proper names "
        "(varied storytelling). Low % = a tight repeated vocabulary.\n"
        "[^themes]: Thematic concentration — count of content words that appear in "
        "**at least 50% of transcripts**. This catches what vocabulary metrics miss: "
        "a channel can have varied incidental words while hammering the same handful "
        "of subjects across every video. High count = same subjects keep coming "
        "back (e.g. politics channels returning to the same names/issues); low "
        "count = each video has its own focus. **Caveat:** the 50% threshold is "
        "easier to hit with small corpora (≤10 transcripts), so compare similar-size "
        "channels for the cleanest signal.\n"
        "[^conf]: Confidence scores — `relevance / accuracy`, both 0–1. "
        "Relevance combines recency (40%), topic diversity (30%), and format "
        "diversity (30%). Accuracy combines sample size (40%), consistency (35%), "
        "and transcript quality (25%). Higher is better; under 0.5 means the "
        "voice profile should be treated as preliminary.\n"
        "[^buckets]: Duration-tiered sub-reports. Each transcript is bucketed by "
        "video length: **shorts** (< 5 min), **mid** (5–36 min), **long** (≥ 36 "
        "min). Each bucket gets its own analysis/profile so format-specific voice "
        "patterns surface (e.g. shorts as fear-promo teasers vs long-form essays).\n"
    )

    body = (
        "# Channel Library\n\n"
        "Cross-channel index of all YouTube voice/personality analyses. "
        "Click any channel to dive in — every report is interlinked. "
        "Hover any column term[^tx] for a definition.\n\n"
        "## Channels\n\n"
        f"{table}\n\n"
        "## Variation Index\n\n"
        "Ranked by **Top-100 coverage**[^top100] — what % of total speech is covered "
        "by the channel's 100 most common content words. Higher = more repetitive / "
        "formulaic; lower = broader vocabulary. Hapax %[^hapax] shows the long tail "
        "(% of words used exactly once).\n\n"
        f"{variation_table}\n\n"
        "## Quick Profiles\n\n"
        + "\n\n".join(cards)
        + "\n\n---\n\n## Glossary\n\n"
        + footnotes
    )
    meta = {
        "generated": datetime.date.today().isoformat(),
        "channels_indexed": len(rows),
        "total_transcripts": sum(r["transcripts"] for r in rows),
    }
    out = cache_root / "INDEX.md"
    out.write_text(render_frontmatter(meta, body), encoding="utf-8")
    print(f"  Library index: {out}")


def cmd_report(args) -> None:
    """Standalone: regenerate INDEX.md cross-channel summary."""
    cache_root = get_cache_root(args.cache_dir)
    _write_global_report(cache_root)


def cmd_profile(args) -> None:
    cache_root = get_cache_root(args.cache_dir)
    slug = args.slug

    # Fail fast if no canonical analysis exists yet (the "all" bucket is required)
    if not analysis_path(slug, cache_root, "all").exists():
        print(
            f"Error: analysis.md not found for '{slug}'.\n"
            f"Run: yt-analyst analyze {slug}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Generate one profile per bucket where the analysis file exists.
    # Confidence scores are computed on the transcripts that actually fed each bucket.
    for bucket in ("all", *BUCKET_THRESHOLDS.keys()):
        if not analysis_path(slug, cache_root, bucket).exists():
            continue
        _profile_bucket(slug, cache_root, bucket)

    # Refresh the cross-channel library now that profile.md exists. INDEX.md
    # filters by `profile.md` presence, so a channel newly analyzed but not yet
    # profiled would otherwise be missing from the library until next report run.
    _write_global_report(cache_root)


def _profile_bucket(slug: str, cache_root: pathlib.Path, bucket: str) -> None:
    """Generate profile-{bucket}.md from the matching analysis-{bucket}.md."""
    an_path = analysis_path(slug, cache_root, bucket)
    an_meta, an_body = parse_frontmatter(an_path.read_text(encoding="utf-8"))

    # Load transcript metadata for confidence scoring — filtered to this bucket.
    # Prefer cleaned siblings (BERT punctuation restored) over raw originals.
    tx_dir = channel_cache_dir(slug, cache_root) / "transcripts"
    tx_files = sorted(tx_dir.glob("*.md")) if tx_dir.exists() else []
    tx_metas = []
    tx_top_word_sets = []
    for f in tx_files:
        if f.name.endswith(".cleaned.md"):
            continue
        cleaned = _cleaned_path(f)
        source = cleaned if cleaned.exists() else f
        m, body = parse_frontmatter(source.read_text(encoding="utf-8"))
        if not m:
            continue
        # Skip transcripts not in this bucket (except for 'all' which keeps everything)
        if bucket != "all":
            if _bucket_for(m.get("duration_seconds", 0), m.get("word_count", 0)) != bucket:
                continue
        tx_metas.append(m)
        if body.strip():
            tokens = tokenize(body)
            freq = collections.Counter(tokens)
            tx_top_word_sets.append({w for w, _ in freq.most_common(30)})

    n = len(tx_metas)
    today = datetime.date.today()

    # ── Relevance score ──
    ages_months = []
    for m in tx_metas:
        d = m.get("date", "")
        if d:
            try:
                tx_date = datetime.date.fromisoformat(str(d)[:10])
                ages_months.append(
                    (today.year - tx_date.year) * 12 + (today.month - tx_date.month)
                )
            except ValueError:
                pass

    if ages_months:
        median_age = sorted(ages_months)[len(ages_months) // 2]
        recency_score = 1.0 if median_age < 12 else 0.5 if median_age < 24 else 0.25 if median_age < 48 else 0.1
    else:
        median_age = None
        recency_score = 0.5

    if len(tx_top_word_sets) >= 2:
        distinct = sum(
            1 for s in tx_top_word_sets[1:]
            if len(s & tx_top_word_sets[0]) / max(1, len(s | tx_top_word_sets[0])) < 0.5
        )
        topic_diversity = min(1.0, distinct / max(1, n - 1))
    else:
        topic_diversity = 0.0

    formats_found = {infer_format(m.get("title", "")) for m in tx_metas} - {"unknown"}
    format_diversity = min(1.0, len(formats_found) / 4)

    relevance = (recency_score * 0.4) + (topic_diversity * 0.3) + (format_diversity * 0.3)

    # ── Accuracy score ──
    sample_score = min(0.95, math.log(n + 1) / math.log(51) * 0.95) if n > 0 else 0.0
    consistency_score = min(0.9, n / 15)
    quality_scores = [1.0 if m.get("transcript_type") == "manual" else 0.6 for m in tx_metas]
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.6

    accuracy = (sample_score * 0.4) + (consistency_score * 0.35) + (avg_quality * 0.25)

    notes = _build_confidence_notes(n, median_age, formats_found, avg_quality)

    # ── Extract key data from analysis body ──
    def _extract(pattern: str) -> str:
        m = re.search(pattern, an_body)
        return m.group(1).strip() if m else ""

    top_words_str = _extract(r"\*\*Top content words:\*\* (.+)")
    themes_str = _extract(r"\*\*Recurring themes[^:]*:\*\*\n(.+)")
    praise_str = _extract(r"\*\*Values — frequently praised:\*\* (.+)")
    criticism_str = _extract(r"\*\*Values — frequently criticized:\*\* (.+)")
    opening_str = _extract(r"\*\*Opening patterns detected:\*\* (.+)")
    closing_str = _extract(r"\*\*Closing patterns detected:\*\* (.+)")
    tone_str = _extract(r"\*\*Dominant mode:\*\* (.+)")
    fk_match = re.search(r"Flesch-Kincaid Grade ([\d.]+) \((.+?)\)", an_body)
    fk_str = f"Grade {fk_match.group(1)} ({fk_match.group(2)})" if fk_match else "unknown"

    subject = an_meta.get("subject", slug)
    channel = an_meta.get("channel", slug)
    date_range = an_meta.get("date_range", "unknown")

    rhetorical = _rhetorical_style(an_body)

    nav = _nav_links(slug, cache_root, f"profile{_bucket_suffix(bucket)}")
    title_suffix = f" ({bucket})" if bucket != "all" else ""

    body = f"""# Voice Profile: {subject}{title_suffix}

{nav}
## How They Sound

{subject} communicates at a {fk_str} reading level with a {tone_str or "varied"} audience address style.

Their vocabulary is characterized by frequent use of: {top_words_str[:200] or "see vocabulary fingerprint in analysis.md"}.

When building arguments they tend to {rhetorical}. Openings typically feature: {opening_str or "varied approaches"}. Closings typically feature: {closing_str or "varied approaches"}.

## Key Vocabulary

**Characteristic content words:** {top_words_str[:300] or "see analysis.md"}

**Recurring themes across transcripts:**
{themes_str or "Insufficient sample for cross-video theme detection."}

## Structural Habits

**Opens with:** {opening_str or "unclear — more transcripts needed"}
**Closes with:** {closing_str or "unclear — more transcripts needed"}
**Argument style:** {rhetorical}

## What They Care About

**Topics:** {themes_str or "unclear — more transcripts needed"}
**Praises:** {praise_str or "no strong praise patterns detected"}
**Criticizes:** {criticism_str or "no strong criticism patterns detected"}

## What They Avoid

Based on {n} transcript(s). Notable absences can only be stated with confidence at 10+ transcripts across diverse formats. Additional content needed for reliable omission detection.

## Sample System Prompt

The following draft system prompt is generated empirically from transcript analysis.
Confidence: relevance={relevance:.2f}, accuracy={accuracy:.2f}.

---

You are {subject}, communicating in your authentic voice based on empirical analysis of your transcripts.

**Your communication style:**
- Reading level: {fk_str}
- Audience address: {tone_str or "direct"}
- Characteristic vocabulary: {top_words_str[:150] or "natural, domain-specific terms"}

**Your recurring themes and interests:**
{themes_str or "Your authentic areas of focus based on your work."}

**What you value:**
- You frequently speak positively about: {praise_str or "your core subject matter"}
- You are critical of: {criticism_str or "ideas that contradict your principles"}

**Your structural habits:**
- You tend to open with: {opening_str or "direct engagement with your subject"}
- You tend to close with: {closing_str or "a call to reflection or action"}

Maintain this voice consistently. When uncertain about how {subject} would phrase something, default to the characteristic vocabulary and rhetorical patterns identified above.

---
"""

    pro_meta = {
        "subject": subject,
        "channel": channel,
        "bucket": bucket,
        "generated": today.isoformat(),
        "transcripts_used": n,
        "transcripts_available": n,
        "date_range": date_range,
        "median_age_months": median_age,
        "relevance": round(relevance, 2),
        "accuracy": round(accuracy, 2),
        "confidence_notes": notes,
    }

    out = profile_path(slug, cache_root, bucket)
    out.write_text(render_frontmatter(pro_meta, body), encoding="utf-8")
    print(f"  Written: {out.name}  relevance={relevance:.2f}  accuracy={accuracy:.2f}")


def _build_confidence_notes(n: int, median_age_months, formats_found: set, avg_quality: float) -> str:
    parts = []
    if n < 5:
        parts.append(f"Low sample size ({n} transcript{'s' if n != 1 else ''}).")
    elif n < 15:
        parts.append(f"Moderate sample size ({n} transcripts).")
    else:
        parts.append(f"Good sample size ({n} transcripts).")
    if median_age_months is not None:
        if median_age_months < 12:
            parts.append("Good recency (all within 12 months).")
        elif median_age_months < 24:
            parts.append(f"Moderate recency (median age: {median_age_months} months).")
        else:
            parts.append(f"Dated content (median age: {median_age_months} months).")
    if formats_found:
        parts.append(f"Format diversity: {', '.join(sorted(formats_found))}.")
    else:
        parts.append("Format diversity: unknown (could not infer from titles).")
    if avg_quality < 0.7:
        parts.append("Transcript quality: auto-generated captions.")
    else:
        parts.append("Transcript quality: manual or mixed.")
    parts.append("Accuracy improves significantly with 10+ transcripts across diverse formats.")
    return " ".join(parts)


def _rhetorical_style(an_body: str) -> str:
    q_match = re.search(r"(\d+) questions", an_body)
    l_match = re.search(r"(\d+) list items", an_body)
    q = int(q_match.group(1)) if q_match else 0
    lv = int(l_match.group(1)) if l_match else 0
    if q > lv * 2:
        return "ask questions to guide the audience toward conclusions"
    if lv > q * 2:
        return "use structured lists and enumeration to organize ideas"
    return "mix questions and declarative statements to build arguments"


def cmd_status(args) -> None:
    cache_root = get_cache_root(args.cache_dir)
    slug = args.slug
    meta, _ = read_index(slug, cache_root)
    if not meta:
        print(f"No index found for '{slug}'.", file=sys.stderr)
        sys.exit(1)

    videos = meta.get("videos", [])
    by_status: collections.Counter = collections.Counter(v["status"] for v in videos)

    print(f"\n  Channel      {meta.get('channel_name', slug)}")
    print(f"  Total        {len(videos)}")
    print()
    print(f"  {'Status':<12} {'Count':>6}")
    print(f"  {'-'*12} {'-'*6}")
    for status in ("fetched", "selected", "pending", "skipped", "failed"):
        if by_status.get(status, 0):
            print(f"  {status:<12} {by_status[status]:>6}")

    pro_path = profile_path(slug, cache_root)
    if pro_path.exists():
        pro_meta, _ = parse_frontmatter(pro_path.read_text(encoding="utf-8"))
        print(f"\n  Profile confidence")
        print(f"  {'Relevance':<12} {pro_meta.get('relevance', '—')}")
        print(f"  {'Accuracy':<12} {pro_meta.get('accuracy', '—')}")
        notes = pro_meta.get("confidence_notes", "")
        if notes:
            print(f"\n  {notes}")
    print()


# ─── LLM enrichment (opt-in, OpenAI-compatible chat completions) ──────────────

# Env vars — defaults target OpenAI directly but ANY OpenAI-compat endpoint works:
# Anthropic, Ollama, LM Studio, Sage.is, Groq, Together, Mistral, etc.
_LLM_ENV = {
    "url":   ("YT_ANALYST_LLM_URL",   "https://api.openai.com/v1"),
    "key":   ("YT_ANALYST_LLM_KEY",   None),     # required
    "model": ("YT_ANALYST_LLM_MODEL", "gpt-4o-mini"),
}

_ENRICH_PROMPT_TEMPLATE = """You are analyzing the voice and messaging of a YouTube channel from concatenated transcripts.

Channel: {channel}
Bucket: {bucket}
Transcripts analyzed: {n}
Total words: {word_count:,}

Read the transcripts below and produce a concise markdown report with EXACTLY these
sections (use ## headings):

## Core Themes
3-5 bullet points. The dominant subjects this channel returns to. One sentence per bullet.

## Primary Intent
One paragraph: is this channel primarily educational / persuasive / promotional /
news / opinion / entertainment? What is the creator trying to make the viewer DO
or BELIEVE?

## Narrative Arc
How do typical videos build? Problem→solution? Anecdote→thesis? Confrontation?
Investigative reveal? Refer to specific patterns you noticed.

## Stance / Worldview
What does the creator value? What do they oppose? What unstated assumptions are
they working from? Be specific, cite phrases.

## Audience
Who is this content for? Beginner / expert / niche-insider / lay audience?
What prior knowledge is assumed?
{cross_bucket_section}
Transcripts:
---
{combined}
"""


def _llm_complete(content: str, model: str, url: str, key: str) -> str:
    """OpenAI-compatible chat completion via requests. Returns assistant text."""
    resp = requests.post(
        f"{url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 2000,
            "temperature": 0.3,
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _truncate_combined(transcripts: list[dict], max_chars: int) -> str:
    """Concatenate transcripts with separators, truncating proportionally if over cap."""
    parts = []
    for t in transcripts:
        title = t["meta"].get("title", t["meta"].get("video_id", "?"))
        parts.append(f"### {title}\n\n{t['body'].strip()}\n")
    combined = "\n\n".join(parts)
    if len(combined) <= max_chars:
        return combined
    # Trim each transcript proportionally to fit (preserves all videos, just shorter excerpts)
    ratio = max_chars / len(combined)
    trimmed_parts = []
    for t in transcripts:
        title = t["meta"].get("title", t["meta"].get("video_id", "?"))
        body = t["body"].strip()
        keep = int(len(body) * ratio)
        trimmed_parts.append(f"### {title}\n\n{body[:keep]}\n")
    return "\n\n".join(trimmed_parts)


def cmd_enrich(args) -> None:
    """LLM-derived themes/intent/stance via OpenAI-compatible chat completions."""
    cache_root = get_cache_root(args.cache_dir)
    slug = args.slug
    bucket = args.bucket

    # Resolve config from env (with defaults)
    url = os.environ.get(_LLM_ENV["url"][0]) or _LLM_ENV["url"][1]
    key = os.environ.get(_LLM_ENV["key"][0])
    model = os.environ.get(_LLM_ENV["model"][0]) or _LLM_ENV["model"][1]
    if not key:
        print(
            f"Error: {_LLM_ENV['key'][0]} not set.\n"
            f"See docs/llm-enrich.md for configuration examples.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load transcripts in this bucket
    tx_dir = channel_cache_dir(slug, cache_root) / "transcripts"
    if not tx_dir.exists():
        print(f"No transcripts directory for '{slug}'.", file=sys.stderr)
        sys.exit(1)

    transcripts = []
    for f in sorted(tx_dir.glob("*.md")):
        if f.name.endswith(".cleaned.md"):
            continue
        cleaned = _cleaned_path(f)
        source = cleaned if cleaned.exists() else f
        meta, body = parse_frontmatter(source.read_text(encoding="utf-8"))
        if not body.strip():
            continue
        if bucket != "all":
            if _bucket_for(meta.get("duration_seconds", 0), meta.get("word_count", 0)) != bucket:
                continue
        transcripts.append({"meta": meta, "body": body})

    if not transcripts:
        print(f"No transcripts in bucket '{bucket}' for '{slug}'.", file=sys.stderr)
        sys.exit(1)

    combined = _truncate_combined(transcripts, args.max_chars)
    word_count = sum(len(t["body"].split()) for t in transcripts)
    channel = transcripts[0]["meta"].get("channel", slug)

    cross_bucket_section = (
        "\n## Cross-bucket Note\nHow does this bucket's voice differ from the channel's overall voice?\n"
        if bucket != "all" else ""
    )
    prompt = _ENRICH_PROMPT_TEMPLATE.format(
        channel=channel, bucket=bucket, n=len(transcripts),
        word_count=word_count, cross_bucket_section=cross_bucket_section,
        combined=combined,
    )

    # ~4 chars/token rough estimate, transparent so user can decide
    est_tokens = len(prompt) // 4
    print(f"Enriching '{slug}' [{bucket}]:")
    print(f"  endpoint: {url}")
    print(f"  model:    {model}")
    print(f"  input:    ~{est_tokens:,} tokens ({len(prompt):,} chars, {len(transcripts)} transcripts)")
    if not args.yes:
        confirm = input("Proceed? [y/N] ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return

    print("Calling LLM...")
    result = _llm_complete(prompt, model, url, key)

    enrich_meta = {
        "subject": channel,
        "channel": channel,
        "bucket": bucket,
        "generated": datetime.date.today().isoformat(),
        "transcripts_used": len(transcripts),
        "words_sent": word_count,
        "llm_endpoint": url,
        "llm_model": model,
    }
    out = channel_cache_dir(slug, cache_root) / f"themes{_bucket_suffix(bucket)}.md"
    nav = _nav_links(slug, cache_root, f"themes{_bucket_suffix(bucket)}")
    title_suffix = f" ({bucket})" if bucket != "all" else ""
    body_with_nav = f"# LLM Themes: {channel}{title_suffix}\n\n{nav}\n{result}"
    out.write_text(render_frontmatter(enrich_meta, body_with_nav), encoding="utf-8")
    print(f"Themes written: {out}")


def cmd_run(args) -> None:
    """One-shot pipeline: discover → sample → fetch → (clean) → analyze → profile.

    Detects whether `target` is a URL/handle (runs discover first) or an
    existing slug (skips discover). Reuses the per-step cmd_* functions by
    constructing minimal argparse Namespaces. Stops at the first failed step
    via sys.exit propagating up — the user can resume from the failed step.
    """
    target = args.target
    is_url = target.startswith(("http", "@")) or "youtube.com" in target

    # Forward shared flags into per-step namespaces
    shared = {
        "cache_dir": args.cache_dir,
        "mcp_url": args.mcp_url,
        "mcp_token": args.mcp_token,
    }

    total_steps = 5 + (1 if is_url else 0) + (1 if args.clean else 0)
    step = 0

    if is_url:
        step += 1
        print(f"\n━━━ [{step}/{total_steps}] Discover ━━━")
        slug = cmd_discover(argparse.Namespace(**shared, target=target))
    else:
        slug = target
        print(f"Skipping discover (target '{slug}' looks like an existing slug)")

    step += 1
    print(f"\n━━━ [{step}/{total_steps}] Sample ━━━")
    cmd_sample(argparse.Namespace(**shared, slug=slug, max=args.max, strategy=args.strategy))
    # sample auto-forks for non-blend strategies → track the active slug
    active_slug = f"{slug}-{args.strategy}" if args.strategy != "blend" else slug

    step += 1
    print(f"\n━━━ [{step}/{total_steps}] Fetch ━━━")
    cmd_fetch(argparse.Namespace(
        **shared, slug=active_slug, max=args.max,
        delay=args.delay, session_pause=args.session_pause,
        business_hours=False, force_retry=False,
    ))

    if args.clean:
        step += 1
        print(f"\n━━━ [{step}/{total_steps}] Clean (BERT) ━━━")
        cmd_clean(argparse.Namespace(**shared, slug=active_slug, force=False))

    step += 1
    print(f"\n━━━ [{step}/{total_steps}] Analyze ━━━")
    cmd_analyze(argparse.Namespace(**shared, slug=active_slug))

    step += 1
    print(f"\n━━━ [{step}/{total_steps}] Profile ━━━")
    cmd_profile(argparse.Namespace(**shared, slug=active_slug))

    cache_root = get_cache_root(args.cache_dir)
    print(f"\n✓ Pipeline complete for '{active_slug}'")
    print(f"  Profile: {profile_path(active_slug, cache_root)}")
    print(f"  Library: {cache_root / 'INDEX.md'}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="yt-analyst",
        description="YouTube channel transcript archiver and voice profiler.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Shared flags inherited by all subcommands
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--cache-dir", metavar="PATH", help="Override cache directory (default: scripts/yt-cache/)")
    shared.add_argument("--mcp-url", metavar="URL", help="MCP server URL")
    shared.add_argument("--mcp-token", metavar="TOKEN", help="MCP server auth token")

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "run", parents=[shared],
        help="One-shot full pipeline: discover → sample → fetch → (clean) → analyze → profile",
    )
    p.add_argument("target", help="Channel/playlist URL, @handle, or existing slug")
    p.add_argument(
        "--strategy", choices=["blend", "latest", "top", "random"], default="blend",
        help="Sampling strategy (default: blend)",
    )
    p.add_argument("--max", type=int, default=20, metavar="N", help="Max videos to sample/fetch (default: 20)")
    p.add_argument("--delay", default="15-45", metavar="MIN-MAX", help="Fetch jitter (default: 15-45)")
    p.add_argument(
        "--session-pause", default="3-5,120-180", metavar="N-M,S-T",
        help="Pause every N-M requests for S-T seconds (default: 3-5,120-180)",
    )
    p.add_argument("--clean", action="store_true", help="Run BERT punctuation cleanup before analyze")

    p = sub.add_parser("discover", parents=[shared], help="Enumerate videos from a channel")
    p.add_argument("target", help="Channel URL, ID, or @handle")

    p = sub.add_parser("sample", parents=[shared], help="Select videos for fetching")
    p.add_argument("slug", help="Channel slug")
    p.add_argument("--max", type=int, default=50, metavar="N", help="Max videos to select (default: 50)")
    p.add_argument(
        "--strategy",
        choices=["blend", "latest", "top", "random"],
        default="blend",
        help="Selection strategy: blend (default=15 latest+top fill+random), latest, top, random",
    )

    p = sub.add_parser("fetch", parents=[shared], help="Fetch transcripts (humanized rate limiting)")
    p.add_argument("slug", help="Channel slug")
    p.add_argument("--delay", metavar="MIN-MAX", default="3-8", help="Jitter delay in seconds (default: 3-8)")
    p.add_argument("--max", type=int, default=25, metavar="N", help="Max fetches per session (default: 25)")
    p.add_argument("--session-pause", metavar="N-M,S-T", default="5-8,45-120", help="Pause every N-M requests for S-T seconds")
    p.add_argument("--business-hours", action="store_true", help="Only fetch 8am-10pm Atlantic/Azores")
    p.add_argument("--force-retry", action="store_true", help="Retry failed transcripts regardless of cooldown")

    p = sub.add_parser("fetch-one", parents=[shared], help="Fetch a single transcript (no rate limiting)")
    p.add_argument("video_id", help="YouTube video ID")

    p = sub.add_parser(
        "clean", parents=[shared],
        help="Restore punctuation in low-density transcripts via BERT (requires [punct] extra)",
    )
    p.add_argument("slug", help="Channel slug")
    p.add_argument("--force", action="store_true", help="Re-clean even if cleaned siblings exist")

    p = sub.add_parser("analyze", parents=[shared], help="Run analysis on cached transcripts (offline)")
    p.add_argument("slug", help="Channel slug")

    p = sub.add_parser("profile", parents=[shared], help="Generate voice profile from analysis")
    p.add_argument("slug", help="Channel slug")

    p = sub.add_parser("status", parents=[shared], help="Show fetch progress and confidence scores")
    p.add_argument("slug", help="Channel slug")

    p = sub.add_parser("compare", parents=[shared], help="Cross-bucket metrics comparison (auto-runs at end of analyze)")
    p.add_argument("slug", help="Channel slug")

    sub.add_parser("report", parents=[shared], help="Regenerate INDEX.md cross-channel library (auto-runs at end of analyze)")

    p = sub.add_parser(
        "enrich", parents=[shared],
        help="LLM-derived themes/intent/stance (opt-in, OpenAI-compatible API)",
    )
    p.add_argument("slug", help="Channel slug")
    p.add_argument(
        "--bucket",
        choices=["all", *BUCKET_THRESHOLDS.keys()],
        default="all",
        help="Which bucket to enrich (default: all)",
    )
    p.add_argument("--yes", action="store_true", help="Skip cost confirmation prompt")
    p.add_argument(
        "--max-chars", type=int, default=80_000, metavar="N",
        help="Cap on combined transcript chars sent to LLM (default: 80,000)",
    )

    args = parser.parse_args()
    {
        "run": cmd_run,
        "discover": cmd_discover,
        "sample": cmd_sample,
        "fetch": cmd_fetch,
        "fetch-one": cmd_fetch_one,
        "clean": cmd_clean,
        "analyze": cmd_analyze,
        "profile": cmd_profile,
        "status": cmd_status,
        "compare": cmd_compare,
        "report": cmd_report,
        "enrich": cmd_enrich,
    }[args.command](args)


if __name__ == "__main__":
    main()
