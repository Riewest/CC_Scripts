# REQ-020 AI provider abstraction and adapters
Status: todo | Milestone: M4 | Depends: REQ-002

## Goal
A provider-neutral interface so any LLM backend can be plugged in, with initial adapters for GitHub Models, OpenAI-compatible endpoints and Anthropic.

## Design notes
- Interface `LLMProvider`: `async stream(messages, tools, model, params) -> AsyncIterator[Chunk]` where chunks are text deltas, tool-call deltas, usage, and finish reason; `list_models()`; capability flags (tool calling, streaming, vision, max context).
- Internal neutral message and tool schema (JSON Schema tools); adapters translate. Registry loaded by name so new providers are one file plus registration.
- Adapters: GitHub Models (`https://models.github.ai/inference`, token-based, OpenAI-style chat completions), OpenAI-compatible (configurable base URL: Ollama, LM Studio, OpenRouter, OpenAI), Anthropic Messages API.
- Provider configs stored per user or team in `ai_providers`; API keys encrypted at rest, never returned by the API after save.
- Retries with backoff on 429/5xx, request timeouts, token usage recorded.
- Note for docs: GitHub Copilot has no public general chat API; GitHub Models is the supported GitHub route.
- Verify current endpoint and model names against provider docs at implementation time.

## Acceptance criteria
- [ ] Interface and neutral schema documented in `docs/ai-providers.md`, including how to add a provider.
- [ ] All three adapters stream text and tool calls through the neutral interface.
- [ ] Keys encrypted at rest and write-only via API.
- [ ] Connection test endpoint per provider config.
- [ ] A deterministic `MockProvider` for tests.

## Test plan
pytest with mocked HTTP (respx/httpx mock) for each adapter: streaming, tool calls, error and retry; encryption round trip.

## Files touched
`server/aicontrol/ai/providers/**`, `docs/ai-providers.md`, tests.
