<script lang="ts">
    import { onMount } from 'svelte';
    import { getAuditLogs, listMemories } from '$lib/memory_layer/api';

    type AuditEntry = {
        id: number;
        timestamp: number;
        event_type: string;
        payload?: Record<string, unknown>;
        summary?: string;
        chat_id?: string;
        memory_id?: number;
    };

    let logs: AuditEntry[] = [];
    let filteredLogs: AuditEntry[] = [];
    let loading = true;
    let error = '';
    let filterType = 'all';
    let filterChat = '';
    let memoriesMap: Record<number, { content: string; category: string }> = {};

    const eventLabels: Record<string, string> = {
        inlet_injected: '🧠 Injection contexte',
        outlet_enqueued: '📥 Enqueue extraction',
        extraction_created: '✨ Mémoire créée',
        retrieval_query: '🔍 Recherche vectorielle',
        profile_regen: '📋 Profil regénéré',
        profile_patched: '🔧 Profil patché',
        conflict_detected: '⚠️ Conflit détecté',
        consolidation_created: '📦 Consolidation',
        onboarding_completed: '🎓 Onboarding',
        memory_updated: '✏️ Mémoire modifiée',
        memory_deleted: '🗑️ Mémoire supprimée',
    };

    async function load() {
        loading = true;
        error = '';
        try {
            const result = await getAuditLogs(localStorage.token, { limit: 200 });
            logs = result.items || [];
            applyFilter();

            // Fetch memory details for entries with memory_id
            const memIds = [...new Set(logs.filter(l => l.memory_id).map(l => l.memory_id))];
            if (memIds.length) {
                const allMems = await listMemories(localStorage.token);
                for (const m of allMems) {
                    memoriesMap[m.id] = { content: m.content, category: m.category };
                }
            }
        } catch (e: any) {
            error = e.message;
        } finally {
            loading = false;
        }
    }

    function applyFilter() {
        filteredLogs = logs.filter(l => {
            if (filterType !== 'all' && l.event_type !== filterType) return false;
            if (filterChat && l.chat_id !== filterChat) return false;
            return true;
        });
    }

    function formatDate(ts: number) {
        return new Date(ts * 1000).toLocaleString('fr-FR');
    }

    function formatPayload(payload: Record<string, unknown> | undefined) {
        if (!payload) return '';
        const lines: string[] = [];
        for (const [k, v] of Object.entries(payload)) {
            if (k === 'injected_memory_previews' && Array.isArray(v)) {
                lines.push(`→ ${v.length} mémoires injectées`);
                for (const preview of v) {
                    lines.push(`  • ${preview}`);
                }
            } else if (typeof v === 'string' && v.length > 120) {
                lines.push(`${k}: ${v.slice(0, 120)}...`);
            } else {
                lines.push(`${k}: ${JSON.stringify(v)}`);
            }
        }
        return lines.join('\n');
    }

    $: if (filterType || filterChat) applyFilter();

    onMount(load);
</script>

<div class="p-4 max-w-5xl mx-auto">
    <h1 class="text-2xl font-bold mb-4">Audit & Tracing</h1>

    <div class="flex flex-wrap gap-3 mb-4">
        <select bind:value={filterType} class="border rounded px-2 py-1">
            <option value="all">Tous les événements</option>
            {#each Object.entries(eventLabels) as [k, v]}
                <option value={k}>{v}</option>
            {/each}
        </select>
        <input bind:value={filterChat} placeholder="Filtrer par chat_id" class="border rounded px-2 py-1" />
        <button class="px-3 py-1 bg-blue-600 text-white rounded" on:click={load}>🔄 Rafraîchir</button>
    </div>

    {#if loading}
        <p>Chargement...</p>
    {:else if error}
        <p class="text-red-500">{error}</p>
    {:else if filteredLogs.length === 0}
        <p>Aucun log trouvé.</p>
    {:else}
        <div class="space-y-3">
            {#each filteredLogs as entry}
                <div class="border rounded p-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition">
                    <div class="flex items-center justify-between mb-1">
                        <span class="text-xs font-mono text-gray-500">{formatDate(entry.timestamp)}</span>
                        <span class="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-medium">
                            {eventLabels[entry.event_type] || entry.event_type}
                        </span>
                    </div>
                    <p class="text-sm font-medium mb-1">{entry.summary || '(pas de résumé)'}</p>
                    {#if entry.memory_id && memoriesMap[entry.memory_id]}
                        <div class="text-xs text-gray-600 mb-1">
                            <a href="/memory" class="underline">Mémoire #{entry.memory_id}</a>
                            [{memoriesMap[entry.memory_id].category}] {memoriesMap[entry.memory_id].content.slice(0, 80)}...
                        </div>
                    {/if}
                    {#if entry.chat_id}
                        <div class="text-xs text-gray-500 mb-1">chat: {entry.chat_id}</div>
                    {/if}
                    {#if entry.payload && Object.keys(entry.payload).length > 0}
                        <pre class="text-xs bg-gray-100 dark:bg-gray-900 p-2 rounded overflow-x-auto whitespace-pre-wrap">{formatPayload(entry.payload)}</pre>
                    {/if}
                </div>
            {/each}
        </div>
    {/if}
</div>
