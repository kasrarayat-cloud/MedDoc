// ============================================================================
// /api/client-errors PHI scrub posture (Security Audit P1-G, 2026-05-13)
// ----------------------------------------------------------------------------
// Pre-fix, the route logged `message`, `digest`, and `url` raw; only
// `stack` was passed through redactPhi. The fix applies redactPhi to
// message + digest, strips the query portion of url. Source-pin
// guards against regression.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const SRC = readFileSync(
  resolve(
    __dirname,
    '..',
    '..',
    'src',
    'app',
    'api',
    'client-errors',
    'route.ts',
  ),
  'utf-8',
);

describe('client-errors route — PHI hygiene (P1-G)', () => {
  it('imports redactPhi from @meddoc/ai (helper available)', () => {
    expect(SRC).toMatch(
      /import\s+\{\s*redactPhi\s*\}\s+from\s+['"]@meddoc\/ai['"]/,
    );
  });

  it('wraps message in redactPhi', () => {
    expect(SRC).toMatch(/message:\s*d\.message\s*\?\s*redactPhi\(d\.message\)/);
  });

  it('wraps digest in redactPhi', () => {
    expect(SRC).toMatch(/digest:\s*d\.digest\s*\?\s*redactPhi\(d\.digest\)/);
  });

  it('strips the query portion of url before logging', () => {
    // The fix derives `safeUrl` by slicing at the first `?`. Match
    // both the assignment AND the use in the JSON.stringify call.
    expect(SRC).toMatch(/const\s+safeUrl\s*=\s*[\s\S]{0,200}?indexOf\('\?'\)/);
    expect(SRC).toMatch(/url:\s*safeUrl/);
  });

  it('still passes stack through redactPhi (regression guard on pre-existing fix)', () => {
    expect(SRC).toMatch(/redactPhi\(d\.stack\)/);
  });
});
