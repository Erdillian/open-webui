"""Build the enriched system prompt injected before every LLM call."""
import asyncio
import logging
import re
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


def _generate_search_queries(user_message: str) -> list[str]:
    """Generate a diverse set of semantic search queries from a user message.

    The goal is to maximize recall: different phrasings surface different memories.
    """
    # Common French and English stop words + generic verbs to ignore
    stop_words = {
        "fais", "faire", "donne", "donner", "dis", "dire", "explique", "expliquer",
        "resume", "resumer", "liste", "lister", "cherche", "chercher", "trouve", "trouver",
        "suis", "es", "est", "sommes", "etes", "sont", "ai", "as", "a", "avons", "avez", "ont",
        "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "moi", "toi", "lui",
        "mon", "ton", "son", "notre", "votre", "leur", "ma", "ta", "sa", "mes", "tes", "ses",
        "nos", "vos", "leurs", "un", "une", "le", "la", "les", "des", "du", "de", "et", "ou",
        "mais", "donc", "or", "ni", "car", "que", "qui", "quoi", "dont", "ou", "quand", "comment",
        "pourquoi", "parce", "avec", "sans", "dans", "sur", "sous", "par", "pour", "contre",
        "vers", "entre", "parmi", "tout", "tous", "toute", "toutes", "chaque", "plusieurs",
        "quelques", "certains", "certaines", "autre", "autres", "meme", "memes", "seul",
        "seule", "seuls", "seules", "tres", "peu", "beaucoup", "trop", "assez", "bien",
        "mal", "oui", "non", "peut", "peux", "pouvoir", "veux", "vouloir", "dois", "devoir",
        "doit", "fais", "fait", "falloir", "aller", "venir", "voir", "savoir", "penser",
        "pense", "croire", "croit", "travail", "travailler", "vie", "vivre", "personne",
        "quelqu", "quelque", "chose", "rien", "tout", "tous", "aussi", "alors", "ainsi",
        "avant", "apres", "encore", "deja", "toujours", "jamais", "souvent", "parfois",
        "maintenant", "aujourd", "hier", "demain", "ici", "la", "bas", "dois", "peut",
        "make", "give", "tell", "explain", "list", "search", "find", "look", "who", "what",
        "where", "when", "why", "how", "am", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
        "may", "might", "can", "shall", "i", "you", "he", "she", "it", "we", "they",
        "me", "him", "her", "us", "them", "my", "your", "his", "its", "our", "their",
        "this", "that", "these", "those", "a", "an", "the", "and", "or", "but", "if",
        "then", "else", "of", "in", "on", "at", "to", "from", "by", "with", "about",
        "as", "into", "through", "during", "before", "after", "above", "below", "up",
        "down", "out", "off", "over", "under", "again", "further", "then", "once",
    }

    msg = user_message.strip()
    if not msg:
        return []

    queries = set()

    # Main query: the message itself (may help when phrasing is specific)
    queries.add(msg)

    # Detect broad/personal/profile questions and inject domain-specific queries
    lower_msg = msg.lower()
    broad_indicators = [
        "profil", "résum", "resum", "exhausti", "parle-moi", "parle moi",
        "qui je suis", "qui suis-je", "qui suis je", "qui je suis",
        "dis-moi tout", "dis moi tout", "rappelle-moi", "rappelle moi",
        "tout sur moi", "à propos de moi", "a propos de moi",
        "ma vie", "mon profil", "mes infos", "mes informations",
    ]
    is_broad = any(ind in lower_msg for ind in broad_indicators)

    if is_broad:
        # Domain-specific semantic probes to maximize recall on a full profile
        queries.add("travail métier rôle entreprise Didask prompt engineer concepteur pédagogique")
        queries.add("santé corps poids musculation sport fitness vasectomie méditation")
        queries.add("famille parents père mère frère Richad relations proches enfants adoption")
        queries.add("loisirs hobbies passions cirque pole dance mât chinois jeux musique poésie cuisine")
        queries.add("projets ambitions crypto token STAKEPOT assistant Claude atelier gouvernance indépendance financière")
        queries.add("lieu vie Joyeuse Ardèche maison colocation jardin forêt")
        queries.add("relations amicales amour ruptures Zélia Maritchu amis Thibaut Nono Ambre")
        queries.add("valeurs sobriété alcool politique spiritualité engagement associatif KiCaféCa Chouette Guinguette")
    else:
        # Always surface core identity / life context for other questions too
        queries.add("profil identité travail lieu vie santé famille relations hobbies projets")

    # Extract content words (3+ chars, letters/hyphens only)
    tokens = re.findall(r"[A-Za-zÀ-ÿ\-]{3,}", msg.lower())
    content_tokens = [t for t in tokens if t not in stop_words]

    # Single terms
    for t in content_tokens[:10]:
        queries.add(t)

    # Pairs of consecutive content terms (preserve order)
    for i in range(len(content_tokens) - 1):
        queries.add(f"{content_tokens[i]} {content_tokens[i + 1]}")

    # Triplets when available (more precise semantic matches)
    for i in range(len(content_tokens) - 2):
        queries.add(f"{content_tokens[i]} {content_tokens[i + 1]} {content_tokens[i + 2]}")

    # Filter out overly generic / short queries
    filtered = []
    for q in queries:
        words = [w for w in q.split() if w not in stop_words]
        if len(words) >= 1 and len(q) >= 4:
            filtered.append(q)

    # Prioritize longer, richer queries (domain probes first when broad)
    filtered.sort(key=lambda q: (len(q.split()), len(q)), reverse=True)
    return filtered[:20]


async def _retrieve_memories_exhaustive(
    user_id: str,
    user_message: str,
    k_per_query: int = 8,
    max_memories: int = 24,
) -> list[dict]:
    """Run parallel semantic searches and merge/deduplicate results.

    Returns memories sorted by composite score, capped at max_memories.
    """
    queries = _generate_search_queries(user_message)
    if not queries:
        return []

    # Cap k to avoid flooding ChromaDB
    if k_per_query < 1:
        k_per_query = 1
    if k_per_query > 15:
        k_per_query = 15

    async def _search_one(query: str) -> list[dict]:
        try:
            return await search_memories(
                user_id=user_id,
                query=query,
                k=k_per_query,
            )
        except Exception as e:
            log.warning(f"Exhaustive retrieval failed for query '{query[:40]}': {e}")
            return []

    results_per_query = await asyncio.gather(*[_search_one(q) for q in queries])

    # Merge by chroma_id / content, keeping best score
    seen = {}
    for results in results_per_query:
        for r in results:
            content = r.get("content", "").strip()
            if not content:
                continue
            key = r.get("id") or content
            score = r.get("score", 0.0) or 0.0
            if key not in seen or seen[key].get("score", 0.0) < score:
                seen[key] = r

    merged = list(seen.values())
    merged.sort(key=lambda x: x.get("score", 0.0) or 0.0, reverse=True)
    return merged[:max_memories]


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

    # Retrieve relevant memories exhaustively via parallel semantic searches
    try:
        # Run multiple queries in parallel and merge results for broader recall
        top_memories = await _retrieve_memories_exhaustive(
            user_id=user_id,
            user_message=user_message,
            k_per_query=max(6, k_passive),
            max_memories=min(48, max(16, k_passive * 3)),
        )

        # Trace retrieval
        try:
            from open_webui.memory_layer.services.audit_service import trace_event
            await trace_event(
                user_id=user_id,
                event_type="retrieval_query",
                payload={
                    "query": user_message,
                    "k_passive": k_passive,
                    "k_returned": len(top_memories),
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
        "Tu disposes du tool `search_memory` pour rechercher dans la mémoire long-terme de l'utilisateur. "
        "Règles obligatoires :\n"
        "1. Si la question est large ou personnelle (\"qui je suis\", \"résume-moi\", \"parle-moi de moi\", \"mon profil\", \"exhaustif\", \"tout sur moi\"), tu DOIS être exhaustif : fais AU MOINS 6 appels parallèles à `search_memory` avec des requêtes explicites, chacune couvrant un domaine distinct :\n"
        "   - travail / études / compétences\n"
        "   - santé / corps / fitness / alimentation / sommeil\n"
        "   - famille / proches / relations amoureuses / amis\n"
        "   - loisirs / passions / créativité / sport / musique / jeux\n"
        "   - projets personnels / ambitions / finances / crypto / assistant IA / atelier gouvernance\n"
        "   - lieu de vie / logement / environnement / engagement associatif / valeurs / sobriété\n"
        "2. Ne dis jamais \"je n'ai pas plus d'informations\", \"ta mémoire est vide\" ou \"je ne trouve rien\" sans avoir d'abord lancé des recherches ciblées par domaine.\n"
        "3. Si tu manques d'informations sur un aspect précis, appelle `search_memory` avec des mots-clés en français directement liés à ce aspect (noms propres, lieux, activités).\n"
        "4. Quand tu synthétises, structure ta réponse explicitement par domaine de vie. Ne te contente pas du travail : l'utilisateur attend un portrait global incluant santé, famille, relations, loisirs, projets, valeurs et lieu de vie."
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
