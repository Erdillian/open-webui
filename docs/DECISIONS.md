# Architecture Decision Record (ADR)

## 2026-05-31: Use Native Dev Mode Over Docker

- **Decision:** Run the Open WebUI backend locally via `python -m open_webui.main` / `uvicorn` rather than the provided Docker Compose setup.
- **Rationale:** Faster iteration cycle for backend development; avoids Docker build overhead when scaffolding new routers and services.
- **Consequences:** Developers must manage Python dependencies and environment variables locally.
