// ============================================================================
// The RENDERED tier — tests that need the REAL Gotenberg/LibreOffice sidecar.
// ----------------------------------------------------------------------------
// Everything under `src/**/__rendered__/` converts a real DOCX through the real
// converter and reads the resulting PDF. That is a different dependency from the
// rest of the unit suite, so it gets its own config and its own invocation:
//
//     npm run test:rendered   (with GOTENBERG_URL pointing at the sidecar)
//
// ⚠️ IT IS EXCLUDED FROM `vitest.config.ts` ON PURPOSE, AND THE EXCLUSION IS THE
// RISK. The default suite runs in the `CI` workflow, which has no sidecar — so
// these files would fail there for an environmental reason and teach everyone to
// ignore them. Excluding them fixes that and creates a worse failure mode: a
// gate nobody runs. `gate-rendered-tier-is-invoked.test.ts` closes that loop by
// asserting, from inside the default suite, that the e2e workflow still invokes
// this config. Delete the CI step and that guard goes red.
// ============================================================================
import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  // ⚠️ OFF THE WORKING TREE. This tier runs in a container that bind-mounts the
  // repo READ-ONLY (see docker-compose.qa.rendered.yml), so vitest's default
  // `node_modules/.vite` is not writable — and must not become writable, since
  // anything written there lands in the deploy surface owned by a container uid.
  cacheDir: '/tmp/vitest-rendered',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    // No jsdom: these tests build bytes and speak HTTP. Nothing renders a
    // component, and the node environment is what `fetch`/`FormData`/`Blob`
    // behave correctly in.
    environment: 'node',
    globals: true,
    include: [path.resolve(__dirname, 'src/**/__rendered__/**/*.{test,spec}.?(c|m)[jt]s?(x)')],
    exclude: ['**/node_modules/**', '**/.next/**', '**/dist/**'],
    // LibreOffice cold-starts on the first conversion and each arm converts a
    // multi-page document. The per-test timeouts are set in the file; this is
    // the outer bound for the whole file.
    testTimeout: 120_000,
    hookTimeout: 60_000,
    // ⚠️ SERIAL. The sidecar is capped at 1.5 CPU / 1 GB and strictly
    // serialises conversions; four in parallel turn a 5-second suite into four
    // competing 60-second timeouts and read as a converter fault.
    fileParallelism: false,
  },
});
