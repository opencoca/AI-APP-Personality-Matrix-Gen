"""yt-analyst: YouTube channel transcript archiver and voice profiler."""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import math
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


def analysis_path(slug: str, cache_root: pathlib.Path) -> pathlib.Path:
    return channel_cache_dir(slug, cache_root) / "analysis.md"


def profile_path(slug: str, cache_root: pathlib.Path) -> pathlib.Path:
    return channel_cache_dir(slug, cache_root) / "profile.md"


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


def _index_body(meta: dict) -> str:
    videos = meta.get("videos", [])
    fetched = sum(1 for v in videos if v["status"] == "fetched")
    selected = sum(1 for v in videos if v["status"] == "selected")
    total = meta.get("total_videos", len(videos))
    name = meta.get("channel_name", "Channel")
    return (
        f"# {name} — Channel Index\n\n"
        f"Discovered {total} videos. {fetched} fetched, {selected} selected.\n"
    )


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


def cmd_sample(args) -> None:
    cache_root = get_cache_root(args.cache_dir)
    slug = args.slug
    meta, _ = read_index(slug, cache_root)
    if not meta:
        print(f"No index found for '{slug}'. Run discover first.", file=sys.stderr)
        sys.exit(1)

    videos = meta.get("videos", [])
    max_videos = args.max
    eligible = [v for v in videos if v["status"] in ("pending", "failed")]

    if len(videos) <= 50:
        for v in eligible:
            v["status"] = "selected"
        selected_count = len(eligible)
    else:
        selected_ids: set[str] = set()

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
    write_index(slug, meta, _index_body(meta), cache_root)
    print(f"Selected {selected_count} videos for fetching.")


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
            write_index(slug, meta, _index_body(meta), cache_root)
            sys.exit(1)

        if status == 429:
            print("Rate limited (429). Waiting 120s then retrying...")
            time.sleep(120)
            status, content = _post_transcript(mcp_url, mcp_token, video_id)
            if status == 429:
                print("Still rate limited. Stopping session.", file=sys.stderr)
                write_index(slug, meta, _index_body(meta), cache_root)
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
                write_index(slug, meta, _index_body(meta), cache_root)
                continue

        if status == 200:
            # MCP returns 200 + error string for gated/unavailable videos
            if content.lstrip().startswith("Error:") or "Could not retrieve a transcript" in content:
                print(f"           ✗ unavailable (members-only or no captions)")
                video["status"] = "failed"
                video["error"] = "unavailable"
                video["failed_date"] = now_iso()
                write_index(slug, meta, _index_body(meta), cache_root)
                continue

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

        write_index(slug, meta, _index_body(meta), cache_root)
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

    cache_root = get_cache_root(args.cache_dir)
    out_dir = cache_root / "_single"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{video_id}.md"
    word_ct = count_words(content)
    tx_meta = {"video_id": video_id, "fetched": now_iso(), "word_count": word_ct}
    out_path.write_text(render_frontmatter(tx_meta, content), encoding="utf-8")
    print(f"Saved: {out_path} ({word_ct:,} words)")


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

    transcripts = []
    for tx_file in tx_files:
        meta, body = parse_frontmatter(tx_file.read_text(encoding="utf-8"))
        if body.strip():
            transcripts.append({"meta": meta, "body": body})

    if not transcripts:
        print("No transcript content found (all files empty?).", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing {len(transcripts)} transcript(s)...")

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

    vocab_section = f"""## Vocabulary Fingerprint

Analyzed {len(transcripts)} transcript(s) totalling {total_words:,} words across {len(sentences):,} sentences.

**Reading level:** Flesch-Kincaid Grade {fk_grade:.1f} ({_fk_label(fk_grade)})
**Average sentence length:** {avg_sentence_len:.1f} words
**Vocabulary richness (type-token ratio):** {ttr:.3f}

**Top content words:** {top_30_str}

**Filler words / verbal tics:**
{filler_lines}
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

    body = f"{vocab_section}\n{structure_section}\n{personality_section}\n{tone_section}"
    an_meta = {
        "subject": channel,
        "channel": channel,
        "generated": datetime.date.today().isoformat(),
        "transcripts_analyzed": len(transcripts),
        "date_range": date_range,
        "total_words_analyzed": total_words,
    }
    out = analysis_path(slug, cache_root)
    out.write_text(render_frontmatter(an_meta, body), encoding="utf-8")
    print(f"Analysis written: {out}")


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


def _compute_date_range(transcripts: list[dict]) -> str:
    dates = [str(t["meta"].get("date", ""))[:7] for t in transcripts if t["meta"].get("date")]
    if not dates:
        return "unknown"
    return f"{min(dates)} to {max(dates)}"


def cmd_profile(args) -> None:
    cache_root = get_cache_root(args.cache_dir)
    slug = args.slug
    an_path = analysis_path(slug, cache_root)

    # Fail fast with a clear message
    if not an_path.exists():
        print(
            f"Error: analysis.md not found for '{slug}'.\n"
            f"Run: yt-analyst analyze {slug}",
            file=sys.stderr,
        )
        sys.exit(1)

    an_meta, an_body = parse_frontmatter(an_path.read_text(encoding="utf-8"))

    # Load transcript metadata for confidence scoring
    tx_dir = channel_cache_dir(slug, cache_root) / "transcripts"
    tx_files = sorted(tx_dir.glob("*.md")) if tx_dir.exists() else []
    tx_metas = []
    tx_top_word_sets = []
    for f in tx_files:
        m, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        if m:
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

    body = f"""# Voice Profile: {subject}

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
        "generated": today.isoformat(),
        "transcripts_used": n,
        "transcripts_available": n,
        "date_range": date_range,
        "median_age_months": median_age,
        "relevance": round(relevance, 2),
        "accuracy": round(accuracy, 2),
        "confidence_notes": notes,
    }

    out = profile_path(slug, cache_root)
    out.write_text(render_frontmatter(pro_meta, body), encoding="utf-8")
    print(f"Profile written: {out}")
    print(f"Confidence  relevance={relevance:.2f}  accuracy={accuracy:.2f}")


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

    p = sub.add_parser("discover", parents=[shared], help="Enumerate videos from a channel")
    p.add_argument("target", help="Channel URL, ID, or @handle")

    p = sub.add_parser("sample", parents=[shared], help="Select videos for fetching")
    p.add_argument("slug", help="Channel slug")
    p.add_argument("--max", type=int, default=50, metavar="N", help="Max videos to select (default: 50)")

    p = sub.add_parser("fetch", parents=[shared], help="Fetch transcripts (humanized rate limiting)")
    p.add_argument("slug", help="Channel slug")
    p.add_argument("--delay", metavar="MIN-MAX", default="3-8", help="Jitter delay in seconds (default: 3-8)")
    p.add_argument("--max", type=int, default=25, metavar="N", help="Max fetches per session (default: 25)")
    p.add_argument("--session-pause", metavar="N-M,S-T", default="5-8,45-120", help="Pause every N-M requests for S-T seconds")
    p.add_argument("--business-hours", action="store_true", help="Only fetch 8am-10pm Atlantic/Azores")
    p.add_argument("--force-retry", action="store_true", help="Retry failed transcripts regardless of cooldown")

    p = sub.add_parser("fetch-one", parents=[shared], help="Fetch a single transcript (no rate limiting)")
    p.add_argument("video_id", help="YouTube video ID")

    p = sub.add_parser("analyze", parents=[shared], help="Run analysis on cached transcripts (offline)")
    p.add_argument("slug", help="Channel slug")

    p = sub.add_parser("profile", parents=[shared], help="Generate voice profile from analysis")
    p.add_argument("slug", help="Channel slug")

    p = sub.add_parser("status", parents=[shared], help="Show fetch progress and confidence scores")
    p.add_argument("slug", help="Channel slug")

    args = parser.parse_args()
    {
        "discover": cmd_discover,
        "sample": cmd_sample,
        "fetch": cmd_fetch,
        "fetch-one": cmd_fetch_one,
        "analyze": cmd_analyze,
        "profile": cmd_profile,
        "status": cmd_status,
    }[args.command](args)


if __name__ == "__main__":
    main()
