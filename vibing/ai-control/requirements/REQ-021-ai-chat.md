# REQ-021 Per-computer AI chat
Status: todo | Milestone: M4 | Depends: REQ-020, REQ-008

## Goal
A chat panel on each computer where the user talks to the AI, which writes and runs Lua.

## Design notes
- Sessions per computer and user, persisted (`ai_sessions`, `ai_messages`), streaming responses over the UI websocket.
- Model/provider selector per session; token/cost usage shown.
- Code blocks in replies show Run, Edit, Save to library buttons (always available regardless of autonomy; autonomy of auto-run is REQ-023).
- Context passed to the AI: computer kind, telemetry, peripherals, recent runs (budgeted); system prompt from REQ-026.
- Conversation controls: stop generation, regenerate, clear, rename.

## Acceptance criteria
- [ ] Streaming chat works with the MockProvider and at least one real adapter.
- [ ] Sessions persist and reload.
- [ ] Code blocks can be run manually with result fed back into the conversation.
- [ ] Stop generation cancels the upstream request.
- [ ] Respects computer permissions (viewer cannot chat-execute).

## Test plan
pytest: session persistence, streaming protocol, cancellation, permission checks.

## Files touched
`server/aicontrol/ai/chat/**`, `web/src/components/AiChat.tsx`.
