import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 3 * 60 * 1000,
  expect: {
    timeout: 20 * 1000,
  },
  use: {
    baseURL: process.env.DEMO_BASE_URL || 'http://localhost:8080',
    headless: process.env.PW_HEADLESS === 'true',
    viewport: { width: 1440, height: 900 },
  },
});
