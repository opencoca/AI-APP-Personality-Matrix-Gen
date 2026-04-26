# MCP Server — YouTube Cookie Refresh

The local YouTube transcript MCP server authenticates with YouTube using browser cookies.
Cookies expire or get rotated by YouTube, causing `IP blocked` or `unavailable` errors even
for public videos. This guide explains how to refresh them.

## How it works

The MCP server (`youtube-transcribe-server-mcpo`) reads cookies from Docker env vars named
`YT_COOKIE_<NAME>` on startup. It builds a Netscape cookie file from these and passes it
to `yt-dlp` / `youtube-transcript-api` on each request.

Because the container also runs a Cloudflare tunnel (`cloudflared`), restarting it generates a
**new public URL**. The refresh script handles this automatically.

## Quick refresh

```bash
python scripts/refresh-yt-cookies.py
```

What it does:
1. Reads the freshest YouTube cookies from your Zen browser profile
2. Stops and recreates the Docker container with fresh cookies
3. Waits for the new Cloudflare tunnel URL to appear in container logs
4. Patches `YT_ANALYST_MCP_URL` in your project `.env`

**Prerequisites:**
- Zen browser open and logged into YouTube
- Docker Desktop running
- `docker` on PATH

## When to refresh

| Symptom | Cause | Fix |
|---|---|---|
| All fetches → `YouTube is blocking requests from your IP` | Cookies expired | Run refresh script |
| Some videos `unavailable` but others work | Members-only / no captions | Normal — not a cookie issue |
| `Connection error` | Container down | `docker start youtube-transcribe-server-mcpo` |
| `YT_ANALYST_MCP_URL` not set | `.env` missing | Run refresh script or set manually |

## Options

```
python scripts/refresh-yt-cookies.py [--dry-run] [--no-env-update] [--container NAME]

  --dry-run         Print the docker run command without executing (secrets redacted)
  --no-env-update   Recreate container but don't touch .env
  --container NAME  Override container name (default: youtube-transcribe-server-mcpo)
```

## After refresh

Your `.env` will contain the new URL:
```
YT_ANALYST_MCP_URL=https://<new-slug>.trycloudflare.com
```

Test it works:
```bash
uv run yt-analyst fetch-one <video_id>
```

## Cookie source

The script reads from your Zen browser's `cookies.sqlite` — the profile with the most
YouTube cookies is used automatically. It copies the file before reading (safe to run while
Zen is open).

Cookies extracted:
- `__Secure-1PSID`, `__Secure-3PSID`, `__Secure-1PSIDTS`, `__Secure-3PSIDTS`
- `__Secure-1PSIDCC`, `__Secure-3PSIDCC`, `__Secure-1PAPISID`, `__Secure-3PAPISID`
- `__Secure-BUCKET`, `__Secure-ROLLOUT_TOKEN`, `__Secure-YNID`
- `LOGIN_INFO`, `VISITOR_INFO1_LIVE`, `VISITOR_PRIVACY_METADATA`
- `PREF`, `SOCS`, `GPS`, `YSC`

## Future: hot-swap without URL change

The current architecture requires a container restart (and thus a new tunnel URL) to update
cookies. A planned improvement to the MCP server would add a cookie file volume mount:

```yaml
# docker-compose.yml (planned)
volumes:
  - ./cookies.txt:/app/cookies.txt:ro
```

With this in place, `refresh-yt-cookies.py` could write a Netscape-format `cookies.txt` and
the server would pick it up on the next request — no restart, URL stays stable. Track this
as a TODO in the MCP server repo.

## Manual refresh (without the script)

If the script fails, you can rebuild the container manually:

1. Extract cookies using `yt-dlp` from your browser:
   ```bash
   yt-dlp --cookies-from-browser zen --cookies /tmp/yt-cookies.txt --skip-download \
     "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
   ```

2. Parse the cookie values from `/tmp/yt-cookies.txt` and set them as `YT_COOKIE_*` env vars
   when running the container.

3. After restart, check logs for the new tunnel URL:
   ```bash
   docker logs youtube-transcribe-server-mcpo 2>&1 | grep trycloudflare
   ```

4. Update `.env`:
   ```bash
   echo "YT_ANALYST_MCP_URL=https://<new-url>" >> .env
   ```
