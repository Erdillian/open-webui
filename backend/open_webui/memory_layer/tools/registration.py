"""Auto-registration of memory_layer tools in Open WebUI."""
import logging
import time
from pathlib import Path

from open_webui.internal.db import get_async_db
from open_webui.models.tools import Tool
from open_webui.utils.plugin import load_tool_module_by_id
from open_webui.utils.tools import get_tool_specs

log = logging.getLogger(__name__)

SEARCH_MEMORY_TOOL_ID = "search_memory"
SEARCH_MEMORY_TOOL_NAME = "search_memory"


def _get_search_memory_source() -> str:
    """Return the current source code of the search_memory tool."""
    path = Path(__file__).parent / "search_memory.py"
    return path.read_text(encoding="utf-8")


async def ensure_search_memory_tool(user_id: str = "system") -> Tool | None:
    """Ensure the search_memory tool exists in the DB and is up to date.

    Returns the registered Tool row (or None on failure).
    """
    try:
        source = _get_search_memory_source()

        # Load module to generate correct OpenAI specs
        tool_module, _ = await load_tool_module_by_id(SEARCH_MEMORY_TOOL_ID, content=source)
        specs = get_tool_specs(tool_module)

        async with get_async_db() as db:
            existing = await db.get(Tool, SEARCH_MEMORY_TOOL_ID)
            if existing:
                if existing.content == source and existing.specs == specs:
                    log.debug("search_memory tool already up to date.")
                    return existing
                log.info("Updating search_memory tool content in DB.")
                existing.name = SEARCH_MEMORY_TOOL_NAME
                existing.content = source
                existing.specs = specs
                existing.updated_at = int(time.time())
                await db.commit()
                await db.refresh(existing)
                return existing

            log.info("Auto-registering search_memory tool in DB.")
            tool = Tool(
                id=SEARCH_MEMORY_TOOL_ID,
                name=SEARCH_MEMORY_TOOL_NAME,
                content=source,
                specs=specs,
                meta={"description": "Recherche dans la memoire personnelle de l'utilisateur.", "manifest": {}},
                valves={},
                user_id=user_id,
                updated_at=int(time.time()),
                created_at=int(time.time()),
            )
            db.add(tool)
            await db.commit()
            await db.refresh(tool)
            log.info("search_memory tool registered successfully.")
            return tool
    except Exception as e:
        log.exception(f"Error ensuring search_memory tool: {e}")
        return None
