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
    // picks up our real tests.
    exclude: ['**/node_modules/**', '**/.next/**', '**/dist/**'],
  },
});
