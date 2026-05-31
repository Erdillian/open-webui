<script lang="ts">
    import { onMount } from 'svelte';
    import { listMemories, deleteMemory, updateMemory } from '../api';

    let memories: any[] = [];
    let loading = true;
    let error = '';

    async function load() {
        loading = true;
        error = '';
        try {
            memories = await listMemories();
        } catch (e: any) {
            error = e.message;
        } finally {
            loading = false;
        }
    }

    async function togglePin(mem: any) {
        await updateMemory(mem.id, { pinned: !mem.pinned });
        await load();
    }

    async function toggleArchive(mem: any) {
        await updateMemory(mem.id, { archived: !mem.archived });
        await load();
    }

    async function remove(mem: any) {
        if (!confirm('Supprimer ce souvenir ?')) return;
        await deleteMemory(mem.id);
        await load();
    }

    onMount(load);
</script>

<div class="p-4">
    <h1 class="text-2xl font-bold mb-4">Mémoire</h1>

    {#if loading}
        <p>Chargement...</p>
    {:else if error}
        <p class="text-red-500">{error}</p>
    {:else}
        <div class="space-y-2">
            {#each memories as mem}
                <div class="border rounded p-3 flex justify-between items-start" class:opacity-50={mem.archived}>
                    <div class="flex-1">
                        <p class="text-sm text-gray-500">[{mem.category}] importance: {mem.importance} | sensitivity: {mem.sensitivity}</p>
                        <p>{mem.content}</p>
                    </div>
                    <div class="flex gap-2">
                        <button class="text-xs px-2 py-1 bg-gray-200 rounded" on:click={() => togglePin(mem)}>
                            {mem.pinned ? 'Désépingler' : 'Épingler'}
                        </button>
                        <button class="text-xs px-2 py-1 bg-gray-200 rounded" on:click={() => toggleArchive(mem)}>
                            {mem.archived ? 'Désarchiver' : 'Archiver'}
                        </button>
                        <button class="text-xs px-2 py-1 bg-red-200 rounded" on:click={() => remove(mem)}>
                            Supprimer
                        </button>
                    </div>
                </div>
            {:else}
                <p class="text-gray-500">Aucun souvenir pour le moment.</p>
            {/each}
        </div>
    {/if}
</div>
