"""Profile worker: incremental patches and full regeneration."""
import asyncio
import json
import logging
import time
from typing import Optional

from open_webui.memory_layer.config import get_config
from open_webui.memory_layer.models.memory import MemoryItem
from open_webui.memory_layer.services.profile_service import (
    get_or_create_profile,
    reset_memories_since_regen,
    snapshot_profile_history,
    update_profile,
)

log = logging.getLogger(__name__)

_running = False


async def _call_llm(prompt: str, model: Optional[str] = None, timeout: float = 60.0) -> str:
    """Call Ollama LLM with a prompt."""
    config = get_config()
    if model is None:
        model = config.MEM_PROFILE_MODEL

    import os
    import aiohttp

    url = f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Profile LLM error {resp.status}: {text}")
            data = await resp.json()
            return data.get("response", "")


async def _do_full_regen(user_id: str) -> None:
    """Regenerate the full profile from top memories."""
    config = get_config()
    log.info(f"Starting full profile regen for user {user_id}")

    # Fetch top memories by importance/recency
    from open_webui.internal.db import get_async_db
    from sqlalchemy import select

    async with get_async_db() as db:
        stmt = (
            select(MemoryItem)
            .where(MemoryItem.user_id == user_id)
            .where(MemoryItem.archived == False)
            .order_by(MemoryItem.importance.desc())
            .limit(200)
        )
        result = await db.execute(stmt)
        memories = result.scalars().all()

    if not memories:
        log.info(f"No memories for user {user_id}, skipping regen")
        return

    # Build prompt
    import pathlib

    prompt_path = pathlib.Path(__file__).parent.parent / "prompts" / "profile_generator_v1.txt"
    template = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    memory_lines = []
    for m in memories:
        ts_str = time.strftime("%Y-%m-%d", time.localtime(m.timestamp_created)) if m.timestamp_created else "?"
        memory_lines.append(f"[{ts_str}] [{m.category}] {m.content}")
    memories_text = "\n".join(memory_lines)

    prompt = template.replace("{memories_text}", memories_text)

    response = await _call_llm(prompt)

    # Parse response - it's a structured text, not JSON
    executive_summary = response[:500] if len(response) > 500 else response

    # Build full_profile_json by parsing sections
    full_profile = _parse_profile_text(response)

    # Snapshot before update
    await snapshot_profile_history(user_id, trigger="full_regen")

    # Update profile
    await update_profile(
        user_id=user_id,
        executive_summary=executive_summary,
        full_profile_json=full_profile,
    )
    await reset_memories_since_regen(user_id)
    log.info(f"Full profile regen completed for user {user_id}")


def _parse_profile_text(text: str) -> dict:
    """Parse the generated profile text into a JSON structure."""
    sections = {}
    current_section = None
    current_lines = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("**") and stripped.endswith("**"):
            if current_section:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = stripped.strip("*").strip().lower().replace(" ", "_")
            current_lines = []
        elif stripped.startswith("## ") or stripped.startswith("### "):
            if current_section:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = stripped.lstrip("# ").strip().lower().replace(" ", "_")
            current_lines = []
        elif current_section:
            current_lines.append(line)

    if current_section and current_lines:
        sections[current_section] = "\n".join(current_lines).strip()

    if not sections:
        sections = {"raw": text}

    return sections


async def _do_incremental_patch(user_id: str, new_memories: list[MemoryItem]) -> None:
    """Apply incremental patches to the profile based on new memories."""
    log.info(f"Starting incremental profile patch for user {user_id} with {len(new_memories)} memories")

    profile = await get_or_create_profile(user_id)
    full = profile.full_profile_json
    if isinstance(full, str):
        full = json.loads(full)

    # Build prompt
    import pathlib

    prompt_path = pathlib.Path(__file__).parent.parent / "prompts" / "profile_patcher_v1.txt"
    template = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    memory_lines = []
    for m in new_memories:
        ts_str = time.strftime("%Y-%m-%d", time.localtime(m.timestamp_created)) if m.timestamp_created else "?"
        memory_lines.append(f"[{ts_str}] [{m.category}] {m.content}")
    new_memories_text = "\n".join(memory_lines)

    prompt = template.replace("{current_profile_json}", json.dumps(full, ensure_ascii=False)).replace(
        "{new_memories_text}", new_memories_text
    )

    response = await _call_llm(prompt)

    # Try to parse patches
    try:
        patches = json.loads(response)
        if isinstance(patches, list):
            for patch in patches:
                section = patch.get("section")
                action = patch.get("action")
                new_value = patch.get("new_value")
                if section and action and new_value is not None:
                    if action == "replace":
                        full[section] = new_value
                    elif action == "add":
                        existing = full.get(section, "")
                        full[section] = existing + "\n" + new_value if existing else new_value
    except Exception as e:
        log.warning(f"Failed to parse incremental patches: {e}")

    # Snapshot before update
    await snapshot_profile_history(user_id, trigger="incremental")

    # Update executive summary from full profile
    exec_summary = full.get("top_of_mind", "")[:500] if full else ""

    await update_profile(
        user_id=user_id,
        executive_summary=exec_summary,
        full_profile_json=full,
    )
    log.info(f"Incremental profile patch completed for user {user_id}")


async def check_and_run_profile_updates(user_id: str) -> None:
    """Check if profile needs update and run the appropriate update."""
    config = get_config()
    profile = await get_or_create_profile(user_id)

    # Check if full regen is needed
    needs_full_regen = False
    if profile.memories_since_regen and profile.memories_since_regen >= config.MEM_PROFILE_REGEN_THRESHOLD:
        needs_full_regen = True

    if profile.last_full_regen:
        days_since = (int(time.time()) - profile.last_full_regen) / 86400
        if days_since >= config.MEM_PROFILE_REGEN_DAYS:
            needs_full_regen = True

    if needs_full_regen:
        await _do_full_regen(user_id)
        return

    # Check if incremental patch is needed (every 5 new memories)
    if profile.memories_since_regen and profile.memories_since_regen % 5 == 0 and profile.memories_since_regen > 0:
        # Fetch last 5 memories
        from open_webui.internal.db import get_async_db
        from sqlalchemy import select

        async with get_async_db() as db:
            stmt = (
                select(MemoryItem)
                .where(MemoryItem.user_id == user_id)
                .where(MemoryItem.archived == False)
                .order_by(MemoryItem.timestamp_created.desc())
                .limit(5)
            )
            result = await db.execute(stmt)
            new_memories = result.scalars().all()

        if new_memories:
            await _do_incremental_patch(user_id, list(new_memories))


async def profile_worker_loop() -> None:
    """Main loop for the profile worker.

    Polls periodically to check if profiles need updates.
    """
    global _running
    _running = True
    log.info("Profile worker started.")

    while _running:
        try:
            # Scan users with memories and check if profile needs update
            from open_webui.internal.db import get_async_db
            from sqlalchemy import select, distinct

            async with get_async_db() as db:
                stmt = select(distinct(MemoryItem.user_id))
                result = await db.execute(stmt)
                user_ids = [row[0] for row in result.fetchall()]

            for user_id in user_ids:
                if not _running:
                    break
                try:
                    await check_and_run_profile_updates(user_id)
                except Exception as user_e:
                    log.warning(f"Profile update check failed for user {user_id}: {user_e}")

            await asyncio.sleep(60)  # Check every minute
        except asyncio.CancelledError:
            log.info("Profile worker cancelled.")
            break
        except Exception as e:
            log.error(f"Profile worker error: {e}")
            await asyncio.sleep(10)

    _running = False
    log.info("Profile worker stopped.")


def stop_worker() -> None:
    global _running
    _running = False
