// ============================================================================
// Structural guard — every /api/admin/* route MUST wrap its handler with the
// SUPER_ADMIN gate (adminApi from src/lib/admin-api-gate.ts)
// ----------------------------------------------------------------------------
// 🔴 SECURITY-CRITICAL. The runtime privilege-boundary E2E (scenario 26) probes
// a representative SPREAD of admin endpoints — it can't catch a NEW admin route
// that ships without the gate. This static check closes that gap: it fails CI
// the moment any admin route handler is exported without going through
// `adminApi(...)` (the server-side product re-check that 404-cloaks non-
// SUPER_ADMIN callers). Same UI-vs-server enforcement class as the logout +
// Rx-sign-gate bugs — make "every endpoint is gated" an invariant, not a
// convention someone can forget.
// ============================================================================

import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// tests/api/ -> apps/transcribe-md/src/app/api/admin
const ADMIN_API_DIR = path.resolve(HERE, '../../src/app/api/admin');
const CADDYFILE = path.resolve(HERE, '../../../../Caddyfile');

const ALTERNATE_MACHINE_GATE_CONTRACTS = new Map<string, readonly string[]>([
  [
    'template-twin/control-health/route.ts',
    [
      'export async function GET()',
      'templateTwinReleaseControlProcessEnabled()',
      'releaseControlDatabase.$queryRawUnsafe("SELECT 1")',
    ],
  ],
  [
    'template-twin/release-metrics/route.ts',
    [
      'export async function POST(request: NextRequest)',
      'templateTwinReleaseControlProcessEnabled()',
      'isAdminHost(request)',
      'recordTemplateTwinReleaseMetricSnapshot({',
      'attestation: z',
    ],
  ],
]);

function adminRouteFiles(): string[] {
  return readdirSync(ADMIN_API_DIR, { recursive: true, encoding: 'utf8' })
    .filter((rel) => rel.replace(/\\/g, '/').endsWith('route.ts'))
    .map((rel) => path.join(ADMIN_API_DIR, rel))
    .sort();
}

describe('admin API gate coverage (server-side authority enforcement)', () => {
  const files = adminRouteFiles();

  it('discovers the admin route handlers', () => {
    // Sanity floor: if this drops to ~0 the glob broke and the per-file
    // assertions below would vacuously pass.
    expect(files.length).toBeGreaterThanOrEqual(20);
  });

  it.each(files)(
    'gates its handler with an approved server-side contract: %s',
    (file) => {
      const src = readFileSync(file, 'utf8');
      const rel = path.relative(ADMIN_API_DIR, file).replace(/\\/gu, '/');
      const alternateContract = ALTERNATE_MACHINE_GATE_CONTRACTS.get(rel);
      if (alternateContract) {
        for (const requiredSource of alternateContract) {
          expect(
            src.includes(requiredSource),
            `/api/admin/${rel} no longer satisfies its exact machine-only gate contract: ${requiredSource}`,
          ).toBe(true);
        }
        return;
      }
      expect(
        src.includes('adminApi('),
        `/api/admin/${rel} exports an admin handler without the adminApi() gate — ` +
          `a non-SUPER_ADMIN could reach it. Wrap the handler: export const GET = adminApi('key', async (req, ctx) => {...}).`,
      ).toBe(true);
    },
  );

  it('keeps the unauthenticated control-process health check off the public Caddy route matcher', () => {
    const caddy = readFileSync(CADDYFILE, 'utf8');
    const publicControlMatcher = caddy
      .split(/\r?\n/gu)
      .find((line) => line.includes('@templateTwinControlApi path'));
    expect(publicControlMatcher).toBeDefined();
    expect(publicControlMatcher).not.toContain(
      '/api/admin/template-twin/control-health',
    );
  });
});
