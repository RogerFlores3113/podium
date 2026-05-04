# Coding Conventions

**Analysis Date:** 2026-05-03

## Naming Patterns

**Python Files:**
- `snake_case` for all module and file names: `guest_auth.py`, `tool_call_display.py`
- Router files named after the resource they own: `chat.py`, `keys.py`, `guest.py`, `memories.py`
- Service files named for the domain they encapsulate: `agent.py`, `llm.py`, `encryption.py`

**Python Functions:**
- Public functions: `snake_case` — `create_guest_user`, `verify_guest_token`, `resolve_api_key`
- Private helpers (module-internal): single underscore prefix — `_guest_secret()`, `_to_responses_input()`, `_mock_db()`
- FastAPI dependency functions: descriptive verb phrases — `get_current_user_id`, `get_or_create_user`, `get_db`

**Python Variables:**
- `snake_case` throughout — `user_id`, `clerk_id`, `api_key_record`, `token_count`
- Module-level constants: `UPPER_SNAKE_CASE` — `RESPONSES_API_MODELS`, `GUEST_ALLOWED_TOOLS`, `AGENT_SYSTEM_PROMPT`, `AVAILABLE_MODELS`
- Private module-level singletons: underscore prefix — `_jwks_client`, `_ALGORITHM`, `_SECRET`

**Python Types/Classes:**
- `PascalCase` for Pydantic models and SQLAlchemy ORM classes — `ChatRequest`, `ChatResponse`, `ToolContext`, `DocumentResponse`
- Pydantic `Settings` class (singular): `app/config.py`
- Module-level singleton instance named lowercase: `settings = Settings()`

**TypeScript Files:**
- PascalCase for React components: `ChatPage.tsx`, `ToolCallDisplay.tsx`, `LandingPage.tsx`
- camelCase for hooks: `useAuthFetch.ts`
- camelCase for utility modules: `time.ts`, `image.ts`

**TypeScript Functions/Exports:**
- React components: PascalCase named exports — `export function ToolCallDisplay(...)`
- Hooks: camelCase named exports starting with `use` — `export function useAuthFetch()`
- Utilities: camelCase named exports — `export function formatRelativeTime(...)`, `export function tryParseImageUrl(...)`
- Module-internal helpers: camelCase without export — `async function getAuthToken(...)`

**TypeScript Interfaces:**
- PascalCase, no `I` prefix — `interface Message`, `interface ToolCall`, `interface ConversationItem`
- Exported when consumed across files: `export interface ToolCall` in `ToolCallDisplay.tsx`
- Local interfaces not exported when used only within a single component

## Code Style

**Python Formatting:**
- No formatter config file found (no `.prettierrc` or `black` config); `noqa` comments indicate flake8/ruff is the linter
- Line length not explicitly configured; practical lines stay under 120 chars
- Trailing commas used in multi-line collections and function signatures

**TypeScript Formatting:**
- TypeScript strict mode enabled (`"strict": true` in `frontend/tsconfig.json`)
- No `.eslintrc` found; Next.js built-in eslint applies
- `"use client"` directive at top of every client component file

**Python Linting:**
- `noqa: E712` used for SQLAlchemy boolean comparisons (`== True`)
- `noqa: E402, F401` used for tool side-effect imports in `app/tools/__init__.py`

## Import Organization

**Python Order (observed pattern):**
1. Standard library (`uuid`, `json`, `logging`, `datetime`, `collections.abc`)
2. Third-party packages (`fastapi`, `sqlalchemy`, `jwt`, `pydantic`, `litellm`)
3. Local app imports (`from app.config import ...`, `from app.models import ...`, `from app.services.xxx import ...`)

**Python Path Style:**
- Always absolute imports from `app.*` — never relative imports
- Example: `from app.services.guest_auth import create_guest_user` (not `from ..services.guest_auth`)

**TypeScript Order (observed pattern):**
1. React and framework imports (`"react"`, `"next/*"`, `"@clerk/nextjs"`)
2. Third-party libraries (`react-markdown`, `remark-gfm`)
3. Internal imports using `@/` alias (`@/app/hooks/useAuthFetch`, `@/app/utils/time`)

**TypeScript Path Aliases:**
- `@/` maps to the `frontend/` directory root (configured in `tsconfig.json` and `vitest.config.ts`)
- All internal imports use `@/app/...` — no relative `../` imports across directories

## Error Handling

**Python — FastAPI routes:**
- Raise `HTTPException` with specific status codes; never return error payloads with 200 status
- 401 for auth failures, 402 for BYOK missing, 404 for not found, 503 for server misconfiguration
- Structured error detail objects for machine-parseable errors:
  ```python
  raise HTTPException(
      status_code=402,
      detail={"error": "byok_required", "message": "..."},
  )
  ```
- Simple string details for simple errors:
  ```python
  raise HTTPException(status_code=404, detail="Conversation not found")
  ```

**Python — Services/helpers:**
- Service functions raise domain exceptions (`jwt.ExpiredSignatureError`, `jwt.InvalidSignatureError`) rather than `HTTPException`
- Callers (routers or auth middleware) translate exceptions to HTTP responses
- `app/errors.py` provides a global `global_exception_handler` for unhandled exceptions → 500

**Python — Agent loop:**
- Tool failures yield `{"type": "tool_call_error", ...}` events — the agent loop never raises from tool errors
- LLM call failures yield `{"type": "error", "detail": str(e)}` and return early
- `json.JSONDecodeError` caught explicitly for malformed tool arguments, yielded as tool errors

**TypeScript — Hooks:**
- `try/catch` blocks around `localStorage`/`sessionStorage` access to handle private browsing/SSR:
  ```typescript
  try {
    const guestToken = sessionStorage.getItem("podium_guest_token");
  } catch {
    // sessionStorage unavailable — fall through
  }
  ```
- No explicit error states in utility functions — they return `null` to signal failure

## Logging

**Framework:** Python `logging` module (standard library)

**Setup Pattern:**
- Each module declares its own logger at module scope:
  ```python
  logger = logging.getLogger(__name__)
  ```
- No centralized logging configuration found in app code (configured at runtime by uvicorn)

**Log Levels in Practice:**
- `logger.info(...)` — routine operations: "Created new user: ...", "Agent iteration N/M"
- `logger.warning(...)` — recoverable issues: "Agent hit max iterations", "Invalid token"
- `logger.error(..., exc_info=True)` — failures: LLM call failures, tool failures

## Comments

**When to Comment:**
- Docstrings on all public functions and classes — explains *what* and *why*, includes usage example for FastAPI dependencies
- Inline comments for non-obvious decisions — algorithm steps, protocol quirks, auth edge cases
- Comments on class attributes when semantics are not obvious from the name:
  ```python
  key_hint: Mapped[str]  # Last 4 chars: "...xY7z"
  ```

**Docstring Style:**
- No formal NumPy/Google docstring format; free-form prose paragraphs
- Docstrings include behavioral contracts and "why" rationale, not just parameter lists
- Example from `app/auth.py`:
  ```python
  def verify_clerk_token(token: str) -> dict:
      """
      Verify a Clerk RS256 JWT and return its claims.

      Raises jwt.InvalidTokenError on failure (not HTTPException — callers decide).
      """
  ```

**Dead Code Policy:**
- No commented-out code observed in any source file
- No TODO/FIXME comments found in `app/` or `frontend/app/` (only `noqa` directives)

## Function Design

**Size:** Functions are small and single-purpose. The largest functions are the agent loop generators in `app/services/agent.py` (unavoidably stateful streaming loops).

**Parameters:**
- FastAPI route functions use `Depends()` for all dependencies — no manual dependency wiring in route bodies
- Helper functions take explicit typed parameters — no `**kwargs` or dynamic dispatch

**Return Values:**
- Service functions return domain objects or tuples: `tuple[User, str]` from `create_guest_user`
- Utility functions use `| None` return types for "not found" rather than raising:
  ```python
  def tryParseImageUrl(result: string): string | null
  ```
- Agent loop uses `AsyncGenerator[dict, None]` — yields typed event dicts

**Async Pattern:**
- All DB operations are `async/await` via `AsyncSession`
- All LLM calls are `async/await` via `acompletion` (litellm) or `AsyncOpenAI`
- Sync functions are pure computation only — `verify_guest_token`, `resolve_api_key`, `model_supports_tools`

## Module Design

**Python Exports:**
- No explicit `__all__` declarations; public API defined by what's imported in routers/main
- `app/tools/__init__.py` uses side-effect imports to populate the tool registry:
  ```python
  from app.tools import web_search  # noqa: E402, F401
  ```

**TypeScript Exports:**
- Named exports only — no default exports except Next.js page components
- Next.js page components use `export default function PageName()` (framework requirement)
- All other components, hooks, and utilities use named exports

**Pydantic Schema Pattern:**
- Request schemas: `XxxRequest` suffix — `ChatRequest`, `ApiKeyCreate`, `MemoryCreate`, `MemoryUpdate`
- Response schemas: `XxxResponse` suffix — `ChatResponse`, `DocumentResponse`, `ConversationResponse`
- ORM mode enabled via `model_config = {"from_attributes": True}` on response schemas only

---

*Convention analysis: 2026-05-03*
