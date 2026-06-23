"""
Open WebUI Tool: get_user_profile_section

Allows the LLM to retrieve detailed profile sections.

Install via Admin > Tools > Create Tool.
"""


class Tools:
    """Tool class required by Open WebUI's tool loading mechanism."""

    def __init__(self):
        pass

    async def get_user_profile_section(
        self,
        section: str,
        __user__: dict = {},
    ) -> str:
        """Récupère la version détaillée d'une section du profil utilisateur.

        Args:
            section: La section du profil à récupérer.
                     Valeurs possibles: work, personal, top_of_mind,
                     history_recent, history_earlier, history_long_term, instructions.
        """
        try:
            from open_webui.memory_layer.services.profile_service import get_profile

            user_id = __user__.get("id", "")
            if not user_id:
                return "Erreur: utilisateur non identifié."

            profile = await get_profile(user_id)
            if not profile:
                return "Profil non trouvé."

            full = profile.full_profile_json
            if isinstance(full, str):
                import json
                full = json.loads(full)

            section_map = {
                "work": "Work context",
                "personal": "Personal context",
                "top_of_mind": "Top of mind",
                "history_recent": "Brief history - Recent months",
                "history_earlier": "Brief history - Earlier context",
                "history_long_term": "Brief history - Long-term background",
                "instructions": "Other instructions",
            }

            key = section_map.get(section, section)
            # Try to find the section in the profile JSON
            value = full.get(section)
            if value is None:
                # Try fuzzy match
                for k, v in full.items():
                    if key.lower() in k.lower():
                        value = v
                        break

            if value is None:
                return f"Section '{section}' non trouvée dans le profil. Sections disponibles : {list(full.keys())}"

            return f"**{key}**\n{value}"

        except Exception as e:
            return f"Erreur lors de la récupération du profil : {e}"
