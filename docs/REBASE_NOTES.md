# Rebase Notes

This document tracks which native Open WebUI files were touched by the memory layer overlay and why.

## Modified Files

### `backend/open_webui/main.py`
**What changed:**
- Imported all memory layer routers: `health`, `memory`, `profile`, `conflicts`, `opening`, `export`
- Added `app.include_router(...)` calls for each router under `/api/mem/`
- In `lifespan()`: started 3 background workers via `asyncio.create_task()`:
  - `extraction_worker_loop()` — extracts memories from chat exchanges
  - `profile_worker_loop()` — incremental + full profile regeneration
  - `consolidation_worker_loop()` — weekly memory consolidation

**Why:** Entry point for all memory layer backend functionality.

### `backend/open_webui/migrations/env.py`
**What changed:**
- Imported memory layer models (`MemoryItem`, `MemoryConflict`, `UserProfile`, `UserProfileHistory`, `MemoryTag`, `MemoryItemTag`) so Alembic autogenerate includes our tables in `target_metadata`.

**Why:** Required for `alembic upgrade head` to create the `mem_*` tables.

## Unmodified Native Files

All other new functionality lives under:

- `backend/open_webui/memory_layer/`
- `src/lib/memory_layer/`
- `src/routes/(app)/memory/`
- `src/routes/(app)/profile/`
- `src/routes/(app)/conflicts/`

## Rebase Checklist

When rebasing onto a newer Open WebUI version:

1. Check if `backend/open_webui/main.py` lifespan signature changed — adjust worker startup lines if needed.
2. Check if `backend/open_webui/migrations/env.py` model import style changed — adjust our model imports if needed.
3. Verify `backend/open_webui/alembic.ini` `script_location` is still `migrations` — our migration file must remain discoverable.
4. Run smoke tests: `GET /api/mem/health` must return `{"ok": true}`.
5. Run `alembic upgrade head` to ensure tables are created.
