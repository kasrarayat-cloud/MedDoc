// Dedicated Playwright config for the authed audit probe.
import { defineConfig, devices } from '@playwright/test';
import * as path from 'node:path';
import * as dotenv from 'dotenv';

dotenv.config({
  path: path.resolve(__dirname, '../../tests/automated/.env.test'),
  quiet: true,
});

export default defineConfig({
  testDir: __dirname,
  testMatch: /probe-.*\.ts$/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 10_000 },
  reporter: [
    ['list'],
    ['json', { outputFile: path.resolve(__dirname, 'authed-results.json') }],
  ],
  use: {
    screenshot: 'on',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
