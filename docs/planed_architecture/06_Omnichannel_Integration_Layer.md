# 6. Omnichannel Integration Layer

Vera must meet users where they are. The Omnichannel Integration Layer is designed to connect Vera's core intelligence to various communication channels, ensuring a consistent and high-quality user experience everywhere. The key principle is to **decouple the agent's brain from the specific channel's protocol**.

The Vera AI Core only ever processes text. This layer acts as a universal adapter, translating voice into text, text into a standard format, and Vera's text responses back into the native format of each channel.

## Session Model
- Sessions reset completely when the user closes the app or leaves a channel. Personalization is preserved via Semantic/Episodic memory, not long-lived session state.
- Each live conversation is identified by a `thread_id` (conversation_id). The frontend includes this on all message posts.

## Streaming Runtime Events
- Channel adapters expose a WebSocket or Server-Sent Events (SSE) endpoint that streams LangGraph Real-time Events (routing, tool calls, token deltas) to the client while a request is processed.
- The UI renders a lightweight “what Vera is doing” view and streams partial tokens for fast feedback.
- We multiplex additional application events on the same stream so the UI can show placeholders and status updates without blocking token streams.

### Event types (shared across onboarding and general chat)
- `conversation.started` { thread_id }
- `token.delta` { text, sources }
- `step.update` { node, status }
- `memory.candidate` { temp_id, type_hint, tags_hint }
- `memory.created` { memory_id, summary, type, tags, created_at }
- `memory.dropped` { temp_id, reason }
- `conversation.summary` { text }
- `onboarding.status` { thread_id, status: queued|processing|done|failed }
- `conversation.ended` { thread_id }

## Core Components

-   **Amazon API Gateway:** Serves as the single, secure front door for all incoming traffic from all channels. It handles authentication, routing, and throttling.
-   **AWS Lambda (Channel Adapters):** A collection of small, specialized Lambda functions. Each function is an "adapter" responsible for handling the specific protocol of one channel (e.g., a `TwilioAdapter`, a `MobileAppAdapter`).

## Channel 1: Mobile App (Chat; Voice in V2)

- V1 supports chat. Voice is planned for V2.

### Chat Flow

1.  User types a message in the app.
2.  The app opens a streaming connection (WebSocket/SSE) to receive LangGraph events and token deltas.
3.  The app sends a JSON payload to **API Gateway**.
4.  API Gateway routes to the `MobileAppAdapter` Lambda, which forwards a standardized request to the **Agent Core Engine** and relays events downstream.
5.  The agent processes the request and returns a streamed response, which is sent back to the app.

### Onboarding API (separate graph)
- `POST /initialize_onboarding` → returns `{ thread_id, welcome, sse_url }` and starts streaming events.
- `POST /onboarding/message` (with `thread_id`) → streams SSE events (`token.delta`, `memory.candidate/created`, etc.).
- `POST /onboarding/done/{thread_id}` → responds `202 Accepted`; enqueues a background finalization job that creates `user_context`, initial semantic memories (if any), and sets `ready_for_orchestrator`.
- Server-enforced close conditions: message cap (e.g., 30) or TTL (e.g., 24h) auto-closes and triggers finalization.

### General Chat API (post-onboarding)
- `POST /initialize` → returns `{ thread_id, welcome_from_user_context, last_conversation_summary, sse_url }`.
- `POST /message` (with `thread_id`) → streams normal SSE events.
  - On each message, the Orchestrator fetches and injects the compact `user_context` header (see Data & Persistence).

### Notification‑initiated conversations (Registered Orchestrator)

Goal: When a user taps a proactive notification, start a conversation already contextualized by the notification’s linked prompt, without pre‑creating abandoned threads.

Flow
1. Notification creation (server): Heuristics Engine prepares a payload with minimal identifiers only:
   - `nudge_id`, `linked_prompt_id`, `title`, `preview`, `expires_at`
   - `nudge_token` (short‑lived, user‑bound, signed; no raw prompt text on device)
2. User taps notification (client): App calls `POST /initialize` with `{ nudge_id, nudge_token }`.
3. Initialize (server):
   - Validate `nudge_token` (signature, expiry, user binding) and `nudge_id`→`linked_prompt_id` mapping.
   - Resolve `linked_prompt_id` to a `notification_task_context` (prompt snippet) server‑side.
   - Create a new `thread_id` lazily (do not pre‑create). If the same `nudge_id` is reused within TTL, return the same `thread_id` (idempotent).
   - Respond `{ thread_id, welcome_from_user_context, sse_url }` and start SSE.
4. SSE event sequence (server → client):
   - `conversation.started` { thread_id }
   - `notification.context` { nudge_id, title, preview }  // explicit about why the user is here
   - Stream reply tokens (`token.delta`) for a welcome composed as: `[system core] + [brand_voice] + [tier] + [notification_task_context] + [user_context header]`.
   - Other events as usual: `step.update`, `memory.candidate/created`, `conversation.summary`.

Rules & guardrails
- No abandoned state: threads are created only on `/initialize` after tap.
- Expiry & single‑use: If `nudge_token` is expired or already consumed and outside TTL, ignore `notification_task_context` and return normal `/initialize` behavior with a neutral welcome (include `onboarding.status` or reason if helpful).
- Idempotency: multiple taps within TTL return the same `thread_id`; record click/open events once.
- Security: `nudge_token` is short‑lived, signed, and bound to `user_id`; the server never trusts client‑supplied prompt text.
- Messaging channels (e.g., WhatsApp): treat an inbound reply that includes `nudge_id` the same as above; attach `notification_task_context` for the first agent turn in that thread.

## Channel 2: Messaging (WhatsApp, iMessage)

-   **Technology:** **Twilio API.**
-   **Mechanism:** Webhooks for inbound; a streaming endpoint for optional live events when the client supports it.

### Inbound Flow

1.  A user sends a message to Vera's WhatsApp number.
2.  Twilio receives the message and immediately makes an HTTPS POST request (a webhook) to a specific endpoint on our **API Gateway**.
3.  This endpoint is configured to trigger the `TwilioAdapter` Lambda.
4.  The Lambda parses the Twilio-formatted request, extracts the user identifier and message text, and invokes the **Agent Core Engine**.

### Outbound Flow

1.  The Agent Core Engine returns its text response to the `TwilioAdapter` Lambda.
2.  The Lambda uses the Twilio SDK to make an API call back to Twilio, telling it to send the response text to the correct user.

## Future Channels (V2)
- **Voice via Amazon Connect:** Real-time STT/TTS and call flows for voice assistance.
- To add any new channel (e.g., Slack):
  1. Create a new endpoint on API Gateway.
  2. Write a new adapter Lambda that understands the new channel's protocol.
  3. Point the API Gateway endpoint to the new Lambda.

No changes are required in the Agent Core Engine itself, demonstrating the power of a decoupled integration layer.
