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
        k: int = 10,
        limit: int = 0,
        __user__: dict = {},
    ) -> str:
        """Recherche dans la memoire personnelle de l'utilisateur.

        Utilise cet outil pour retrouver des faits, preferences, evenements, projets,
        relations ou opinions de l'utilisateur qui ne sont pas deja dans le contexte.

        Pour etre exhaustif sur un sujet large, lance plusieurs appels `search_memory`
        en parallele avec des requetes ciblees (ex: "travail Didask", "famille",
        "sante alimentation", "loisirs cirque", "projets perso").

        Args:
            query: Requete en langage naturel, formulee pour maximiser la pertinence semantique.
            category: Filtre optionnel. Laisse 'any' sauf si tu cherches explicitement une categorie exacte connue (fact, health, work, hobby, preference, relationship, etc.).
            k: Nombre maximum de resultats (1-15, defaut 10).
            limit: Alias pour k (certains modeles passent `limit` au lieu de `k`).
        """
        try:
            from open_webui.memory_layer.retrieval.retriever import search_memories

            user_id = __user__.get("id", "")
            if not user_id:
                return "Erreur: utilisateur non identifie."

            # Use limit as fallback for k when models pass limit instead of k
            if limit > 0:
                k = limit

            # Clamp k
            if k < 1:
                k = 10
            if k > 15:
                k = 15

            results = await search_memories(
                user_id=user_id,
                query=query,
                k=k,
                category=category if category and category.lower() != "any" else None,
            )

            if not results:
                return "Aucun souvenir trouve pour cette requete."

            lines = ["Souvenirs trouves :"]
            for i, r in enumerate(results, 1):
                meta = r.get("metadata", {})
                cat = meta.get("category", "?")
                importance = meta.get("importance", "?")
                content = r.get("content", "")
                lines.append(f"{i}. [{cat}, importance:{importance}] {content}")

            return "\n".join(lines)

        except Exception as e:
            return f"Erreur lors de la recherche memoire : {e}"
