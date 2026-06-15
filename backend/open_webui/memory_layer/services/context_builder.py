"""Build the enriched system prompt injected before every LLM call."""
import logging
import time
from datetime import datetime
from typing import Optional

from open_webui.memory_layer.config import get_config
from open_webui.memory_layer.retrieval.retriever import search_memories

log = logging.getLogger(__name__)


def _load_prompt_file(filename: str) -> str:
    """Load a prompt template from the prompts directory."""
    import pathlib

    path = pathlib.Path(__file__).parent.parent / "prompts" / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _format_humanized_delta(last_timestamp: Optional[int]) -> str:
    """Return a human-readable time delta from the last message timestamp."""
    if last_timestamp is None:
        return "inconnu"
    now = int(time.time())
    delta_seconds = now - last_timestamp
    if delta_seconds < 60:
        return "moins d'une minute"
    if delta_seconds < 3600:
        minutes = delta_seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''}"
    if delta_seconds < 86400:
        hours = delta_seconds // 3600
        return f"{hours} heure{'s' if hours > 1 else ''}"
    if delta_seconds < 604800:
        days = delta_seconds // 86400
        return f"{days} jour{'s' if days > 1 else ''}"
    if delta_seconds < 2592000:
        weeks = delta_seconds // 604800
        return f"{weeks} semaine{'s' if weeks > 1 else ''}"
    months = delta_seconds // 2592000
    return f"{months} mois"


def _build_timestamp_block(now_iso: str, last_message_iso: str, humanized_delta: str) -> str:
    return f"""<system_context>
Date et heure actuelles : {now_iso}
Dernier message de ce chat : {last_message_iso}
Temps écoulé depuis le dernier échange : {humanized_delta}
</system_context>"""


def _build_memories_block(memories: list[dict]) -> str:
    if not memories:
        return ""
    lines = ["<relevant_memories>"]
    for mem in memories:
        meta = mem.get("metadata", {})
        importance = meta.get("importance", "N/A")
        date_str = meta.get("timestamp_event", "N/A")
        content = mem.get("content", "").replace("\n", " ")
        lines.append(f"- [importance:{importance}, date:{date_str}] {content}")
    lines.append("</relevant_memories>")
    return "\n".join(lines)


def _build_profile_block(executive_summary: str) -> str:
    if not executive_summary:
        return ""
    return f"""<user_profile>
{executive_summary}
</user_profile>"""


def _build_anti_sycophancy_block() -> str:
    config = get_config()
    if not config.MEM_ANTI_SYCOPHANCY_ENABLED:
        return ""
    return _load_prompt_file("anti_sycophancy_v1.txt")


def _build_conflict_block(pending_conflicts: list[dict]) -> str:
    if not pending_conflicts:
        return ""
    lines = ["<pending_conflict>"]
    for conflict in pending_conflicts:
        mem_a = conflict.get("memory_a_content", "")
        mem_b = conflict.get("memory_b_content", "")
        date_a = conflict.get("memory_a_date", "il y a un moment")
        date_b = conflict.get("memory_b_date", "aujourd'hui")
        lines.append(f"La mémoire contient deux éléments potentiellement contradictoires :")
        lines.append(f"- [{date_a}] L'utilisateur a déclaré : \"{mem_a}\"")
        lines.append(f"- [{date_b}] L'utilisateur vient de déclarer : \"{mem_b}\"")
        lines.append("À un moment opportun dans ta réponse (sans dérailler la conversation), pointe gentiment cette contradiction et demande à l'utilisateur s'il s'agit d'un changement d'avis, d'un oubli, d'une précision ou d'une autre chose. Ne fais pas la morale.")
    lines.append("</pending_conflict>")
    return "\n".join(lines)


async def build_system_prompt(
    user_id: str,
    user_message: str,
    chat_history: list[dict],
    k_passive: int = 8,
    anti_sycophancy: bool = True,
    pending_conflicts: Optional[list[dict]] = None,
    executive_summary: Optional[str] = None,
) -> str:
    """Build the full system prompt to inject before the LLM call.

    Returns the system prompt string containing:
    - Anti-sycophancy block
    - User profile executive summary
    - Relevant memories (top-K passive retrieval)
    - Timestamp context
    - Pending conflict challenge (if any)
    - Tool availability notice
    """
    config = get_config()
    if k_passive <= 0:
        k_passive = config.MEM_DEFAULT_K_PASSIVE

    # Retrieve relevant memories
    try:
        memories = await search_memories(
            user_id=user_id,
            query=user_message,
            k=k_passive * 3,  # Retrieve more for better filtering
        )
        top_memories = memories[:k_passive]

        # Trace retrieval
        try:
            from open_webui.memory_layer.services.audit_service import trace_event
            await trace_event(
                user_id=user_id,
                event_type="retrieval_query",
                payload={
                    "query": user_message,
                    "k_requested": k_passive * 3,
                    "k_returned": len(memories),
                    "k_injected": len(top_memories),
                    "injected_memory_previews": [m.get("content", "")[:80] for m in top_memories],
                },
                summary=f"Retrieval: query='{user_message[:60]}...' -> {len(top_memories)} memories injected",
            )
        except Exception:
            pass
    except Exception as e:
        log.warning(f"Memory retrieval failed: {e}")
        top_memories = []

    # Compute timestamps
    now = datetime.now()
    now_iso = now.isoformat()

    last_message_ts = None
    if chat_history:
        for msg in reversed(chat_history):
            if msg.get("timestamp"):
                last_message_ts = msg["timestamp"]
                break
    last_message_iso = datetime.fromtimestamp(last_message_ts).isoformat() if last_message_ts else "N/A"
    humanized_delta = _format_humanized_delta(last_message_ts)

    # Build blocks
    blocks = []

    # Anti-sycophancy
    if anti_sycophancy:
        sycophancy_block = _build_anti_sycophancy_block()
        if sycophancy_block:
            blocks.append(sycophancy_block)

    # Profile
    if executive_summary:
        blocks.append(_build_profile_block(executive_summary))

    # Memories
    memories_block = _build_memories_block(top_memories)
    if memories_block:
        blocks.append(memories_block)

    # Timestamps
    blocks.append(_build_timestamp_block(now_iso, last_message_iso, humanized_delta))

    # Conflicts
    if pending_conflicts:
        blocks.append(_build_conflict_block(pending_conflicts))

    # Tool notice
    blocks.append(
        "Tu disposes du tool `search_memory` pour rechercher dans la mémoire de l'utilisateur quand les éléments ci-dessus ne suffisent pas, et du tool `get_user_profile_section` pour obtenir la version détaillée d'une section du profil."
    )

    return "\n\n".join(blocks)


def inject_date_markers(messages: list[dict]) -> list[dict]:
    """Insert ephemeral date separator messages into the chat history.

    These markers are NOT persisted; they are reconstructed on each call.
    """
    if not messages:
        return messages

    result = []
    last_date = None

    for msg in messages:
        ts = msg.get("timestamp")
        if ts:
            msg_date = datetime.fromtimestamp(ts).strftime("%A %d %B %Y")
            if msg_date != last_date:
                result.append(
                    {
                        "role": "system",
                        "content": f"--- {msg_date} ---",
                    }
                )
                last_date = msg_date
        result.append(msg)

    return result
