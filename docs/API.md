# Memory Layer API

## Endpoints

### Health
- `GET /api/mem/health` → `{"ok": true}`

### Memory Items
- `GET /api/mem/memory?query=...&category=...&include_archived=false`
- `POST /api/mem/memory` — body: `MemoryItemCreate`
- `PATCH /api/mem/memory/{id}` — body: `MemoryItemUpdate`
- `DELETE /api/mem/memory/{id}`

### Profile
- `GET /api/mem/profile` → `UserProfileResponse`
- `PATCH /api/mem/profile` — body: `UserProfileUpdate`
- `POST /api/mem/profile/regenerate`
- `GET /api/mem/profile/history` → list of `UserProfileHistoryResponse`

### Conflicts
- `GET /api/mem/conflicts?status=pending|challenged|resolved|ignored`
- `PATCH /api/mem/conflicts/{id}` — body: `MemoryConflictUpdate`

### Opening Prompt
- `GET /api/mem/opening_prompt` → `{"prompt": "..."}`

### Export / Import
- `GET /api/mem/export` — returns JSON file download
- `POST /api/mem/import` — multipart/form-data with `file` field
