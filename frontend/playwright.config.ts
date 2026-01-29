import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E Test Configuration
 *
 * Supports multiple test profiles via E2E_PROFILE env var:
 * - default: Core functionality (backend + frontend)
 * - magic-import: Magic Import features (requires Celery + Redis)
 * - dataspace: Dataspace features (requires BaSyx, EDC, DTR, Vault)
 * - plc: PLC4X Bridge features (requires Dataspace + PLC4X)
 *
 * Usage:
 *   npx playwright test                          # Run all default tests
 *   E2E_PROFILE=dataspace npx playwright test    # Run dataspace tests
 *   npx playwright test --project=chromium       # Run specific browser
 */

// Determine base URLs from environment
const BASE_URL = process.env.DEMO_BASE_URL || 'http://localhost:8080';
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _API_URL = process.env.VITE_API_URL || 'http://localhost:8000';

// Determine profile
const PROFILE = process.env.E2E_PROFILE || 'default';

// Test timeout varies by profile
const TEST_TIMEOUT_MS = {
  default: 3 * 60 * 1000,      // 3 minutes
  'magic-import': 5 * 60 * 1000, // 5 minutes (LLM processing)
  dataspace: 5 * 60 * 1000,    // 5 minutes (service orchestration)
  plc: 5 * 60 * 1000,          // 5 minutes
}[PROFILE] || 3 * 60 * 1000;

// Determine which test suites to run based on profile
function getTestMatch(): string | string[] {
  switch (PROFILE) {
    case 'magic-import':
      return [
        '**/suite-00-smoke/**/*.spec.ts',
        '**/suite-01-core-editing/**/*.spec.ts',
        '**/suite-02-validation/**/*.spec.ts',
        '**/suite-06-magic-import/**/*.spec.ts',
      ];
    case 'dataspace':
      return [
        '**/suite-00-smoke/**/*.spec.ts',
        '**/suite-09-dataspace/**/*.spec.ts',
      ];
    case 'plc':
      return [
        '**/suite-00-smoke/**/*.spec.ts',
        '**/suite-09-dataspace/**/*.spec.ts',
        '**/suite-10-plc4x-bridge/**/*.spec.ts',
      ];
    default:
      // Default profile runs all non-profile-specific suites
      return [
        '**/suite-00-smoke/**/*.spec.ts',
        '**/suite-01-core-editing/**/*.spec.ts',
        '**/suite-02-validation/**/*.spec.ts',
        '**/suite-03-smart-mapper/**/*.spec.ts',
        '**/suite-04-template-ops/**/*.spec.ts',
        '**/suite-05-semantic-lookup/**/*.spec.ts',
        '**/suite-07-pcf-calculator/**/*.spec.ts',
        '**/suite-08-passport-mode/**/*.spec.ts',
      ];
  }
}

export default defineConfig({
  // Test directory
  testDir: './e2e',

  // Test file pattern
  testMatch: getTestMatch(),

  // Global setup/teardown
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',

  // Timeout configuration
  timeout: TEST_TIMEOUT_MS,
  expect: {
    timeout: 20 * 1000,
  },

  // Fail fast on CI
  forbidOnly: !!process.env.CI,

  // Retry configuration
  retries: process.env.CI ? 2 : 0,

  // Parallel workers
  workers: process.env.CI ? 1 : undefined,

  // Reporter configuration
  reporter: process.env.CI
    ? [
        ['html', { outputFolder: 'playwright-report' }],
        ['json', { outputFile: 'test-results/e2e-results.json' }],
        ['github'],
      ]
    : [
        ['html', { open: 'never' }],
        ['list'],
      ],

  // Shared settings for all projects
  use: {
    // Base URL for the frontend
    baseURL: BASE_URL,

    // Headless mode
    headless: process.env.PW_HEADLESS !== 'false',

    // Viewport
    viewport: { width: 1440, height: 900 },

    // Action timeout
    actionTimeout: 15 * 1000,

    // Navigation timeout
    navigationTimeout: 30 * 1000,

    // Trace collection
    trace: process.env.CI ? 'on-first-retry' : 'retain-on-failure',

    // Screenshot on failure
    screenshot: 'only-on-failure',

    // Video recording
    video: process.env.CI ? 'on-first-retry' : 'retain-on-failure',

    // Extra HTTP headers
    extraHTTPHeaders: {
      'Accept': 'application/json, text/html, */*',
    },
  },

  // Browser projects
  projects: [
    // Chromium (default)
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
      },
    },

    // Firefox
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
      },
    },

    // WebKit
    {
      name: 'webkit',
      use: {
        ...devices['Desktop Safari'],
      },
    },

    // Mobile Chrome
    {
      name: 'mobile-chrome',
      use: {
        ...devices['Pixel 5'],
      },
    },

    // Mobile Safari
    {
      name: 'mobile-safari',
      use: {
        ...devices['iPhone 12'],
      },
    },
  ],

  // Output directory for test artifacts
  outputDir: 'test-results',

  // Web server configuration (optional - use if running tests without pre-started services)
  // Uncomment if you want Playwright to start the dev server automatically
  // webServer: [
  //   {
  //     command: 'npm run dev',
  //     url: BASE_URL,
  //     reuseExistingServer: !process.env.CI,
  //     timeout: 120 * 1000,
  //   },
  // ],
});
