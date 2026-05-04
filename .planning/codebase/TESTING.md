# Testing Patterns

**Analysis Date:** 2026-05-03

## Test Framework

### Backend

**Runner:** pytest 8.x (declared in `pyproject.toml` `[project.optional-dependencies] dev`)

**Async support:** `pytest-asyncio` 0.24+ with `asyncio_mode = "auto"` — no manual `@pytest.mark.asyncio` decorator needed (but the decorator is still written explicitly on async tests in this codebase)

**Config:** `pyproject.toml` `[tool.pytest.ini_options]`
```toml
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Install dev deps:** `uv sync --extra dev`

**Run Commands:**
```bash
uv run pytest tests/ -v          # Run all tests with verbose output
uv run pytest tests/test_guest_auth.py -v   # Run a single file
uv run pytest tests/ -k "guest"  # Run tests matching a keyword
```

### Frontend

**Runner:** Vitest 4.x (`frontend/package.json` devDependencies)

**Config:** `frontend/vitest.config.ts`
- Environment: `jsdom` (DOM simulation)
- Globals: enabled (no need to import `describe`/`it`/`expect` per file)
- Setup file: `frontend/vitest.setup.ts` (imports `@testing-library/react/pure`)
- Path alias: `@/` → `frontend/` root

**Assertion library:** Vitest built-in (`expect`) + `@testing-library/react` matchers

**Run Commands:**
```bash
cd frontend
npm test              # Run all tests once (vitest run)
npm run test:watch    # Watch mode (vitest)
```

## Test File Organization

### Backend

**Location:** Separate `tests/` directory at project root — not co-located with source files.

**Naming:** `test_<subject>.py` — one file per major concern:
- `tests/test_guest_auth.py` — guest JWT creation and verification
- `tests/test_byok_and_guest_guards.py` — BYOK enforcement and tool filtering
- `tests/test_agent.py` — agent message transformation helpers
- `tests/test_config.py` — model capability flags and provider detection
- `tests/test_schemas.py` — Pydantic schema validation

**Structure:**
```
tests/
├── __init__.py
├── test_agent.py
├── test_byok_and_guest_guards.py
├── test_config.py
├── test_guest_auth.py
└── test_schemas.py
```

### Frontend

**Location:** Separate `frontend/__tests__/` directory — not co-located with source.

**Naming:** `<Subject>.test.ts` or `<Subject>.test.tsx` matching the module under test:
- `frontend/__tests__/ToolCallDisplay.test.tsx` → tests `app/components/ToolCallDisplay.tsx`
- `frontend/__tests__/useAuthFetch.test.ts` → tests `app/hooks/useAuthFetch.ts`
- `frontend/__tests__/formatRelativeTime.test.ts` → tests `app/utils/time.ts`
- `frontend/__tests__/tryParseImageUrl.test.ts` → tests `app/utils/image.ts`

**Structure:**
```
frontend/
├── __tests__/
│   ├── ToolCallDisplay.test.tsx
│   ├── formatRelativeTime.test.ts
│   ├── tryParseImageUrl.test.ts
│   └── useAuthFetch.test.ts
├── vitest.config.ts
└── vitest.setup.ts
```

## Test Structure

### Backend Test Pattern

Tests are organized with section comment banners grouping related tests, and helper factories at module scope:

```python
"""Tests for guest authentication: token creation, verification, and expiry."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.guest_auth import create_guest_user, verify_guest_token

_SECRET = "test-secret-for-unit-tests-exactly-32b"

# Module-level autouse fixture to patch settings
@pytest.fixture(autouse=True)
def patch_secret(monkeypatch):
    monkeypatch.setattr("app.services.guest_auth.settings.guest_jwt_secret", _SECRET)

# --- Group heading ---

def test_verify_guest_token_accepts_valid_token():
    ...

def test_verify_guest_token_rejects_expired_token():
    ...
```

**Test name format:** `test_<subject>_<action_or_condition>` — verb phrase describing behavior:
- `test_guest_always_uses_system_key`
- `test_authenticated_user_without_byok_raises_402`
- `test_create_guest_user_token_expires_in_24h`

### Frontend Test Pattern

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MyComponent } from "@/app/components/MyComponent";

describe("MyComponent", () => {
  // Shared fixture
  const base = { id: "tc-1", name: "web_search", ... };

  it("renders the tool name", () => {
    render(<MyComponent prop={base} />);
    expect(screen.getByText("web_search")).toBeTruthy();
  });
});
```

**Test name format:** Sentence describing behavior — `"renders 'done' status"`, `"expands to show arguments and result on click"`, `"falls back to Clerk token when guest token is expired"`.

## Mocking

### Backend: `unittest.mock`

**Primary tools:** `MagicMock`, `AsyncMock`, `monkeypatch`

**Settings patching:** Always use `monkeypatch.setattr` on the module-level path where the attribute is consumed — not where it is defined:
```python
# Correct — patches the attribute as seen by the module under test
monkeypatch.setattr("app.services.guest_auth.settings.guest_jwt_secret", _SECRET)
monkeypatch.setattr("app.services.llm.settings.openai_api_key", "sk-system-key")
```

**Database mocking:** Factory function returning a `MagicMock` with async methods as `AsyncMock`:
```python
def _mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db
```

**User mocking:** Factory function returning a `MagicMock` with attributes set directly:
```python
def _make_user(is_guest: bool) -> MagicMock:
    u = MagicMock()
    u.is_guest = is_guest
    u.clerk_id = "guest_abc" if is_guest else "user_clerk_123"
    return u
```

**What to mock:**
- External service calls via `monkeypatch` (settings attributes, not the service itself)
- Database sessions via `_mock_db()` factory
- Never mock the module under test itself

**What NOT to mock:**
- The pure functions and domain logic being tested (JWT encode/decode, `resolve_api_key`, schema validation)
- SQLAlchemy model constructors — tested by passing to real mock sessions

### Frontend: `vi` (Vitest)

**Primary tools:** `vi.mock()`, `vi.spyOn()`, `vi.fn()`, `vi.restoreAllMocks()`

**Module mocking:** Full module mock at top of test file:
```typescript
vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    getToken: vi.fn().mockResolvedValue("clerk-token-123"),
  }),
}));
```

**Global API mocking:** `vi.spyOn` on `globalThis`:
```typescript
beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response("ok", { status: 200 })
  );
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});
```

**What to mock:**
- External modules (`@clerk/nextjs`)
- Browser globals (`fetch`, `Date.now`)
- `sessionStorage`/`localStorage` state (clear in `beforeEach`/`afterEach`)

**What NOT to mock:**
- Pure utility functions under test (`formatRelativeTime`, `tryParseImageUrl`)
- React components under test — render them directly with `@testing-library/react`

## Fixtures and Factories

### Backend

**`autouse` fixtures for settings patches:**
```python
@pytest.fixture(autouse=True)
def patch_secret(monkeypatch):
    monkeypatch.setattr("app.services.guest_auth.settings.guest_jwt_secret", _SECRET)
    monkeypatch.setattr("app.services.guest_auth.settings.guest_session_duration_hours", 24)
    monkeypatch.setattr("app.services.guest_auth.settings.guest_max_messages_per_session", 20)
```

**Module-level constants for test data:**
```python
_SECRET = "test-secret-for-unit-tests-exactly-32b"
_ALGORITHM = "HS256"
```

**Factory functions (not fixtures) for mocks:**
```python
def _mock_db(): ...
def _make_user(is_guest: bool) -> MagicMock: ...
```

### Frontend

**Shared base object within `describe` block:**
```typescript
const base = {
  id: "tc-1",
  name: "web_search",
  arguments: JSON.stringify({ query: "vitest testing" }),
  status: "done" as const,
  result: "Found 5 results",
};
```

**Date pinning with `vi.spyOn`:**
```typescript
const NOW = new Date("2025-01-15T12:00:00Z").getTime();
beforeEach(() => {
  vi.spyOn(Date, "now").mockReturnValue(NOW);
});
afterEach(() => {
  vi.restoreAllMocks();
});
```

**Location:** No separate fixtures directory. Test data defined inline within test files.

## Coverage

**Requirements:** Not enforced. No coverage threshold configured in `pyproject.toml` or `vitest.config.ts`.

**`@vitest/coverage-v8` is installed** (in `frontend/package.json` devDependencies) but no coverage script is defined in `package.json`.

**View Coverage (frontend):**
```bash
cd frontend
npx vitest run --coverage
```

**View Coverage (backend):**
```bash
uv run pytest tests/ --cov=app --cov-report=term-missing
```
(requires `pytest-cov`, not currently in dev dependencies)

## Test Types

**Unit Tests (backend):**
- Scope: Individual service functions and pure helpers in isolation
- Pattern: Call the function under test directly; mock only external dependencies (DB, settings)
- Files: All 5 test files in `tests/` are unit tests — no integration or E2E tests

**Unit Tests (frontend):**
- Scope: Individual utility functions, hooks, and components in isolation
- Pattern: `render()` components directly; `renderHook()` for hooks; call utilities directly
- Files: All 4 test files in `frontend/__tests__/`

**Integration Tests:** Not present in either suite.

**E2E Tests:** Not present. No Playwright, Cypress, or similar framework configured.

## Common Patterns

### Async Testing (backend)

```python
@pytest.mark.asyncio
async def test_create_guest_user_returns_user_and_token():
    mock_db = _mock_db()
    user, token = await create_guest_user(mock_db)
    assert user.is_guest is True
    assert user.clerk_id.startswith("guest_")
    mock_db.add.assert_called_once_with(user)
    mock_db.commit.assert_awaited_once()
```

`asyncio_mode = "auto"` in `pyproject.toml` means the decorator is technically optional, but tests still include it explicitly for clarity.

### Error/Exception Testing (backend)

```python
def test_verify_guest_token_rejects_expired_token():
    payload = {"sub": "guest_abc123", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}
    token = jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)
    with pytest.raises(jwt.ExpiredSignatureError):
        verify_guest_token(token)

def test_authenticated_user_without_byok_raises_402():
    user = _make_user(is_guest=False)
    with pytest.raises(HTTPException) as exc_info:
        resolve_api_key(user, user_key=None)
    assert exc_info.value.status_code == 402
    assert exc_info.value.detail["error"] == "byok_required"
```

### User Interaction Testing (frontend)

```typescript
it("expands to show arguments and result on click", async () => {
  const user = userEvent.setup();
  render(<ToolCallDisplay toolCall={base} />);

  // Assert pre-interaction state
  expect(screen.queryByText("Arguments:")).toBeNull();

  await user.click(screen.getByRole("button"));

  // Assert post-interaction state
  expect(screen.getByText("Arguments:")).toBeTruthy();
  expect(screen.getByText("Result:")).toBeTruthy();
});
```

### Hook Testing (frontend)

```typescript
it("attaches Authorization header with Clerk Bearer token", async () => {
  const { result } = renderHook(() => useAuthFetch());
  await result.current("https://api.example.com/chat/");

  expect(fetch).toHaveBeenCalledWith(
    "https://api.example.com/chat/",
    expect.objectContaining({
      headers: expect.objectContaining({
        Authorization: "Bearer clerk-token-123",
      }),
    })
  );
});
```

## CI Integration

**File:** `.github/workflows/test.yml`

**Triggers:** Pull requests to `main`; pushes to any branch except `main`

**Backend job (`backend`):**
- Runs on `ubuntu-latest`
- Installs uv, syncs with `--extra dev`
- Injects test env vars inline (`DATABASE_URL`, `OPENAI_API_KEY`, `GUEST_JWT_SECRET`)
- Runs: `uv run pytest tests/ -v`

**Frontend job (`frontend`):**
- Runs on `ubuntu-latest`
- Node 20, npm cache keyed on `frontend/package-lock.json`
- Runs: `npm ci` then `npm test` from `frontend/` working directory

**Jobs run in parallel** (no dependency between backend and frontend jobs).

---

*Testing analysis: 2026-05-03*
