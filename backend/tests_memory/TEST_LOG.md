# Test Execution Log — memory_layer

## Session 2026-06-02 — Phase 1 (Base suite)
- **Python**: 3.12.10 (venv `.venv`)
- **Pytest**: 8.4.2 + anyio 4.13.0
- **Command**: `pytest tests_memory -v --tb=short`
- **Result**: 43 passed, 0 failed
- **Duration**: ~1.9s

### Fixes Applied During Implementation
1. `test_models.py`: Added `@pytest.mark.anyio` + `expire_on_commit=False` to prevent `MissingGreenlet`.
2. `conftest.py`: Imported `Chat` and `User` native models to register tables in `Base.metadata`.
3. Monkeypatch target aligned with `extractor.py` import site for ChromaDB dimension mismatch.
4. E2E temporal assertions adapted for 2026 vs 2024 scenario dates.

---

## Session 2026-06-02 — Phase 2 (Subagent extension + fixes)
- **Subagents launched**: 3 (Audit, Router tests, Flaky detection)
- **New tests added**: 25 router tests (memory: 12, profile: 7, conflicts: 6)
- **Flaky runs**: 20 randomized executions — 0 flaky tests detected on base suite
- **Command**: `pytest tests_memory -q --tb=short`
- **Result**: 68 passed, 0 failed, 3 warnings (SQLAlchemy/Alembic deprecations)
- **Duration**: ~2.7s

### Fixes Applied During Phase 2
1. **Profile schema mismatch** (`memories_since_regen`): Added `memories_since_regen=0` to `UserProfile` constructors in `test_router_profile.py`.
2. **DB isolation** (list tests polluted by prior test data): Moved cleanup into `db_session` fixture teardown — deletes all memory_layer rows after each test.
3. **Async fixture warnings**: Removed standalone `clean_memory_tables` async autouse fixture; cleanup now happens inside `db_session` teardown, avoiding `PytestRemovedIn9Warning` on sync tests.

### Coverage Snapshot After Phase 2
| Module | Coverage | Detail |
|---|---|---|
| `models/` | **100%** | All ORM tables tested |
| `services/context_builder.py` | **74%** | Prompt assembly |
| `services/extractor.py` | **62%** | LLM extraction pipeline |
| `retrieval/retriever.py` | **45%** | Scoring formulas |
| `routers/memory.py` | **~40%** | CRUD + onboarding |
| `routers/profile.py` | **~35%** | Get/patch/regenerate/history |
| `routers/conflicts.py` | **~30%** | List + patch |
| Routers/workers/consolidation (rest) | **0%** | Still dark |

## Next Actions
- Add `@pytest.mark.slow` tests with real Ollama for end-to-end validation.
- Cover `memory_filter.inlet/outlet` (primary Open WebUI integration point).
- Write worker tests (`profile_worker`, `consolidation_worker`).
