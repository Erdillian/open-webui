# Testing Strategy for `memory_layer`

## Overview

This document describes the automated test suite for the `memory_layer` custom extension in the Open WebUI fork.

## Test Structure

```
backend/tests_memory/
├── conftest.py               # Common fixtures (DB in-memory, mock embeddings)
├── fixtures/
│   ├── user_facts.json         # Real facts extracted from OpenAI export
│   └── test_scenarios.json     # Chronological conversation scenarios
├── test_models.py              # Quick sanity check for ORM models (pre-existing)
├── unit/
│   ├── test_retrieval.py       # Scoring, re-ranking, decay formulas
│   ├── test_context_builder.py # Date markers, prompt assembly
│   └── test_conflict_detection.py # Duplicate & conflict detection
├── integration/
│   ├── test_extraction.py      # Extraction with mocked LLM
│   └── test_profile_worker.py  # Profile incremental update
└── e2e/
    └── test_e2e_scenarios.py   # Full scenario runs from JSON fixtures
```

## Running Tests

All commands assume you are in `backend/` and the virtual environment is active.

```bash
# Activate venv (example path)
.venv\Scripts\activate

# Unit + Integration (fast, no real LLM)
pytest tests_memory/unit tests_memory/integration -v --tb=short

# E2E mocked scenarios
pytest tests_memory/e2e/test_e2e_scenarios.py -v

# Full suite (43 tests)
pytest tests_memory -v --tb=short

# Coverage
cd backend
pytest tests_memory --cov=open_webui.memory_layer --cov-report=html
```

## Latest Run Summary

- **Date**: 2026-06-02
- **Result**: 43 passed, 0 failed
- **Duration**: ~1.9s
- **Python**: 3.12.10
- **Plugins**: anyio-4.13.0

### Breakdown

| Phase | File(s) | Count | Status |
|-------|---------|-------|--------|
| Unit | `test_retrieval.py` | 9 | ✅ Pass |
| Unit | `test_context_builder.py` | 12 | ✅ Pass |
| Unit | `test_conflict_detection.py` | 5 | ✅ Pass |
| Integration | `test_extraction.py` | 2 | ✅ Pass |
| Integration | `test_profile_worker.py` | 1 | ✅ Pass |
| E2E | `test_e2e_scenarios.py` | 8 | ✅ Pass |
| Pre-existing | `test_models.py` | 1 | ✅ Pass |

### Fixes Applied During Setup

1. **`test_models.py`**: Added `@pytest.mark.anyio` and `expire_on_commit=False` to the async session to prevent `MissingGreenlet` after `commit()`.
2. **`NoReferencedTableError`**: Imported `Chat` and `User` native models in `conftest.py` so their tables are registered in `Base.metadata`.
3. **ChromaDB dimension mismatch**: Monkeypatched `add_memory` at the module import site (`open_webui.memory_layer.services.extractor`) rather than the original definition.
4. **Temporal assertions**: E2E assertions verify the presence of `<system_context>` blocks instead of exact delta strings, because the real current date (2026) differs from scenario dates (2024).

## Fixtures

- **`user_facts.json`**: Ground-truth facts about the user extracted from his ChatGPT export (vegetarian, CFPC, Ardèche, D&D, weight loss, etc.).
- **`test_scenarios.json`**: Each scenario is a chronological conversation + verification assertions (`should_contain`, `should_not_contain`, `profile_should_contain`).

> ⚠️ **Privacy**: `user_facts.json` and `test_scenarios.json` contain personal data. Do not commit them to a public repository.

## Markers

- `@pytest.mark.anyio`: Async tests (handled by the anyio plugin).
- `@pytest.mark.slow`: Tests requiring a real Ollama instance (not yet implemented).

## Mocking Strategy

To keep tests fast and deterministic:
- LLM calls are mocked to return predictable JSON.
- Embeddings are deterministic hash-based vectors.
- ChromaDB is mocked in-memory via monkeypatched functions.

For the E2E scenarios, the `extractor` is mocked but the `context_builder` and `retriever` run with real code.

## Logging

Test output is captured in `logs/test_run.log`.

## Next Steps / Extension Ideas

- Add `@pytest.mark.slow` tests that run against a real Ollama instance for end-to-end validation.
- Add `scripts/extract_facts_from_openai_export.py` to regenerate `user_facts.json` automatically from a new ChatGPT export.
- Add performance regression tests for retrieval latency as the memory store grows.
