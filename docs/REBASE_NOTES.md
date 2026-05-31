# Rebase Notes

This document tracks which native Open WebUI files were touched by the memory layer overlay and why.

## Modified Files

- `backend/open_webui/main.py`
  - Imported `open_webui.memory_layer.routers.health` router.
  - Added `app.include_router(health.router, prefix="/api/mem", tags=["memory_layer"])` to wire the memory layer API endpoints into the FastAPI application.
  - This is the minimal required touch-point to expose memory layer routes.

## Unmodified Native Files

All other new functionality lives under:

- `backend/open_webui/memory_layer/`
- `src/lib/memory_layer/`
- `src/routes/(app)/memory/`
- `src/routes/(app)/profile/`
- `src/routes/(app)/conflicts/`
