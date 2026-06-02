import { test, expect, Page } from '@playwright/test';

/**
 * End-to-end test for the memory_layer feature in Open WebUI.
 *
 * Prerequisites:
 * - Open WebUI frontend running at http://localhost:18080
 * - A backend model configured and available (so the assistant can reply)
 * - Playwright installed: npm init playwright@latest (or npx playwright install)
 *
 * Run with:
 *   npx playwright test tests_memory/e2e/playwright/test_memory_layer_live.spec.ts
 */

test.setTimeout(120000);

const BASE_URL = 'http://localhost:18080';
const TEST_EMAIL = 'memory.test@example.com';
const TEST_PASSWORD = 'MemoryTest123!';
const TEST_NAME = 'Memory Test User';

/**
 * Helper: create an account or sign in if the user already exists.
 * Handles the "onboarding" (first-run admin creation) flow as well as normal sign-up.
 */
async function signUpOrSignIn(page: Page) {
	await page.setViewportSize({ width: 1280, height: 720 });

	// Use the backend API directly to sign up / sign in — much more reliable than the UI form
	const authResponse = await page.evaluate(async ({ email, password, name, baseUrl }) => {
		// Try sign-in first
		let res = await fetch(`${baseUrl}/api/v1/auths/signin`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ email, password }),
		});
		if (!res.ok) {
			// Fallback to sign-up
			res = await fetch(`${baseUrl}/api/v1/auths/signup`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email, password, name }),
			});
		}
		return res.ok ? await res.json() : null;
	}, { email: TEST_EMAIL, password: TEST_PASSWORD, name: TEST_NAME, baseUrl: BASE_URL });

	if (!authResponse || !authResponse.token) {
		throw new Error('Failed to authenticate via API');
	}

	// Seed localStorage so the UI thinks we are logged in
	await page.goto(`${BASE_URL}/auth`);
	await page.evaluate((token: string) => {
		localStorage.setItem('token', token);
	}, authResponse.token);

	// Now navigate to the app — should redirect away from /auth automatically
	await page.goto(`${BASE_URL}/`);
	await page.waitForURL(/^(?!.*\/auth).*$/, { timeout: 30000 });

	// Dismiss the "What's New" release-notes modal if it appears
	const okayButton = page.locator('button').filter({ hasText: /Okay, Let's Go!/i });
	if (await okayButton.isVisible().catch(() => false)) {
		await okayButton.click();
	}
}

/**
 * Helper: start a brand-new chat by clicking the hidden new-chat button
 * or navigating to root.
 */
async function startNewChat(page: Page) {
	await page.goto(`${BASE_URL}/`);
	// Wait for the chat page to load
	await page.waitForSelector('#chat-input', { timeout: 30000 });

	// Dismiss the "What's New" release-notes modal if it appears
	const okayButton = page.locator('button').filter({ hasText: /Okay, Let's Go!/i });
	if (await okayButton.isVisible().catch(() => false)) {
		await okayButton.click();
	}

	// Dismiss the memory_layer onboarding modal (Bienvenue) if it appears
	const skipOnboarding = page.locator('a, button').filter({ hasText: /Ignorer/i });
	if (await skipOnboarding.isVisible().catch(() => false)) {
		await skipOnboarding.click();
	}
}

/**
 * Helper: send a message in the current chat.
 */
async function sendMessage(page: Page, text: string) {
	const input = page.locator('#chat-input');
	await input.waitFor({ state: 'visible', timeout: 30000 });
	await input.click();
	await input.fill(text);
	await page.waitForTimeout(300); // let ProseMirror settle
	await page.locator('#send-message-button').click();
}

/**
 * Helper: wait for the last assistant response to finish streaming.
 */
async function waitForLastResponse(page: Page) {
	// While the assistant is generating, the response-content-container may be empty
	// and a Skeleton is shown. We wait until the container has non-empty text.
	const lastResponse = page.locator('#response-content-container').last();
	await lastResponse.waitFor({ timeout: 60000 });

	// Wait until the skeleton disappears (i.e. container is no longer just skeleton)
	await expect.poll(async () => {
		const text = await lastResponse.textContent();
		return (text ?? '').trim().length > 0;
	}, {
		message: 'Waiting for assistant response to contain text',
		interval: 1000,
		timeout: 60000,
	}).toBe(true);

	// Give a short buffer for any trailing UI updates
	await page.waitForTimeout(1000);
}

/**
 * Helper: fetch the text of the last assistant response.
 */
async function getLastResponseText(page: Page): Promise<string> {
	const lastResponse = page.locator('#response-content-container').last();
	return (await lastResponse.textContent()) ?? '';
}

test('memory_layer live e2e – remembers personal facts across chats', async ({ page }) => {
	// ------------------------------------------------------------------
	// 1. Create account (or sign in)
	// ------------------------------------------------------------------
	await signUpOrSignIn(page);

	// ------------------------------------------------------------------
	// 2. Start a new chat
	// ------------------------------------------------------------------
	await startNewChat(page);

	// ------------------------------------------------------------------
	// 3. Send a personal message
	// ------------------------------------------------------------------
	const personalMessage = 'Je suis végétarien et j\'habite en Ardèche. J\'adore jouer à Donjons et Dragons.';
	await sendMessage(page, personalMessage);

	// ------------------------------------------------------------------
	// 4. Wait for the assistant response
	// ------------------------------------------------------------------
	await waitForLastResponse(page);

	// ------------------------------------------------------------------
	// 5. Wait for asynchronous memory extraction to finish
	// ------------------------------------------------------------------
	await expect.poll(async () => {
		const token = await page.evaluate(() => localStorage.getItem('token'));
		const res = await fetch(`${BASE_URL}/api/mem/memory/`, {
			headers: { Authorization: `Bearer ${token}` },
		});
		if (!res.ok) return 0;
		const data = await res.json();
		return Array.isArray(data) ? data.length : 0;
	}, {
		message: 'Waiting for at least one memory to be extracted',
		interval: 2000,
		timeout: 60000,
	}).toBeGreaterThan(0);

	// ------------------------------------------------------------------
	// 6. Start a NEW chat (to force a fresh context)
	// ------------------------------------------------------------------
	await startNewChat(page);
	await page.waitForTimeout(1000);

	// ------------------------------------------------------------------
	// 6. Send a message that should trigger memory usage
	// ------------------------------------------------------------------
	await sendMessage(page, 'Qu\'est-ce que je mange ce soir ?');
	await waitForLastResponse(page);

	// ------------------------------------------------------------------
	// 7. Assert that the assistant response mentions vegetarian-related suggestions
	// ------------------------------------------------------------------
	const responseText = await getLastResponseText(page);
	const lowerResponse = responseText.toLowerCase();

	const vegetarianKeywords = [
		'végétarien',
		'végé',
		'sans viande',
		'légume',
		'végétal',
		'plante',
		'végétalien',
		'fromage',
		'salade',
		'soupe',
		'gratin',
		'omelette',
	];

	const hasVegetarianHint = vegetarianKeywords.some((kw) => lowerResponse.includes(kw));
	expect(
		hasVegetarianHint,
		`Expected the assistant response to mention vegetarian-related food, but got:\n${responseText}`
	).toBe(true);

	// ------------------------------------------------------------------
	// 8. Navigate to the "Mémoire" tab
	// ------------------------------------------------------------------
	// Memory extraction is asynchronous (outlet hook). Give it time, then refresh.
	// TODO: adjust sleep duration depending on how fast the backend extracts memories
	await page.waitForTimeout(8000);
	await page.reload();

	// Navigate via direct URL (most reliable)
	await page.goto(`${BASE_URL}/memory`);

	// Alternatively, if you prefer the sidebar link, use:
	// const memoryLink = page.locator('a, button').filter({ hasText: /Mémoire/i });
	// if (await memoryLink.isVisible().catch(() => false)) {
	//   await memoryLink.click();
	// } else {
	//   throw new Error('The "Mémoire" tab is not visible in the sidebar.');
	// }

	await page.waitForSelector('h1:has-text("Mémoire")', { timeout: 30000 });

	// ------------------------------------------------------------------
	// 9. Assert that a memory was extracted
	// ------------------------------------------------------------------
	// Wait for the list to finish loading
	const loadingText = page.locator('text=Chargement...');
	await expect(loadingText).toHaveCount(0, { timeout: 15000 });

	// The memories are rendered in a list of bordered cards. We grab all of them.
	const memoryCards = page.locator('.border.rounded.p-3');
	const count = await memoryCards.count();
	expect(count, 'Expected at least one memory to have been extracted').toBeGreaterThan(0);

	// At least one card should mention one of the personal facts
	const personalKeywords = ['végétarien', 'ardèche', 'donjons et dragons'];
	let foundPersonalFact = false;
	for (let i = 0; i < count; i++) {
		const cardText = (await memoryCards.nth(i).textContent())?.toLowerCase() ?? '';
		if (personalKeywords.some((kw) => cardText.includes(kw))) {
			foundPersonalFact = true;
			break;
		}
	}

	expect(
		foundPersonalFact,
		`Expected at least one memory card to mention "végétarien", "Ardèche", or "Donjons et Dragons", but none did.`
	).toBe(true);
});
