# Memory Layer Architecture

## Overview

The memory layer is an overlay on top of Open WebUI that adds:
- Persistent memory items extracted from conversations
- Semantic retrieval via ChromaDB + Ollama embeddings
- Synthetic user profile auto-generation
- Conflict detection and resolution
- Weekly memory consolidation
- Opening prompts after inactivity
- Document ingestion to memory
- Export/import of memory data

## Directory Structure

```
backend/open_webui/memory_layer/
├── config.py                  # Environment-based configuration
├── models/                    # SQLAlchemy models (mem_items, mem_conflicts, mem_profile, mem_tags)
├── schemas/                   # Pydantic request/response schemas
├── migrations/versions/       # Alembic migration for mem_* tables
├── routers/                   # FastAPI routers under /api/mem/
│   ├── health.py
│   ├── memory.py
│   ├── profile.py
│   ├── conflicts.py
│   ├── opening.py
│   └── export.py
├── services/                  # Business logic
│   ├── context_builder.py   # System prompt builder
│   ├── extractor.py         # LLM-based memory extraction
│   ├── conflict_service.py  # Conflict CRUD
│   ├── profile_service.py   # Profile CRUD
│   └── opening_service.py   # Opening prompt generation
├── functions/                 # Open WebUI Filter Functions
│   └── memory_filter.py     # inlet (context injection) + outlet (extraction enqueue)
├── tools/                     # Open WebUI Tools
│   ├── search_memory.py
│   └── get_user_profile_section.py
├── retrieval/               # ChromaDB + retriever
│   ├── chroma_client.py
│   └── retriever.py
├── embeddings/              # Ollama embedding wrapper
│   └── ollama_embed.py
├── workers/                 # Background async workers
│   ├── extraction_queue.py
│   ├── extraction_worker.py
│   ├── profile_worker.py
│   ├── consolidation_worker.py
│   └── document_to_memory.py
└── prompts/                 # LLM prompt templates
    ├── memory_extractor_v1.txt
    ├── anti_sycophancy_v1.txt
    ├── profile_generator_v1.txt
    ├── profile_patcher_v1.txt
    ├── consolidation_v1.txt
    ├── opening_prompt_v1.txt
    └── document_summarizer_v1.txt

src/lib/memory_layer/          # Frontend
├── api.ts
├── components/
│   ├── MemoryList.svelte
│   ├── ProfileEditor.svelte
│   └── ConflictsList.svelte
└── stores/

src/routes/(app)/
├── memory/+page.svelte
├── profile/+page.svelte
└── conflicts/+page.svelte
```

## Data Flow

1. **Chat** → `memory_filter.inlet` injects system prompt with profile + memories + timestamps
2. **LLM response** → `memory_filter.outlet` enqueues exchange for extraction
3. **Extraction worker** → calls LLM to extract memories, embeds them, stores in DB + ChromaDB
4. **Conflict detection** → during extraction, similar but non-identical memories create conflict entries
5. **Profile worker** → incremental patches every 5 memories, full regen every 50 or 7 days
6. **Consolidation worker** → weekly clustering of repetitive memories into synthesis memories
7. **Opening prompt** → generated after >12h inactivity based on recent/pinned memories

## API Endpoints

All under `/api/mem/`:

- `GET /health` — health check
- `GET /memory` — list memories
- `POST /memory` — create memory
- `PATCH /memory/{id}` — update memory
- `DELETE /memory/{id}` — delete memory
- `GET /profile` — get profile
- `PATCH /profile` — update profile
- `POST /profile/regenerate` — force regen
- `GET /profile/history` — profile history
- `GET /conflicts` — list conflicts
- `PATCH /conflicts/{id}` — update conflict status
- `GET /opening_prompt` — get opening prompt
- `GET /export` — export memory JSON
- `POST /import` — import memory JSON

## Native Files Modified

- `backend/open_webui/main.py` — router includes, worker startup in lifespan
- `backend/open_webui/migrations/env.py` — import memory layer models for Alembic

See `docs/REBASE_NOTES.md` for details.
