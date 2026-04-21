# TODOS

Work captured but deferred. Each item has enough context to pick up in any future session.

---

## tools-v2: Additional Tools

**What:** Add `url_reader`, `weather`, and `image_generation` tools to the agent. Update the system prompt to reflect the new capabilities.

**Why:** Widens the "wow" surface. URL reader + image generation are the two features most likely to impress a recruiter or casual user.

**Pros:** All three tools have simple APIs (Jina for URL reading, OpenWeatherMap for weather, OpenAI DALL-E for images).

**Cons:** Each tool adds an optional API key dependency. Image generation is expensive per-call.

**Context:**
- Tools live in `app/tools/`. Follow the `base.py` `BaseTool` interface.
- URL reader: `GET https://r.jina.ai/{url}` — returns clean markdown from any URL. No API key needed.
- Weather: OpenWeatherMap API (free tier). Tool takes `city` argument.
- Image gen: `openai.images.generate(model="dall-e-3", prompt=..., size="1024x1024")`. Return the URL.
- Update `AGENT_SYSTEM_PROMPT` in `agent.py` to mention the new tools.
- Add `JINA_API_KEY` (optional) and `OPENWEATHERMAP_API_KEY` to config/env.
- Frontend: `ToolCallDisplay` already handles `image_generation` icon (🎨). For image results, render an `<img>` tag if the result looks like a URL.

---

## tools-v2: Image Rendering in Chat

**What:** When a tool result is an image URL (from image_generation), render `<img>` in the message bubble instead of raw text.

**Why:** Showing a thumbnail is dramatically better UX than showing a URL.

**Context:** In `ChatPage.tsx`, the `tool_call_result` handler appends the result as a string. Add a `tryParseImageUrl(result: string)` helper — if the string starts with `https://` and ends with a known image extension (or matches DALL-E's CDN URL pattern), render an `<img>` tag.

---

## Stretch: Streaming memory extraction status

**What:** Show a subtle indicator in the UI when memory extraction is running in the background.

**Why:** The background arq job runs 60s after every completed conversation, but the user has no visibility. A small "Saving memories…" indicator would help users trust the memory feature.

**Context:** The `done` SSE event fires when the conversation commits. Memory extraction is scheduled then. The frontend could show a brief indicator after `done` that auto-dismisses after a few seconds.
