# Switching LLM provider / model / base URL

All LLM calls go through one place: `graph/llm.py` (`get_chat_model()` +
`generate_json()`). No node in `graph/nodes.py` knows or cares which provider is
active — switching provider is a `.env` edit, not a code change.

## Switch provider

Set `LLM_PROVIDER` in `.env` to one of:

```ini
LLM_PROVIDER=gemini      # default
LLM_PROVIDER=openai
LLM_PROVIDER=anthropic
```

Each provider has its own key/model/base_url variables, all defined in
`.env.example` and read in `config/settings.py`:

| Provider  | API key             | Model             | Base URL override    |
|-----------|---------------------|-------------------|----------------------|
| gemini    | `GEMINI_API_KEY`    | `GEMINI_MODEL`    | `GEMINI_BASE_URL`    |
| openai    | `OPENAI_API_KEY`    | `OPENAI_MODEL`    | `OPENAI_BASE_URL`    |
| anthropic | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL` | `ANTHROPIC_BASE_URL` |

Only the active provider's key must be set; the other two can stay empty. All
three `langchain-*` packages are installed, so switching needs no reinstall.

## Switch model

Change the `*_MODEL` variable for whichever provider is active:

```ini
GEMINI_MODEL=gemini-2.5-pro
OPENAI_MODEL=gpt-5.1
ANTHROPIC_MODEL=claude-opus-5
```

The model name is not validated at startup — an unknown one surfaces as a normal
API error on the first call, which fails the run with the provider's message.

## Switch base URL

Leave `*_BASE_URL` unset to use the provider's default endpoint. Set it to point
at an Azure OpenAI deployment or any OpenAI-compatible proxy, a region-specific
Gemini endpoint, or an Anthropic-compatible proxy.

This is also how to use a provider with no block of its own: for anything that
speaks the OpenAI protocol (DeepSeek, Together, vLLM, LM Studio, Ollama's
compatibility endpoint), set `LLM_PROVIDER=openai`, `OPENAI_API_KEY` to its key,
`OPENAI_MODEL` to its model name, and `OPENAI_BASE_URL` to its endpoint.

## Failure behavior

There is **no fallback content**. If the model cannot produce valid output, the
run fails and the reviewer is told — nothing is generated locally to fill the
gap, because a plausible-looking placeholder is far more dangerous in marketing
copy than a visible failure.

Two distinct retry layers:

1. **Transport** — connection resets, 429s and 5xx are retried by the provider
   client itself, up to `LLM_MAX_RETRIES` (default 3) with backoff. `graph/llm.py`
   does not re-attempt these; re-asking a dead endpoint just delays the failure.
2. **Shape** — a response that doesn't parse as JSON, or parses but violates the
   node's schema, is retried up to `LLM_JSON_ATTEMPTS` (default 3). The retry
   appends the model's own bad output plus the specific error
   (`"beats" must contain exactly 5 entries…`) and asks it to correct that.
   Most misses self-correct on the second attempt.

Recovered-after-retry runs still succeed, and record a warning in `_meta.json`
noting how many attempts a node needed — a node that consistently needs two is a
signal the prompt or the brand rules want attention.

Before either layer runs, `check_configuration()` rejects a missing or
placeholder-looking key by name, so a mis-set key fails at startup rather than
eight nodes into a run.

## Adding a new provider

1. Add its API key / model / base_url settings to `config/settings.py` (follow
   the existing three blocks) and to `.env.example`.
2. Add a `ProviderConfig` entry in `_provider_configs()` and a builder function
   in `_PROVIDER_BUILDERS` in `graph/llm.py`, using the appropriate
   `langchain-*` chat model class.
3. Add the `langchain-*` package to `requirements.txt`.
4. Add the provider name to the `_choice(...)` tuple for `LLM_PROVIDER`.

Nothing outside those two files changes — `generate_json()`, every node, and the
Streamlit UI are provider-agnostic already.
