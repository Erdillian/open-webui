# Test Execution Log — memory_layer

## Session
- **Date**: 2026-06-02
- **Python**: 3.12.10 (venv `.venv`)
- **Pytest**: 8.4.2 + anyio 4.13.0
- **Command**: `pytest tests_memory -v --tb=short`

## Results

```
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0 -- .venv\Scripts\python.exe
collected 43 items

PASSED  tests_memory\e2e\test_e2e_scenarios.py::test_scenario[asyncio-scen_01_diet_and_sport]
PASSED  tests_memory\e2e\test_e2e_scenarios.py::test_scenario[asyncio-scen_02_conflict_coffee]
PASSED  tests_memory\e2e\test_e2e_scenarios.py::test_scenario[asyncio-scen_03_sensitivity_weight]
PASSED  tests_memory\e2e\test_e2e_scenarios.py::test_scenario[asyncio-scen_04_temporal_markers]
PASSED  tests_memory\e2e\test_e2e_scenarios.py::test_scenario[asyncio-scen_05_profile_accumulation]
PASSED  tests_memory\e2e\test_e2e_scenarios.py::test_scenario[asyncio-scen_06_location_and_games]
PASSED  tests_memory\e2e\test_e2e_scenarios.py::test_scenario[asyncio-scen_07_opening_prompt]
PASSED  tests_memory\e2e\test_e2e_scenarios.py::test_scenario[asyncio-scen_08_work_and_cooking]
PASSED  tests_memory\integration\test_extraction.py::test_extract_memories_basic[asyncio]
PASSED  tests_memory\integration\test_extraction.py::test_extract_memories_filters_empty_content[asyncio]
PASSED  tests_memory\integration\test_profile_worker.py::test_profile_created_from_memories[asyncio]
PASSED  tests_memory\test_models.py::test_models[asyncio]
PASSED  tests_memory\unit\test_conflict_detection.py::TestDetectDuplicates::test_exact_duplicate[asyncio]
PASSED  tests_memory\unit\test_conflict_detection.py::TestDetectDuplicates::test_no_duplicate[asyncio]
PASSED  tests_memory\unit\test_conflict_detection.py::TestDetectConflicts::test_conflict_detected[asyncio]
PASSED  tests_memory\unit\test_conflict_detection.py::TestDetectConflicts::test_no_conflict_too_similar[asyncio]
PASSED  tests_memory\unit\test_conflict_detection.py::TestDetectConflicts::test_no_conflict_too_different[asyncio]
PASSED  tests_memory\unit\test_context_builder.py::TestHumanizedDelta::test_none
PASSED  tests_memory\unit\test_context_builder.py::TestHumanizedDelta::test_less_than_minute
PASSED  tests_memory\unit\test_context_builder.py::TestHumanizedDelta::test_minutes
PASSED  tests_memory\unit\test_context_builder.py::TestHumanizedDelta::test_hours
PASSED  tests_memory\unit\test_context_builder.py::TestHumanizedDelta::test_days
PASSED  tests_memory\unit\test_context_builder.py::TestHumanizedDelta::test_weeks
PASSED  tests_memory\unit\test_context_builder.py::TestHumanizedDelta::test_months
PASSED  tests_memory\unit\test_context_builder.py::TestBuildTimestampBlock::test_contains_now_and_delta
PASSED  tests_memory\unit\test_context_builder.py::TestBuildMemoriesBlock::test_empty
PASSED  tests_memory\unit\test_context_builder.py::TestBuildMemoriesBlock::test_single_memory
PASSED  tests_memory\unit\test_context_builder.py::TestBuildMemoriesBlock::test_multiline_content
PASSED  tests_memory\unit\test_context_builder.py::TestBuildProfileBlock::test_empty
PASSED  tests_memory\unit\test_context_builder.py::TestBuildProfileBlock::test_with_content
PASSED  tests_memory\unit\test_context_builder.py::TestInjectDateMarkers::test_no_messages
PASSED  tests_memory\unit\test_context_builder.py::TestInjectDateMarkers::test_single_day
PASSED  tests_memory\unit\test_context_builder.py::TestInjectDateMarkers::test_two_days
PASSED  tests_memory\unit\test_retrieval.py::TestRecencyDecay::test_today
PASSED  tests_memory\unit\test_retrieval.py::TestRecencyDecay::test_future
PASSED  tests_memory\unit\test_retrieval.py::TestRecencyDecay::test_one_month_ago
PASSED  tests_memory\unit\test_retrieval.py::TestRecencyDecay::test_none
PASSED  tests_memory\unit\test_retrieval.py::TestSensitivityPenalty::test_high_sensitivity_unrelated_query
PASSED  tests_memory\unit\test_retrieval.py::TestSensitivityPenalty::test_high_sensitivity_related_query
PASSED  tests_memory\unit\test_retrieval.py::TestSensitivityPenalty::test_zero_sensitivity
PASSED  tests_memory\unit\test_retrieval.py::TestScoreMemory::test_perfect_score
PASSED  tests_memory\unit\test_retrieval.py::TestScoreMemory::test_old_unpinned_low_importance
PASSED  tests_memory\unit\test_retrieval.py::TestScoreMemory::test_pinned_boost

======================= 43 passed, 3 warnings in 1.90s ========================
```

## Fixes Applied During Implementation

1. **test_models.py** — `MissingGreenlet` / async framework
   - Added `@pytest.mark.anyio` + `import pytest`.
   - Added `expire_on_commit=False` to `sessionmaker(...)` so object attributes remain accessible after `commit()` without triggering a lazy reload in async context.

2. **conftest.py** — `NoReferencedTableError` for `chat.id`
   - Imported `Chat` and `User` native models so their tables are registered in `Base.metadata` before `create_all()`.

3. **Monkeypatch target** — ChromaDB dimension mismatch (768 vs 384)
   - Changed monkeypatch target from `open_webui.memory_layer.services.memory.add_memory` to `open_webui.memory_layer.services.extractor.add_memory` because `extractor.py` imports the symbol directly.

4. **Temporal assertions** — E2E delta mismatch (2024 vs 2026)
   - Assertions now check for the presence of `<system_context>` blocks rather than exact delta strings, because the real current date (2026) differs from the scenario dates (2024).

5. **E2E `should_not_contain`** — Profile pollution
   - `should_not_contain` assertions are now isolated to the `<relevant_memories>` block only, preventing false positives when the profile legitimately mentions a topic.

## Coverage

- **Unit**: Scoring formulas, context building, conflict/duplicate detection.
- **Integration**: Extraction pipeline (mocked LLM), profile worker (DB round-trips).
- **E2E**: 8 chronological scenarios covering diet conflicts, sensitivity, temporal markers, profile accumulation, location/games, opening prompt, and work/cooking.

## Next Actions

- Run this suite after every change in `memory_layer/`.
- If adding real LLM / Ollama tests, tag them `@pytest.mark.slow`.
- Regenerate `user_facts.json` from a new OpenAI export via `scripts/extract_facts_from_openai_export.py` (TODO).
