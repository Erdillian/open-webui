/* Client API for memory layer endpoints */

import { WEBUI_BASE_URL } from '$lib/constants';

const API_BASE = `${WEBUI_BASE_URL}/api/mem`;

async function fetchJSON(url: string, token: string, options?: RequestInit) {
    const res = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            ...(options?.headers || {})
        }
    });
    if (!res.ok) {
        const text = await res.text();
        throw new Error(`API error ${res.status}: ${text}`);
    }
    return res.json();
}

export async function listMemories(token: string, params?: { query?: string; category?: string; include_archived?: boolean }) {
    const qs = new URLSearchParams();
    if (params?.query) qs.set('query', params.query);
    if (params?.category) qs.set('category', params.category);
    if (params?.include_archived) qs.set('include_archived', 'true');
    return fetchJSON(`${API_BASE}/memory/?${qs.toString()}`, token);
}

export async function createMemory(token: string, data: Record<string, unknown>) {
    return fetchJSON(`${API_BASE}/memory/`, token, {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

export async function updateMemory(token: string, id: number, data: Record<string, unknown>) {
    return fetchJSON(`${API_BASE}/memory/${id}`, token, {
        method: 'PATCH',
        body: JSON.stringify(data)
    });
}

export async function deleteMemory(token: string, id: number) {
    return fetchJSON(`${API_BASE}/memory/${id}`, token, { method: 'DELETE' });
}

export async function getProfile(token: string) {
    return fetchJSON(`${API_BASE}/profile/`, token);
}

export async function updateProfile(token: string, data: Record<string, unknown>) {
    return fetchJSON(`${API_BASE}/profile/`, token, {
        method: 'PATCH',
        body: JSON.stringify(data)
    });
}

export async function regenerateProfile(token: string) {
    return fetchJSON(`${API_BASE}/profile/regenerate`, token, { method: 'POST' });
}

export async function getProfileHistory(token: string) {
    return fetchJSON(`${API_BASE}/profile/history`, token);
}

export async function listConflicts(token: string, status?: string) {
    const qs = status ? `?status=${status}` : '';
    return fetchJSON(`${API_BASE}/conflicts/${qs}`, token);
}

export async function updateConflict(token: string, id: number, data: Record<string, unknown>) {
    return fetchJSON(`${API_BASE}/conflicts/${id}`, token, {
        method: 'PATCH',
        body: JSON.stringify(data)
    });
}

export async function getOpeningPrompt(token: string) {
    return fetchJSON(`${API_BASE}/opening_prompt/`, token);
}

export async function getHealth(token: string) {
    return fetchJSON(`${API_BASE}/health`, token);
}

export async function getAuditLogs(token: string, params?: { event_type?: string; chat_id?: string; limit?: number; offset?: number }) {
    const qs = new URLSearchParams();
    if (params?.event_type) qs.set('event_type', params.event_type);
    if (params?.chat_id) qs.set('chat_id', params.chat_id);
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    return fetchJSON(`${API_BASE}/audit/?${qs.toString()}`, token);
}

export async function submitOnboarding(token: string, answers: { question: string; answer: string; category: string }[]) {
    return fetchJSON(`${API_BASE}/memory/onboarding`, token, {
        method: 'POST',
        body: JSON.stringify({ answers })
    });
}
