import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  // Resolve `@/*` the same way the tsconfig paths map does, so unit
  // tests can import worker layers without workspace gymnastics.
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    // Exclude the .next/ build output + node_modules so vitest only
    // picks up our real tests. Also exclude Playwright's tests/e2e/
    // tree — those use @playwright/test hooks (test.afterEach, etc.)
    // which conflict with vitest's globals.
    exclude: [
      '**/node_modules/**',
      '**/.next/**',
      '**/dist/**',
      '**/tests/e2e/**',
    ],
  },
});
