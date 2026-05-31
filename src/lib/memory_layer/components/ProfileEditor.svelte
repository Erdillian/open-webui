<script lang="ts">
    import { onMount } from 'svelte';
    import { getProfile, updateProfile, regenerateProfile, getProfileHistory } from '../api';

    let profile: any = null;
    let history: any[] = [];
    let loading = true;
    let saving = false;
    let error = '';
    let execSummary = '';
    let fullJson = '';

    async function load() {
        loading = true;
        error = '';
        try {
            profile = await getProfile();
            execSummary = profile.executive_summary || '';
            fullJson = JSON.stringify(profile.full_profile_json || {}, null, 2);
            history = await getProfileHistory();
        } catch (e: any) {
            error = e.message;
        } finally {
            loading = false;
        }
    }

    async function save() {
        saving = true;
        try {
            let parsed = {};
            try {
                parsed = JSON.parse(fullJson);
            } catch {
                alert('JSON invalide');
                return;
            }
            await updateProfile({ executive_summary: execSummary, full_profile_json: parsed });
            await load();
        } catch (e: any) {
            error = e.message;
        } finally {
            saving = false;
        }
    }

    async function regen() {
        if (!confirm('Régénérer le profil complet ? Cela peut prendre un moment.')) return;
        await regenerateProfile();
        alert('Régénération lancée en arrière-plan.');
    }

    onMount(load);
</script>

<div class="p-4">
    <h1 class="text-2xl font-bold mb-4">Profil</h1>

    {#if loading}
        <p>Chargement...</p>
    {:else if error}
        <p class="text-red-500">{error}</p>
    {:else}
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium">Résumé exécutif</label>
                <textarea class="w-full border rounded p-2" rows="3" bind:value={execSummary}></textarea>
            </div>

            <div>
                <label class="block text-sm font-medium">Profil détaillé (JSON)</label>
                <textarea class="w-full border rounded p-2 font-mono text-sm" rows="10" bind:value={fullJson}></textarea>
            </div>

            <div class="flex gap-2">
                <button class="px-4 py-2 bg-blue-600 text-white rounded" on:click={save} disabled={saving}>
                    {saving ? 'Sauvegarde...' : 'Sauvegarder'}
                </button>
                <button class="px-4 py-2 bg-gray-200 rounded" on:click={regen}>Régénérer</button>
            </div>

            {#if history.length > 0}
                <h2 class="text-lg font-semibold mt-6">Historique</h2>
                <div class="space-y-1 text-sm">
                    {#each history as h}
                        <div class="border-b py-1">
                            <span class="text-gray-500">{new Date((h.created_at || 0) * 1000).toLocaleString()} — {h.trigger}</span>
                        </div>
                    {/each}
                </div>
            {/if}
        </div>
    {/if}
</div>
