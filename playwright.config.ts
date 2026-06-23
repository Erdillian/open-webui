import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './backend/tests_memory/e2e/playwright',
  fullyParallel: false,
  workers: 1,
  timeout: 120000,
  use: {
    baseURL: 'http://localhost:18080',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    headless: true,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
