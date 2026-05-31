# Architecture Decision Record (ADR)

## 2026-05-31: Use Native Dev Mode Over Docker

- **Decision:** Run the Open WebUI backend locally via `python -m open_webui.main` / `uvicorn` rather than the provided Docker Compose setup.
- **Rationale:** Faster iteration cycle for backend development; avoids Docker build overhead when scaffolding new routers and services.
- **Consequences:** Developers must manage Python dependencies and environment variables locally.

## 2026-05-31 — Overlay strict sur Open WebUI

- **Contexte** : Le projet est un fork d'Open WebUI, pas une réimplémentation.
- **Décision** : Tout notre code va dans `memory_layer/` (backend) et `lib/memory_layer/` (frontend). Les fichiers natifs ne sont modifiés que pour les points d'entrée (`main.py`, `migrations/env.py`).
- **Pourquoi** : Facilite les rebases mensuels sur upstream Open WebUI.

## 2026-05-31 — Asyncio workers plutôt que Celery

- **Contexte** : Besoin de workers background pour extraction, profil, consolidation.
- **Décision** : Utiliser des `asyncio.create_task()` dans le lifespan FastAPI, pas Celery.
- **Pourquoi** : Moins de dépendances, pas besoin de broker Redis, suffisant pour un usage mono-utilisateur.

## 2026-05-31 — ChromaDB natif d'Open WebUI réutilisé

- **Contexte** : Besoin d'un store vectoriel pour les embeddings de mémoire.
- **Décision** : Réutiliser le client ChromaDB déjà configuré par Open WebUI, avec une collection dédiée `memory_items`.
- **Pourquoi** : Évite d'ajouter un nouveau service Docker, reste cohérent avec l'existant.

## 2026-05-31 — Pas d'anonymisation ni chiffrement (MVP)

- **Contexte** : Cahier des charges mentionne anonymisation et chiffrement at-rest.
- **Décision** : Hors MVP, prévu en v2.
- **Pourquoi** : L'anonymisation locale robuste nécessite SQLCipher + tokenisation, complexifie le MVP. Le chiffrement at-rest est aussi reporté.
