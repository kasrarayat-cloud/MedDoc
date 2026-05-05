import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  resolve: {
    // The monorepo hoists @testing-library/react + its react/react-dom
    // peers to the root /opt/meddoc-pro/node_modules (react@19.2.5)
    // while the app-local install sits at apps/transcribe-md/node_modules
    // (react@19.2.4). Two copies in one process = "useState is null"
    // hook dispatcher mismatch when a component from one tree mounts
    // inside the other's renderer.
    //
    // Fix: alias every react / react-dom / jsx-runtime entry point to
    // the ROOT copy (the one RTL already resolves), so the component-
    // under-test uses the same instance as the test harness. Dedupe
    // alone isn't enough because the hoisted @testing-library resolves
    // its peer dep BEFORE vitest's own dedupe runs.
    dedupe: ['react', 'react-dom'],
    alias: {
      '@': path.resolve(__dirname, './src'),
      react: path.resolve(__dirname, '../../node_modules/react'),
      'react-dom': path.resolve(__dirname, '../../node_modules/react-dom'),
      'react/jsx-runtime': path.resolve(
        __dirname,
        '../../node_modules/react/jsx-runtime.js'
      ),
      'react/jsx-dev-runtime': path.resolve(
        __dirname,
        '../../node_modules/react/jsx-dev-runtime.js'
      ),
      'react-dom/client': path.resolve(
        __dirname,
        '../../node_modules/react-dom/client.js'
      ),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    // Default `include` is `**/*.{test,spec}.?(c|m)[jt]s?(x)` relative
    // to root — i.e. only files inside apps/transcribe-md. The
    // @meddoc/ai package has no vitest of its own (no build step,
    // either), so its tests live under packages/ai/src/__tests__/ and
    // are folded into this config so they run alongside the worker
    // tests they guard. Path is absolute so the resolution doesn't
    // depend on cwd when CI invokes vitest.
    include: [
      '**/*.{test,spec}.?(c|m)[jt]s?(x)',
      path.resolve(__dirname, '../../packages/ai/src/**/*.test.ts'),
    ],
    exclude: [
      '**/node_modules/**',
      '**/.next/**',
      '**/dist/**',
      '**/tests/e2e/**',
    ],
  },
});
