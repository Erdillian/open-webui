<script lang="ts">
    import { onMount, createEventDispatcher } from 'svelte';
    import { submitOnboarding } from '../api';

    export let show = false;

    const dispatch = createEventDispatcher();

    const questions = [
        { id: 'name', label: "Comment veux-tu qu'on t'appelle ?", category: 'identity', placeholder: 'Ton prénom ou surnom' },
        { id: 'age', label: "Quel est ton âge approximatif ?", category: 'identity', placeholder: 'Ex : 30 ans' },
        { id: 'location', label: "Où vis-tu (ville / pays) ?", category: 'location', placeholder: 'Ex : Paris, France' },
        { id: 'passions', label: "Quelles sont tes passions principales ?", category: 'interests', placeholder: 'Ex : lecture, randonnée, cuisine' },
        { id: 'work', label: "Quelle est ton activité professionnelle / études ?", category: 'professional', placeholder: 'Ex : développeur, étudiant en médecine' },
        { id: 'goals', label: "Quels sont tes objectifs à court terme avec cette IA ?", category: 'goals', placeholder: 'Ex : apprendre le Python, organiser mes idées' },
    ];

    let currentStep = 0;
    let answers: Record<string, string> = {};
    let loading = false;
    let error = '';

    function next() {
        if (currentStep < questions.length - 1) {
            currentStep++;
        }
    }

    function prev() {
        if (currentStep > 0) {
            currentStep--;
        }
    }

    async function finish() {
        loading = true;
        error = '';
        try {
            const payload = questions.map(q => ({
                question: q.label,
                answer: answers[q.id] || '',
                category: q.category,
            }));
            await submitOnboarding(localStorage.token, payload);
            dispatch('done');
        } catch (e: any) {
            error = e.message || 'Erreur lors de la sauvegarde';
        } finally {
            loading = false;
        }
    }

    function skip() {
        dispatch('skip');
    }

    $: if (!show) {
        currentStep = 0;
        answers = {};
        error = '';
    }
</script>

{#if show}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-6 flex flex-col gap-4">
            <div class="flex justify-between items-center">
                <h2 class="text-xl font-bold text-gray-900 dark:text-white">
                    Bienvenue 👋
                </h2>
                <button
                    class="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 underline"
                    on:click={skip}
                >
                    Ignorer
                </button>
            </div>

            <p class="text-sm text-gray-600 dark:text-gray-400">
                Réponds à quelques questions pour que l'IA te connaisse mieux. Cela prendra moins d'une minute.
            </p>

            <div class="flex items-center gap-1 mt-1">
                {#each questions as _, idx}
                    <div
                        class="h-1.5 flex-1 rounded-full transition-colors"
                        class:bg-blue-500={idx <= currentStep}
                        class:bg-gray-200={idx > currentStep}
                        class:dark:bg-gray-700={idx > currentStep}
                    />
                {/each}
            </div>

            <div class="flex flex-col gap-3 mt-2">
                <label class="text-sm font-medium text-gray-800 dark:text-gray-200">
                    {questions[currentStep].label}
                </label>
                <input
                    type="text"
                    class="w-full px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder={questions[currentStep].placeholder}
                    bind:value={answers[questions[currentStep].id]}
                    on:keydown={(e) => {
                        if (e.key === 'Enter') {
                            if (currentStep < questions.length - 1) next();
                            else finish();
                        }
                    }}
                />
            </div>

            {#if error}
                <p class="text-sm text-red-500">{error}</p>
            {/if}

            <div class="flex justify-between items-center mt-2">
                <button
                    class="px-4 py-2 rounded-xl text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition"
                    on:click={prev}
                    disabled={currentStep === 0 || loading}
                    class:opacity-50={currentStep === 0}
                >
                    Précédent
                </button>

                {#if currentStep < questions.length - 1}
                    <button
                        class="px-5 py-2 rounded-xl text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition"
                        on:click={next}
                        disabled={loading}
                    >
                        Suivant
                    </button>
                {:else}
                    <button
                        class="px-5 py-2 rounded-xl text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition flex items-center gap-2"
                        on:click={finish}
                        disabled={loading}
                    >
                        {#if loading}
                            <span class="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                        {/if}
                        Terminer
                    </button>
                {/if}
            </div>
        </div>
    </div>
{/if}
