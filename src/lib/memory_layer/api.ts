/* Client API for memory layer endpoints */

const API_BASE = '/api/mem';

async function fetchJSON(url: string, options?: RequestInit) {
    const res = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...(options?.headers || {})
        }
    });
    if (!res.ok) {
        const text = await res.text();
        throw new Error(`API error ${res.status}: ${text}`);
    }
    return res.json();
}

export async function listMemories(params?: { query?: string; category?: string; include_archived?: boolean }) {
    const qs = new URLSearchParams();
    if (params?.query) qs.set('query', params.query);
    if (params?.category) qs.set('category', params.category);
    if (params?.include_archived) qs.set('include_archived', 'true');
    return fetchJSON(`${API_BASE}/memory/?${qs.toString()}`);
}

export async function createMemory(data: Record<string, unknown>) {
    return fetchJSON(`${API_BASE}/memory/`, {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

export async function updateMemory(id: number, data: Record<string, unknown>) {
    return fetchJSON(`${API_BASE}/memory/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data)
    });
}

export async function deleteMemory(id: number) {
    return fetchJSON(`${API_BASE}/memory/${id}`, { method: 'DELETE' });
}

export async function getProfile() {
    return fetchJSON(`${API_BASE}/profile/`);
}

export async function updateProfile(data: Record<string, unknown>) {
    return fetchJSON(`${API_BASE}/profile/`, {
        method: 'PATCH',
        body: JSON.stringify(data)
    });
}

export async function regenerateProfile() {
    return fetchJSON(`${API_BASE}/profile/regenerate`, { method: 'POST' });
}

export async function getProfileHistory() {
    return fetchJSON(`${API_BASE}/profile/history`);
}

export async function listConflicts(status?: string) {
    const qs = status ? `?status=${status}` : '';
    return fetchJSON(`${API_BASE}/conflicts/${qs}`);
}

export async function updateConflict(id: number, data: Record<string, unknown>) {
    return fetchJSON(`${API_BASE}/conflicts/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data)
    });
}

export async function getOpeningPrompt() {
    return fetchJSON(`${API_BASE}/opening_prompt/`);
}

export async function getHealth() {
    return fetchJSON(`${API_BASE}/health`);
}
