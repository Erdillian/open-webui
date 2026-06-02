# CLAUDE.md — Projet IA Personnelle (Memory Layer sur Open WebUI)

> **Dernière mise à jour** : 2026-06-02
> **Branche active** : `feat/memory-layer`
> **Base** : Fork de [Open WebUI](https://github.com/open-webui/open-webui) (FastAPI + SvelteKit)

---

## 1. Objectif du projet

Construire une **IA conversationnelle personnelle avec mémoire souveraine locale**, exécutée sur PC Windows, en forkant Open WebUI. Le projet réutilise l'ensemble de l'infrastructure native (chat, gestion modèles Ollama, RAG documents, web search, UI) et ajoute une **couche mémoire évolutive** qui :

- Extrait automatiquement les souvenirs des conversations
- Les stocke vectoriellement (ChromaDB) et relationnellement (SQLite)
- Les réinjecte dans le contexte LLM à chaque message
- Maintient un profil utilisateur synthétique auto-généré
- Détecte les conflits et les incohérences
- Consolide les patterns répétitifs hebdomadairement
- Trace tout l'activité dans un système d'audit structuré

---

## 2. Architecture globale

### 2.1 Overlay strategy

Tout notre code est isolé dans des dossiers dédiés. Le code natif d'Open WebUI n'est modifié qu'aux points d'extension strictement nécessaires.

```
open-webui-fork/
├── backend/open_webui/memory_layer/      ← NOTRE CODE BACKEND
│   ├── models/         (SQLAlchemy)
│   ├── schemas/        (Pydantic v2)
│   ├── routers/        (FastAPI endpoints)
│   ├── services/       (business logic)
│   ├── workers/        (async loops)
│   ├── functions/      (Open WebUI Filter Function)
│   ├── retrieval/      (ChromaDB wrapper)
│   ├── embeddings/     (Ollama embed wrapper)
│   ├── prompts/        (prompt templates versionnés)
│   └── config.py
├── src/lib/memory_layer/               ← NOTRE CODE FRONTEND
│   ├── api.ts          (fetch client)
│   ├── components/     (Svelte components)
│   └── stores/
├── src/routes/(app)/                    ← Pages SvelteKit ajoutées
│   ├── memory/+page.svelte
│   ├── profile/+page.svelte
│   ├── conflicts/+page.svelte
│   └── audit/+page.svelte
└── backend/open_webui/migrations/versions/
    ├── 001_create_memory_tables.py   (mem_001)
    ├── 002_add_onboarding_flag.py    (mem_002)
    └── 003_add_audit_log.py          (mem_003)
```

### 2.2 Points de contact avec le code natif

Le seul fichier natif significativement modifié est `backend/open_webui/main.py` :

- **Imports** (~ligne 111) : `from open_webui.memory_layer.routers import ...`
- **Auto-enable filter** (~ligne 115) : `_memory_filter = MemoryFilter()` — active la Filter Function sans configuration admin
- **Lifespan / workers** (~lignes 697-714) : lance `extraction_worker_loop`, `profile_worker_loop`, `consolidation_worker_loop`
- **Routers** (~lignes 1490-1496) : 6 routers ajoutés sous `/api/mem/...`

Le frontend natif modifié est `src/lib/components/layout/Sidebar.svelte` :
- `DEFAULT_PINNED_ITEMS` inclut `'memory', 'profile', 'conflicts', 'audit'`
- `isMenuItemVisible` et `getMenuItemMeta` étendus pour nos 4 pages
- Les icônes sont rendues par du SVG inline dans le composant (pas de fichiers d'icônes séparés)

---

## 3. Modèles de données

### 3.1 Tables custom (préfixe `mem_`)

| Table | Rôle | Clé primaire |
|-------|------|---------------|
| `mem_items` | Souvenirs extraits | `id` (Integer, auto) |
| `mem_conflicts` | Paires de memories contradictoires détectées | `id` (Integer, auto) |
| `mem_profile` | Profil utilisateur synthétique (1 ligne par user) | `user_id` (String) |
| `mem_profile_history` | Snapshots historiques du profil | `id` (Integer, auto) |
| `mem_tags` | Tags custom pour organiser les memories | `id` (Integer, auto) |
| `mem_item_tags` | Association N-N | composite |
| `mem_audit_log` | Tracing structuré de tout l'activité | `id` (Integer, auto) |

### 3.2 SQLAlchemy 2.x — convention importante

- Tous les modèles utilisent `Column(...)` (style 1.x) car Open WebUI utilise une base `Base` custom (`open_webui.internal.db.Base`).
- Le nom de colonne `meta` est utilisé à la place de `metadata` (conflit avec l'attribut SQLAlchemy interne).
- Les colonnes temporelles sont des `BigInteger` (timestamp Unix), pas des `DateTime`.

### 3.3 Stockage vectoriel (ChromaDB)

Collection dédiée `memory_items` (configurable via `MEM_CHROMA_COLLECTION`), distincte de la collection `doc_chunks` native Open WebUI.

Métadonnées stockées par vecteur :
```python
{
    "user_id": str,
    "category": str,
    "importance": float,
    "sensitivity": float,
    "timestamp_event": str,
    "memory_item_id": int,
    "pinned": bool,
    "archived": bool,
}
```

Le pont relationnel ↔ vectoriel se fait via `mem_items.chroma_id`.

---

## 4. Migrations Alembic

Les migrations sont placées dans `backend/open_webui/migrations/versions/` avec un **préfixe `mem_`** pour les distinguer des migrations natives.

| Migration | Description | Down revision |
|-----------|-------------|---------------|
| `mem_001` | Crée `mem_items`, `mem_conflicts`, `mem_profile`, `mem_profile_history`, `mem_tags`, `mem_item_tags` | `a0b1c2d3e4f5` |
| `mem_002` | Ajoute `onboarding_done` à `mem_profile` | `mem_001` |
| `mem_003` | Crée `mem_audit_log` avec indexes | `mem_002` |

**Commande** : `cd backend && alembic upgrade head` (joue aussi les migrations natives d'Open WebUI).

---

## 5. Pipeline mémoire (end-to-end)

### 5.1 Déclenchement — Filter Function `memory_filter`

Fichier : `backend/open_webui/memory_layer/functions/memory_filter.py`

C'est une **Open WebUI Filter Function** (mécanisme natif) qui expose deux hooks :

- **`inlet(body, __user__)`** : appelé AVANT l'appel LLM. Injecte le system prompt enrichi (profil + memories + timestamps + anti-sycophancy + pending conflicts).
- **`outlet(body, __user__)`** : appelé APRÈS la réponse LLM. Capture le dernier échange (user + assistant) et le met en file d'attente pour extraction.

La Filter est **auto-activée** via `_memory_filter = MemoryFilter()` dans `main.py` (pas besoin de la configurer dans l'admin Open WebUI).

Valves (paramètres) :
- `enabled` (default True)
- `k_passive` (default 8) — nombre de memories injectées
- `anti_sycophancy_enabled` (default True)
- `timestamp_prefix_messages` (default False)

### 5.2 Retrieval — `context_builder.py`

Fichier : `backend/open_webui/memory_layer/services/context_builder.py`

À chaque `inlet` :
1. Embed la requête utilisateur via Ollama (`nomic-embed-text`)
2. Query ChromaDB `memory_items` filtré par `user_id`, top-K = `k_passive * 3`
3. Re-ranking par formule Python (importance, recency, pinned boost, sensitivity penalty)
4. Garde top-N (`k_passive`)
5. Construit le system prompt avec les blocs : anti-sycophancy → profil → memories → timestamps → conflicts → notice tools

**Trace** : appel `trace_event(event_type="retrieval_query", ...)` avec les previews des memories injectées.

### 5.3 Extraction — `extractor.py` + `extraction_worker.py`

Fichier worker : `backend/open_webui/memory_layer/workers/extraction_worker.py`

File asyncio interne (`extraction_queue.py`) alimentée par `outlet`. Le worker dépile en continu :

1. **Appel LLM extracteur** (`qwen3-coder-next:cloud` via `/api/generate`) avec prompt `memory_extractor_v1.txt`
2. **Parse JSON** : tableau d'objets `{content, category, importance, sensitivity, timestamp_event, speaker, involves_entities}`
3. **Déduplication** : cosine sim > 0.92 → doublon (TODO: update référence, actuellement ignoré)
4. **Détection de conflits** : 0.75 < cosine < 0.92 → création `mem_conflicts` avec `status='pending'`
5. **Insertion** : `mem_items` + embedding ChromaDB
6. **Incrément** : `memories_since_regen` du profil utilisateur
7. **Trace** : `trace_event(event_type="extraction_created", ...)` ou `"conflict_detected"`

### 5.4 Profil — `profile_worker.py`

Fichier : `backend/open_webui/memory_layer/workers/profile_worker.py`

Boucle infinie qui scanne les utilisateurs ayant des memories toutes les 60 secondes :

- **Full regen** : si `memories_since_regen >= 50` (configurable) OU `last_full_regen > 7 jours`. Appelle le prompt `profile_generator_v1.txt` avec les top-200 memories.
- **Patch incrémental** : toutes les 5 nouvelles memories. Appelle `profile_patcher_v1.txt`.
- **Onboarding trigger** : à la fin de l'onboarding, `_do_full_regen` est lancé en async.

**Trace** : `trace_event(event_type="profile_regen", ...)` ou `"profile_patched"`.

### 5.5 Consolidation — `consolidation_worker.py`

Fichier : `backend/open_webui/memory_layer/workers/consolidation_worker.py`

Worker qui tourne toutes les semaines (`sleep 7*24*3600`) :

1. Récupère les memories de la semaine (catégories `event`, `fact`, `preference`)
2. Clustering sémantique (cosine > 0.85) via ChromaDB
3. Pour chaque cluster de taille >= 3 : appel LLM avec `consolidation_v1.txt` (format JSON)
4. Crée une memory `category="consolidation"` qui référence les sources (`related_to`)
5. Archive les sources (`archived=True`)

**Trace** : `trace_event(event_type="consolidation_created", ...)`.

---

## 6. Système d'audit / tracing

Fichier : `backend/open_webui/memory_layer/services/audit_service.py`

Fonction centrale `trace_event(user_id, event_type, payload, summary, chat_id, memory_id)` écrit dans `mem_audit_log`. Jamais bloquante (try/except silencieux).

**Types d'événements tracés** :
- `inlet_injected` — contexte enrichi injecté
- `outlet_enqueued` — échange mis en file d'extraction
- `extraction_created` — nouvelle memory extraite
- `retrieval_query` — recherche vectorielle effectuée
- `profile_regen` — régénération complète du profil
- `profile_patched` — patch incrémental du profil
- `conflict_detected` — conflit détecté
- `consolidation_created` — consolidation générée
- `onboarding_completed` — questionnaire d'onboarding terminé
- `memory_updated` — modification manuelle d'une memory
- `memory_deleted` — suppression d'une memory

**UI** : page `/audit` (`src/routes/(app)/audit/+page.svelte`) avec filtre par event_type, chat_id, liens vers les memories.

---

## 7. Endpoints API custom

Tous sous `/api/mem/...`

| Endpoint | Description |
|----------|-------------|
| `GET /api/mem/health` | Smoke test |
| `GET /api/mem/memory/?query=&category=&include_archived=` | Liste memories |
| `POST /api/mem/memory/` | Création manuelle |
| `PATCH /api/mem/memory/{id}` | Édition |
| `DELETE /api/mem/memory/{id}` | Suppression |
| `POST /api/mem/memory/onboarding` | Soumission questionnaire onboarding |
| `GET /api/mem/profile/` | Profil utilisateur |
| `PATCH /api/mem/profile/` | Édition profil |
| `POST /api/mem/profile/regenerate` | Force régénération |
| `GET /api/mem/profile/history` | Historique snapshots |
| `GET /api/mem/conflicts/?status=` | Liste conflits |
| `PATCH /api/mem/conflicts/{id}` | Modifier statut conflit |
| `GET /api/mem/opening_prompt/` | Question d'ouverture |
| `GET /api/mem/audit/?event_type=&chat_id=&limit=&offset=` | Logs audit |
| `GET /api/mem/export` | Export JSON mémoire |
| `POST /api/mem/import` | Import JSON mémoire |

---

## 8. Frontend

### 8.1 Pages SvelteKit

| Route | Fichier | Description |
|-------|---------|-------------|
| `/memory` | `src/routes/(app)/memory/+page.svelte` | Liste, édition, tags, archives |
| `/profile` | `src/routes/(app)/profile/+page.svelte` | Visualisation + édition profil |
| `/conflicts` | `src/routes/(app)/conflicts/+page.svelte` | Gestion des conflits détectés |
| `/audit` | `src/routes/(app)/audit/+page.svelte` | Observabilité temps réel |

### 8.2 Composants partagés

Dans `src/lib/memory_layer/components/` :
- `MemoryList.svelte`, `MemoryItem.svelte`
- `ProfileEditor.svelte`
- `ConflictsList.svelte`
- `OnboardingModal.svelte`

### 8.3 Client API

`src/lib/memory_layer/api.ts` — fonctions `fetchJSON` avec auth Bearer depuis `localStorage.token`.

### 8.4 Navigation

Intégration dans la sidebar native via `Sidebar.svelte` :
- `DEFAULT_PINNED_ITEMS` contient les IDs `'memory', 'profile', 'conflicts', 'audit'`
- `isMenuItemVisible(id)` retourne `True` pour ces IDs
- `getMenuItemMeta(id)` retourne `{ label, href, iconType }`
- Les icônes sont des SVG inline dans la fonction de rendu du composant (pas d'import séparé)

---

## 9. Configuration environnement

Variables dans `.env` ou `docker-compose.override.yml` :

```bash
# LLM provider (Open WebUI natif)
OLLAMA_BASE_URL=http://host.docker.internal:11434

# Memory layer
MEM_EMBEDDINGS_MODEL=nomic-embed-text
MEM_EXTRACTOR_MODEL=qwen3-coder-next:cloud
MEM_PROFILE_MODEL=qwen3-coder-next:cloud
MEM_DEFAULT_K_PASSIVE=8
MEM_CONFLICT_SIMILARITY_LOW=0.75
MEM_CONFLICT_SIMILARITY_HIGH=0.92
MEM_PROFILE_REGEN_THRESHOLD=50
MEM_PROFILE_REGEN_DAYS=7
MEM_CONSOLIDATION_CRON="0 3 * * 0"
MEM_OPENING_INACTIVITY_HOURS=12
MEM_CHROMA_COLLECTION=memory_items
MEM_SENSITIVITY_PENALTY_WEIGHT=0.3
MEM_ANTI_SYCOPHANCY_ENABLED=true
```

---

## 10. Branches et workflow Git

| Branche | Rôle |
|---------|------|
| `main` | Suit `upstream/main` d'Open WebUI, rebase mensuel testé |
| `feat/memory-layer` | Branche de travail, poussée sur `origin/feat/memory-layer` |

**Règle d'or** : tout nouveau code va dans `memory_layer/` (backend) ou `lib/memory_layer/` (frontend). Pas de modification du code natif sauf point d'extension documenté.

---

## 11. Démarrage et dev local

### Backend
```bash
cd backend
python -m uvicorn open_webui.main:app --reload --port 8080
```

### Frontend
```bash
cd open-webui-fork
npm run dev
```

### Docker Compose (production-like)
```bash
docker compose up
```

### Migration DB
```bash
cd backend
alembic upgrade head
```

---

## 12. Modèles LLM utilisés

| Usage | Modèle | Endpoint |
|-------|--------|----------|
| Embeddings | `nomic-embed-text` | Ollama `/api/embed` |
| Extraction mémoire | `qwen3-coder-next:cloud` | Ollama `/api/generate` |
| Profil (regen + patch) | `qwen3-coder-next:cloud` | Ollama `/api/generate` |
| Consolidation | `qwen3-coder-next:cloud` | Ollama `/api/generate` (format JSON) |
| Opening prompt | `qwen3-coder-next:cloud` | Ollama `/api/generate` |
| Chat principal | Configurable par l'utilisateur dans l'UI | Open WebUI natif |

---

## 13. Prompts versionnés

Tous dans `backend/open_webui/memory_layer/prompts/` :

- `memory_extractor_v1.txt` — Extraction de memories depuis un échange
- `profile_generator_v1.txt` — Régénération complète du profil
- `profile_patcher_v1.txt` — Patch incrémental du profil
- `consolidation_v1.txt` — Synthèse d'un cluster de memories
- `opening_prompt_v1.txt` — Question d'ouverture personnalisée
- `anti_sycophancy_v1.txt` — Bloc anti-sycophancy injecté systématiquement
- `document_summarizer_v1.txt` — Résumé de document ingéré

---

## 14. TODOs actifs dans le code

| Fichier | Ligne | Description |
|---------|-------|-------------|
| `extractor.py` | ~222 | "Update existing memory with new reference" — quand un doublon est détecté (cosine > 0.92), il faut fusionner les références au lieu d'ignorer silencieusement |
| `memory.py` | ~205 | `POST /api/mem/memory/re-extract` — "Implement re-extraction from chat history" |

---

## 15. Décisions techniques clés à respecter

1. **Pydantic v2** : tous les schemas utilisent `ConfigDict(from_attributes=True)`.
2. **SQLAlchemy** : style 1.x (`Column(...)`) car hérite de `Base` custom Open WebUI.
3. **Async DB** : utiliser `get_async_db()` (context manager) pour toute opération DB.
4. **Fail open** : la Filter Function et l'audit ne doivent jamais planter le chat. Try/except silencieux.
5. **Pas de Celery** : workers = simples `asyncio.create_task()` dans le lifespan FastAPI.
6. **ChromaDB** : utiliser le client déjà initialisé par Open WebUI (`get_chroma_client()`), pas recréer un client.
7. **Windows** : tout le dev et les tests sont sur Windows 11. Les workers utilisent des paths `pathlib`.

---

## 16. Références externes

- **Plan d'implémentation détaillé** : `D:\Assistant\PLAN_IA_PERSONNELLE_v1.3.md`
- **Doc Open WebUI Functions** : https://docs.openwebui.com/features/plugin/functions/
- **Doc Open WebUI Tools** : https://docs.openwebui.com/features/plugin/tools/
- **Doc dev Open WebUI** : https://docs.openwebui.com/getting-started/advanced-topics/development/
- **Mémoires de session** : `C:\Users\erdil\.claude\projects\D--Assistant\memory\`

---

## 17. Glossaire

- **Memory item** : unité atomique de souvenir extraite, stockée et embeddée
- **Consolidation** : memory de synthèse créée à partir d'un cluster de memories répétitives
- **Conflict** : paire de memories sémantiquement proches mais potentiellement contradictoires
- **Context builder** : module qui construit le prompt final envoyé au LLM principal
- **Extracteur** : LLM secondaire qui produit les memory items à partir des échanges
- **Filter Function** : mécanisme natif Open WebUI pour intercepter les messages avant/après LLM
- **Sensitivity** : flag 0-1 qui pénalise le retrieval sauf si la query active le sujet
- **Opening prompt** : question d'ouverture personnalisée générée après inactivité
- **Audit log** : trace structurée de tout l'activité de la couche mémoire

---

*Document maintenu par les sessions Claude Code. Mettre à jour après chaque phase majeure.*
