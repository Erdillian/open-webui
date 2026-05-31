"""Opening prompt generation service."""
import logging
import time
from typing import Optional

from sqlalchemy import select

from open_webui.internal.db import get_async_db
from open_webui.memory_layer.config import get_config
from open_webui.memory_layer.models.memory import MemoryItem

log = logging.getLogger(__name__)


async def generate_opening_prompt(user_id: str) -> str:
    """Generate a personalized opening prompt after inactivity.

    Returns an empty string if conditions are not met or if generation fails.
    """
    config = get_config()
    now = int(time.time())

    # Check last activity (we'd need a last_activity field; for now approximate from last memory)
    async with get_async_db() as db:
        stmt = (
            select(MemoryItem)
            .where(MemoryItem.user_id == user_id)
            .where(MemoryItem.archived == False)
            .order_by(MemoryItem.timestamp_created.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        last_memory = result.scalar_one_or_none()

    if last_memory and last_memory.timestamp_created:
        inactivity_hours = (now - last_memory.timestamp_created) / 3600
        if inactivity_hours < config.MEM_OPENING_INACTIVITY_HOURS:
            return ""  # Not enough inactivity

    # Get executive summary
    from open_webui.memory_layer.services.profile_service import get_or_create_profile

    profile = await get_or_create_profile(user_id)
    executive_summary = profile.executive_summary if profile else ""

    # Get top memories (recent or pinned, low sensitivity)
    async with get_async_db() as db:
        stmt = (
            select(MemoryItem)
            .where(MemoryItem.user_id == user_id)
            .where(MemoryItem.archived == False)
            .where(MemoryItem.sensitivity <= 0.5)
            .order_by(MemoryItem.pinned.desc(), MemoryItem.timestamp_created.desc())
            .limit(10)
        )
        result = await db.execute(stmt)
        top_memories = result.scalars().all()

    memory_lines = []
    for m in top_memories:
        ts_str = time.strftime("%Y-%m-%d", time.localtime(m.timestamp_created)) if m.timestamp_created else "?"
        memory_lines.append(f"[{ts_str}] {m.content}")
    top_memories_text = "\n".join(memory_lines) if memory_lines else "Aucun souvenir récent."

    # Build prompt
    import pathlib

    prompt_path = pathlib.Path(__file__).parent.parent / "prompts" / "opening_prompt_v1.txt"
    template = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    if not template:
        return ""

    inactivity_str = _format_inactivity(last_memory.timestamp_created if last_memory else None)
    last_chat_summary = "Dernier chat inconnu."  # We'd need to fetch from Chat model

    prompt = (
        template.replace("{inactivity_duration}", inactivity_str)
        .replace("{executive_summary}", executive_summary)
        .replace("{top_memories}", top_memories_text)
        .replace("{last_chat_summary}", last_chat_summary)
    )

    # Call LLM
    try:
        import os
        import aiohttp

        model = config.MEM_PROFILE_MODEL
        url = f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return ""
                data = await resp.json()
                return data.get("response", "").strip()
    except Exception as e:
        log.warning(f"Opening prompt generation failed: {e}")
        return ""


def _format_inactivity(last_timestamp: Optional[int]) -> str:
    if not last_timestamp:
        return "longtemps"
    now = int(time.time())
    delta = now - last_timestamp
    if delta < 3600:
        minutes = delta // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''}"
    if delta < 86400:
        hours = delta // 3600
        return f"{hours} heure{'s' if hours > 1 else ''}"
    if delta < 604800:
        days = delta // 86400
        return f"{days} jour{'s' if days > 1 else ''}"
    if delta < 2592000:
        weeks = delta // 604800
        return f"{weeks} semaine{'s' if weeks > 1 else ''}"
    months = delta // 2592000
    return f"{months} mois"
