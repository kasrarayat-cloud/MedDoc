// ============================================================================
// tests/automated/e2e — Playwright config (prod-targeting regression suite)
// ----------------------------------------------------------------------------
// Different from apps/transcribe-md/playwright.config.ts:
//   - apps/transcribe-md/ runs against a local MOCK_AI_CALLS=true stack.
//   - this config runs against LIVE production URLs by default. Tests
//     that mutate state are gated on E2E_READ_ONLY=false so a default run
//     against prod can't create garbage accounts / visits / files.
//
// Credentials + target URLs come from tests/automated/.env.test (see
// .env.test.example). Missing creds cause individual tests to skip —
// never hard-fail — so `npx playwright test` still produces a clean
// report during bootstrap.
// ============================================================================

import { defineConfig, devices } from '@playwright/test';
import * as path from 'node:path';
import * as dotenv from 'dotenv';

// `quiet: true` suppresses the dotenv maintainer's self-promotional
// "tip: ⌁ auth for agents [www.vestauth.com]" line (introduced in
// dotenv@17). Without this it leaks into the playwright reporter and
// makes log diffs noisier.
dotenv.config({ path: path.resolve(__dirname, '../.env.test'), quiet: true });

const APP_URL = process.env.TEST_APP_URL ?? 'https://app.quillmd.com';

export default defineConfig({
  testDir: __dirname,
  testMatch: '**/*.spec.ts',

  // Prod tests do network round-trips + occasional worker waits. Keep
  // sequential so a rate-limit spec doesn't trip the next test.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,

  // 3 min total, 10s per expect — generous enough for a real worker
  // pass-through but short enough that a hung API doesn't stall the
  // nightly run past its window.
  timeout: 180_000,
  expect: { timeout: 10_000 },

  reporter: [
    ['list'],
    [
      'json',
      {
        outputFile: path.resolve(__dirname, '../reports/playwright-latest.json'),
      },
    ],
    [
      'html',
      {
        outputFolder: path.resolve(__dirname, '../reports/playwright-html'),
        open: 'never',
      },
    ],
  ],

  use: {
    baseURL: APP_URL,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 20_000,
    // Prod uses a real cert; no --ignore-https-errors needed.
  },

  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // iPhone 13 would be ideal, but its device descriptor ships WebKit
      // which needs an extra `playwright install webkit` (~60 MB) that
      // blows up cold-start on the VPS. Chromium-based Pixel 5 matches
      // the same 393×851 viewport closely enough for layout checks.
      name: 'mobile',
      use: { ...devices['Pixel 5'] },
      testMatch: /mobile.*\.spec\.ts$/,
    },
  ],
});
