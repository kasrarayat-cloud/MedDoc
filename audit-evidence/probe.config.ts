// Dedicated Playwright config for the audit probe. Reuses Chromium
// install from apps/transcribe-md. No retries — we WANT to see flakes
// as-is; flakes are bugs.

import { defineConfig, devices } from '@playwright/test';
import * as path from 'node:path';

export default defineConfig({
  testDir: __dirname,
  testMatch: 'dynamic-probe.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [
    ['list'],
    [
      'json',
      {
        outputFile: path.resolve(__dirname, 'test-results-raw.json'),
      },
    ],
  ],
  use: {
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
