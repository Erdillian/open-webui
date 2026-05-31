"""
Open WebUI Tool: search_memory

Allows the LLM to search the user's memory autonomously.

Install via Admin > Tools > Create Tool.
"""
from typing import Optional


class Tools:
    """Tool class required by Open WebUI's tool loading mechanism."""

    def __init__(self):
        pass

    async def search_memory(
        self,
        query: str,
        category: str = "any",
        k: int = 5,
        __user__: dict = {},
    ) -> str:
        """Recherche dans la mémoire personnelle de l'utilisateur.

        Utilise cet outil quand tu as besoin de retrouver un fait, une préférence,
        un événement, un projet, une relation ou une opinion de l'utilisateur
        qui n'est pas déjà présent dans les memories injectées.

        Args:
            query: Requête en langage naturel, formulée pour maximiser la pertinence sémantique.
            category: Filtre optionnel par catégorie (fact, preference, event, project, relation, opinion, any).
            k: Nombre maximum de résultats (1-15, défaut 5).
        """
        try:
            from open_webui.memory_layer.retrieval.retriever import search_memories

            user_id = __user__.get("id", "")
            if not user_id:
                return "Erreur: utilisateur non identifié."

            # Clamp k
            if k < 1:
                k = 1
            if k > 15:
                k = 15

            results = await search_memories(
                user_id=user_id,
                query=query,
                k=k,
                category=category if category != "any" else None,
            )

            if not results:
                return "Aucun souvenir trouvé pour cette requête."

            lines = ["Souvenirs trouvés :"]
            for i, r in enumerate(results, 1):
                meta = r.get("metadata", {})
                cat = meta.get("category", "?")
                importance = meta.get("importance", "?")
                content = r.get("content", "")
                lines.append(f"{i}. [{cat}, importance:{importance}] {content}")

            return "\n".join(lines)

        except Exception as e:
            return f"Erreur lors de la recherche mémoire : {e}"
