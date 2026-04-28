# LLM Enrichment

The `enrich` command sends a channel's transcripts to an OpenAI-compatible chat
completions endpoint and writes a `themes.md` (or `themes-{bucket}.md`) file
with LLM-derived themes, intent, narrative arc, stance, and audience.

The endpoint is configured via env vars — any OpenAI-compatible API works.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `YT_ANALYST_LLM_URL` | `https://api.openai.com/v1` | Base URL of the chat completions endpoint |
| `YT_ANALYST_LLM_KEY` | (none — required) | Bearer token sent as `Authorization: Bearer ...` |
| `YT_ANALYST_LLM_MODEL` | `gpt-4o-mini` | Model name passed in the request body |

## Examples

### OpenAI

```bash
export YT_ANALYST_LLM_KEY=sk-...
export YT_ANALYST_LLM_MODEL=gpt-4o-mini
uv run yt-analyst enrich ai-in-context
```

### Anthropic (OpenAI-compatibility endpoint)

```bash
export YT_ANALYST_LLM_URL=https://api.anthropic.com/v1
export YT_ANALYST_LLM_KEY=sk-ant-...
export YT_ANALYST_LLM_MODEL=claude-haiku-4-5-20251001
uv run yt-analyst enrich ai-in-context --bucket long
```

### Ollama (local, free)

```bash
# brew install ollama && ollama pull llama3.2
export YT_ANALYST_LLM_URL=http://localhost:11434/v1
export YT_ANALYST_LLM_KEY=ollama  # any non-empty string
export YT_ANALYST_LLM_MODEL=llama3.2
uv run yt-analyst enrich casey-top --yes
```

### LM Studio (local, GUI)

LM Studio exposes an OpenAI-compatible server. Apple Intelligence-eligible
machines can run quantized models locally with Metal acceleration.

```bash
export YT_ANALYST_LLM_URL=http://localhost:1234/v1
export YT_ANALYST_LLM_KEY=lmstudio
export YT_ANALYST_LLM_MODEL=<model-id-shown-in-LM-Studio>
uv run yt-analyst enrich vanneistat-top
```

### Sage.is gateway

```bash
export YT_ANALYST_LLM_URL=https://api.sage.is/v1
export YT_ANALYST_LLM_KEY=$SAGE_API_KEY
export YT_ANALYST_LLM_MODEL=sage-default
uv run yt-analyst enrich tech-nomics-top
```

## Usage

```
yt-analyst enrich <slug> [--bucket all|shorts|mid|long] [--yes] [--max-chars N]
```

- `--bucket`: which bucket to enrich (default: `all`)
- `--yes`: skip the cost confirmation prompt
- `--max-chars`: cap on combined transcript characters sent to the LLM (default: 80,000 ≈ 20k tokens)

The command will:
1. Load all transcripts for the bucket
2. Concatenate them with section headers, truncating proportionally if over the cap
3. Show endpoint, model, and estimated input tokens
4. Prompt for confirmation (unless `--yes`)
5. Make a single chat completion call
6. Write the response as `themes.md` (or `themes-{bucket}.md`)

## Output

`themes.md` has YAML frontmatter with provenance:

```yaml
---
subject: AI_In_Context
channel: AI_In_Context
bucket: all
generated: '2026-04-27'
transcripts_used: 14
words_sent: 21847
llm_endpoint: https://api.openai.com/v1
llm_model: gpt-4o-mini
---
```

The body contains six sections: Core Themes, Primary Intent, Narrative Arc,
Stance / Worldview, Audience, and (when bucket ≠ `all`) Cross-bucket Note.

## Privacy

**Transcripts are sent to whatever endpoint you configure.** If you use a hosted
provider (OpenAI, Anthropic, Sage.is), the transcripts traverse the public
internet to that provider. Use Ollama or LM Studio for fully-local processing.

## Cost

The command shows an estimated input token count before calling. As a rough
guide for an 80k-char run (~20k input tokens):
- `gpt-4o-mini`: ~$0.003
- `claude-haiku-4-5`: ~$0.005
- Local (Ollama/LM Studio): free

Output is capped at 2,000 tokens. Re-runs are not cached — each invocation
makes a fresh API call.
