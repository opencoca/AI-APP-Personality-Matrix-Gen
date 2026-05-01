#!/usr/bin/env python3
"""
Refresh YouTube cookies in the local MCP transcript server.

Reads fresh cookies from the Zen browser (Firefox-based), recreates the
youtube-transcribe-server-mcpo Docker container with them, waits for the
new Cloudflare tunnel URL, and patches .env automatically.

Usage:
    python scripts/refresh-yt-cookies.py [--dry-run] [--container NAME]

Requires: sqlite3 (stdlib), docker CLI on PATH, Zen browser running on macOS.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

# ── Cookie name → YT_COOKIE_* env var name (must match youtube_transcribe_server.py) ──
COOKIE_ENV_MAP: dict[str, str] = {
    "__Secure-1PAPISID":           "YT_COOKIE___Secure_1PAPISID",
    "__Secure-1PSID":              "YT_COOKIE___Secure_1PSID",
    "__Secure-1PSIDCC":            "YT_COOKIE___Secure_1PSIDCC",
    "__Secure-1PSIDTS":            "YT_COOKIE___Secure_1PSIDTS",
    "__Secure-3PAPISID":           "YT_COOKIE___Secure_3PAPISID",
    "__Secure-3PSID":              "YT_COOKIE___Secure_3PSID",
    "__Secure-3PSIDCC":            "YT_COOKIE___Secure_3PSIDCC",
    "__Secure-3PSIDTS":            "YT_COOKIE___Secure_3PSIDTS",
    "__Secure-BUCKET":             "YT_COOKIE___Secure_BUCKET",
    "__Secure-ROLLOUT_TOKEN":      "YT_COOKIE___Secure_ROLLOUT_TOKEN",
    "__Secure-YNID":               "YT_COOKIE___Secure_YNID",
    "GPS":                         "YT_COOKIE_GPS",
    "LOGIN_INFO":                  "YT_COOKIE_LOGIN_INFO",
    "PREF":                        "YT_COOKIE_PREF",
    "SOCS":                        "YT_COOKIE_SOCS",
    "VISITOR_INFO1_LIVE":          "YT_COOKIE_VISITOR_INFO1_LIVE",
    "VISITOR_PRIVACY_METADATA":    "YT_COOKIE_VISITOR_PRIVACY_METADATA",
    "YSC":                         "YT_COOKIE_YSC",
}

ZEN_PROFILES_DIR = pathlib.Path.home() / "Library/Application Support/zen/Profiles"
CONTAINER_NAME = "youtube-transcribe-server-mcpo"
IMAGE_NAME = "youtube-transcribe-server:latest"
ENV_FILE = pathlib.Path(__file__).parent.parent / ".env"

# The command that starts the server with the public Cloudflare tunnel.
# Override via --server-cmd if the image changes.
DEFAULT_SERVER_CMD = [
    "python", "youtube_transcribe_server.py",
    "--public-mcpo", "--mcpo-port", "8000",
]


# ── Zen browser helpers ─────────────────────────────────────────────────────

def find_zen_profile() -> pathlib.Path:
    """Return the Zen profile with the most YouTube cookies."""
    if not ZEN_PROFILES_DIR.exists():
        sys.exit("Zen browser profiles not found — is Zen installed?")
    best = (0, None)
    for profile in ZEN_PROFILES_DIR.iterdir():
        db = profile / "cookies.sqlite"
        if not db.exists():
            continue
        tmp = pathlib.Path(tempfile.mktemp(suffix=".sqlite"))
        shutil.copy2(db, tmp)
        try:
            with sqlite3.connect(tmp) as con:
                count = con.execute(
                    "SELECT COUNT(*) FROM moz_cookies WHERE host LIKE '%youtube%'"
                ).fetchone()[0]
            if count > best[0]:
                best = (count, db)
        except Exception:
            pass
        finally:
            tmp.unlink(missing_ok=True)
    if best[1] is None:
        sys.exit("No Zen profile with YouTube cookies found.")
    print(f"  Using profile: {best[1].parent.name} ({best[0]} YT cookies)")
    return best[1]


def extract_cookies(db_path: pathlib.Path) -> dict[str, str]:
    """Return {cookie_name: freshest_value} for all COOKIE_ENV_MAP keys."""
    tmp = pathlib.Path(tempfile.mktemp(suffix=".sqlite"))
    shutil.copy2(db_path, tmp)
    cookies: dict[str, str] = {}
    try:
        with sqlite3.connect(tmp) as con:
            names_placeholder = ",".join("?" * len(COOKIE_ENV_MAP))
            rows = con.execute(
                f"""
                SELECT name, value
                FROM moz_cookies
                WHERE host LIKE '%youtube.com%'
                  AND name IN ({names_placeholder})
                ORDER BY lastAccessed DESC
                """,
                list(COOKIE_ENV_MAP.keys()),
            ).fetchall()
            # First row per name = most recently accessed
            for name, value in rows:
                if name not in cookies:
                    cookies[name] = value
    finally:
        tmp.unlink(missing_ok=True)
    return cookies


# ── Docker helpers ──────────────────────────────────────────────────────────

def docker(*args: str, check: bool = True, capture: bool = True) -> str:
    r = subprocess.run(["docker", *args],
                       capture_output=capture, text=True)
    if check and r.returncode != 0:
        sys.exit(f"docker {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout.strip()


def get_container_env(name: str) -> dict[str, str]:
    """Return {key: value} env vars from a running container."""
    import json
    raw = docker("inspect", name, "--format", "{{json .Config.Env}}", check=False)
    if not raw:
        return {}
    env_list: list[str] = json.loads(raw)
    result = {}
    for item in env_list:
        if "=" in item:
            k, _, v = item.partition("=")
            result[k] = v
    return result


def get_container_hostconfig(name: str) -> dict:
    """Return HostConfig dict from a running or stopped container."""
    import json
    raw = docker("inspect", name, "--format", "{{json .HostConfig}}", check=False)
    return json.loads(raw) if raw else {}


def get_container_cmd(name: str) -> list[str]:
    """Return Config.Cmd from a running or stopped container, or [] if not found."""
    import json
    raw = docker("inspect", name, "--format", "{{json .Config.Cmd}}", check=False)
    if not raw:
        return []
    try:
        return json.loads(raw) or []
    except Exception:
        return []


def container_exists(name: str) -> bool:
    """True if container exists (running or stopped)."""
    out = docker("ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}", check=False)
    return name in out


def container_running(name: str) -> bool:
    out = docker("ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}", check=False)
    return name in out


def wait_for_tunnel_url(name: str, timeout: int = 90) -> str | None:
    """Poll container logs (stdout + stderr) until a trycloudflare.com URL appears."""
    deadline = time.time() + timeout
    seen_lines = 0
    while time.time() < deadline:
        r = subprocess.run(["docker", "logs", name],
                           capture_output=True, text=True)
        # docker logs mixes output across stdout and stderr
        combined = r.stdout + r.stderr
        lines = combined.splitlines()
        for line in lines[seen_lines:]:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m:
                return m.group(0)
        seen_lines = len(lines)
        time.sleep(3)
    return None


def update_env_file(key: str, value: str) -> None:
    """Upsert KEY=value in .env, preserving other entries."""
    if not ENV_FILE.exists():
        ENV_FILE.write_text(f"{key}={value}\n", encoding="utf-8")
        return
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    replaced = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{key}={value}\n")
    ENV_FILE.write_text("".join(new_lines), encoding="utf-8")


# ── Main ────────────────────────────────────────────────────────────────────

def hot_swap_cookies(cookies: dict[str, str]) -> bool:
    """Try the in-process hot-swap endpoint. Returns True on success.

    Uses the `set_youtube_cookies` MCP tool exposed by mcpo. Avoids the full
    container restart (and Cloudflare tunnel URL churn) when the running image
    is new enough to expose this endpoint. Falls back to recreate if not.
    """
    import json as _json

    # Resolve MCP URL + token from .env (same source yt-analyst uses)
    url, token = "http://localhost:8000", ""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("YT_ANALYST_MCP_URL="):
                url = line.split("=", 1)[1].strip()
            elif line.startswith("YT_ANALYST_MCP_TOKEN="):
                token = line.split("=", 1)[1].strip()
    if not token:
        print("  Hot-swap skipped: YT_ANALYST_MCP_TOKEN not in .env")
        return False

    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(
            f"{url.rstrip('/')}/set_youtube_cookies",
            data=_json.dumps({"cookies_json": _json.dumps(cookies)}).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            if resp.status == 200:
                print(f"  ✅ Hot-swap response: {body[:120]}")
                return True
            print(f"  Hot-swap failed (HTTP {resp.status}): {body[:200]}")
            return False
    except urllib.error.HTTPError as e:
        # 404 = old image without the endpoint → fall back to recreate
        if e.code == 404:
            print(f"  Hot-swap endpoint not present (HTTP 404) — falling back to container recreate")
        else:
            print(f"  Hot-swap HTTP error: {e.code} {e.reason} — falling back to recreate")
        return False
    except Exception as e:
        print(f"  Hot-swap error: {e} — falling back to recreate")
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the docker run command without executing it")
    ap.add_argument("--container", default=CONTAINER_NAME,
                    help=f"Container name (default: {CONTAINER_NAME})")
    ap.add_argument("--no-env-update", action="store_true",
                    help="Don't patch .env with the new tunnel URL (recreate path only)")
    ap.add_argument("--server-cmd", nargs=argparse.REMAINDER, default=None,
                    help="Override server startup CMD (default: auto-detected or built-in)")
    ap.add_argument("--force-recreate", action="store_true",
                    help="Skip the hot-swap endpoint and force a full container recreate")
    args = ap.parse_args()

    print("🍪  Extracting fresh YouTube cookies from Zen browser...")
    db = find_zen_profile()
    cookies = extract_cookies(db)
    if not cookies:
        sys.exit("No YouTube cookies found in Zen profile.")
    print(f"  Found {len(cookies)} cookies: {', '.join(sorted(cookies))}")

    # Try the hot-swap endpoint first (no restart, no URL churn). Falls back
    # to full container recreate if the endpoint isn't present (old image)
    # or the user passed --force-recreate.
    if not args.force_recreate and not args.dry_run:
        print("\n♻️   Attempting hot-swap via /set_youtube_cookies endpoint...")
        if hot_swap_cookies(cookies):
            print("\n✅  Cookies hot-swapped — no container restart, no URL change.")
            return
        print("    Falling back to full container recreate.\n")

    # Build cookie env vars
    cookie_env: dict[str, str] = {}
    for name, value in cookies.items():
        env_key = COOKIE_ENV_MAP[name]
        cookie_env[env_key] = value

    # Read existing container config BEFORE stopping it
    preserved_keys = {"MCPO_API_KEY", "SECRET_KEY", "BASIC_AUTH_USERNAME", "BASIC_AUTH_PASSWORD"}
    old_env = get_container_env(args.container) if container_exists(args.container) else {}
    static_env = {k: v for k, v in old_env.items() if k in preserved_keys}

    # Fallback: read MCPO_API_KEY from .env (stored as YT_ANALYST_MCP_TOKEN)
    if "MCPO_API_KEY" not in static_env and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("YT_ANALYST_MCP_TOKEN="):
                static_env["MCPO_API_KEY"] = line.split("=", 1)[1].strip()
                print("  MCPO_API_KEY: read from .env (YT_ANALYST_MCP_TOKEN)")
                break

    if not static_env:
        print("  ⚠️  Could not read existing container env — MCPO_API_KEY etc. will be missing.")

    hc = get_container_hostconfig(args.container) if container_exists(args.container) else {}
    network = hc.get("NetworkMode", "youtube_transcript_server_default")
    restart = hc.get("RestartPolicy", {}).get("Name", "unless-stopped")

    # Server CMD: CLI override > existing container CMD > project default
    if args.server_cmd:
        server_cmd = args.server_cmd
    else:
        detected = get_container_cmd(args.container)
        if detected and "--public-mcpo" in detected:
            server_cmd = detected
            print(f"  CMD from container: {' '.join(server_cmd)}")
        else:
            server_cmd = DEFAULT_SERVER_CMD
            print(f"  CMD (default): {' '.join(server_cmd)}")

    # Derive internal port from --mcpo-port in CMD
    try:
        port = server_cmd[server_cmd.index("--mcpo-port") + 1]
    except (ValueError, IndexError):
        port = "8000"

    all_env = {**static_env, **cookie_env}

    cmd = [
        "docker", "run", "-d",
        "--name", args.container,
        "--restart", restart,
        "--network", network,
        "-p", f"8000:{port}",
    ]
    for k, v in all_env.items():
        cmd += ["-e", f"{k}={v}"]
    cmd += [IMAGE_NAME, *server_cmd]

    if args.dry_run:
        print("\n🔍  Dry run — docker command:")
        # Mask secrets in output
        safe = []
        skip_next = False
        for token in cmd:
            if skip_next:
                key = token.split("=")[0] if "=" in token else token
                if any(s in key for s in ("PSID", "TOKEN", "KEY", "SECRET", "LOGIN", "PSIDCC")):
                    safe.append(f"{key}=<redacted>")
                else:
                    safe.append(token)
                skip_next = False
            elif token == "-e":
                safe.append(token)
                skip_next = True
            else:
                safe.append(token)
        print("  " + " \\\n    ".join(safe))
        return

    # Stop and remove existing container
    if container_running(args.container):
        print(f"\n🛑  Stopping {args.container}...")
        docker("stop", args.container)
        docker("rm", args.container)
    else:
        docker("rm", args.container, check=False)  # remove if stopped

    # Start fresh
    print(f"🚀  Starting {args.container} with fresh cookies...")
    docker(*cmd[1:])  # docker() already prepends "docker"

    # Wait for tunnel URL
    print("🌐  Waiting for Cloudflare tunnel URL", end="", flush=True)
    url = wait_for_tunnel_url(args.container, timeout=60)
    print()

    if url:
        print(f"  Tunnel URL: {url}")
        if not args.no_env_update:
            update_env_file("YT_ANALYST_MCP_URL", url)
            print(f"  ✅ Updated {ENV_FILE} with new URL")
    else:
        print("  ⚠️  Tunnel URL not detected within 60s — check: docker logs " + args.container)

    print("\n✅  Done. Test with:")
    print(f"     curl -s http://localhost:8000/")


if __name__ == "__main__":
    main()
