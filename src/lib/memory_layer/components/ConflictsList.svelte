<script lang="ts">
    import { onMount } from 'svelte';
    import { listConflicts, updateConflict } from '../api';

    let conflicts: any[] = [];
    let loading = true;
    let error = '';

    async function load() {
        loading = true;
        error = '';
        try {
            conflicts = await listConflicts(localStorage.token);
        } catch (e: any) {
            error = e.message;
        } finally {
            loading = false;
        }
    }

    async function ignore(id: number) {
        await updateConflict(localStorage.token, id, { status: 'ignored' });
        await load();
    }

    async function resolve(id: number) {
        await updateConflict(localStorage.token, id, { status: 'resolved' });
        await load();
    }

    onMount(load);
</script>

<div class="p-4">
    <h1 class="text-2xl font-bold mb-4">Conflits</h1>

    {#if loading}
        <p>Chargement...</p>
    {:else if error}
        <p class="text-red-500">{error}</p>
    {:else}
        <div class="space-y-2">
            {#each conflicts as c}
                <div class="border rounded p-3">
                    <p class="text-sm text-gray-500">Statut : {c.status} | Similarité : {c.similarity_score?.toFixed(2)}</p>
                    <p>Conflit #{c.id}</p>
                    <div class="flex gap-2 mt-2">
                        {#if c.status === 'pending' || c.status === 'challenged'}
                            <button class="text-xs px-2 py-1 bg-green-200 rounded" on:click={() => resolve(c.id)}>Résolu</button>
                            <button class="text-xs px-2 py-1 bg-gray-200 rounded" on:click={() => ignore(c.id)}>Ignorer</button>
                        {/if}
                    </div>
                </div>
            {:else}
                <p class="text-gray-500">Aucun conflit détecté.</p>
            {/each}
        </div>
    {/if}
</div>
