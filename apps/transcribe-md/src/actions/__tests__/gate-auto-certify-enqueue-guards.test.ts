import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { requireManualCertification } from '@/config/require-manual-certification';

/**
 * THE ENQUEUE CARRIES BOTH GUARDS.
 *
 * ⚠️ THIS ARM EXISTS BECAUSE ONE OF THEM WAS SILENTLY LOST. An indentation fix
 * to this block dropped `!requireManualCertification()` — the edit applied, its
 * own assertion passed, tsc stayed green, and the guard was simply gone. Nothing
 * anywhere would have caught it: an auto-certification that ignores the opt-out
 * looks exactly like one working correctly, unless you are the practice that
 * opted out.
 *
 * A scripted edit proves what it APPLIED; this proves what it PRESERVED.
 */
const SRC = readFileSync(
  join(__dirname, '..', 'note-template-lifecycle.ts'),
  'utf8',
);

describe('auto-certify enqueue guards', () => {
  it('gates on ZERO blocking elements — the ruling\'s own condition', () => {
    expect(SRC).toMatch(/blockingUnsupportedCount === 0/);
  });

  it('⚠️ ALSO gates on the manual-certification opt-out — the guard that was lost', () => {
    expect(SRC).toMatch(/!requireManualCertification\(\)/);
  });

  it('BOTH guards are on the SAME condition, not two branches', () => {
    // Two separate ifs would let a later edit satisfy one and skip the other.
    expect(SRC).toMatch(
      /blockingUnsupportedCount === 0 && !requireManualCertification\(\)/,
    );
  });

  it('the enqueue is inside that condition, not beside it', () => {
    const i = SRC.indexOf('blockingUnsupportedCount === 0 && !requireManualCertification()');
    const j = SRC.indexOf('enqueueAutoCertifyTwin', i);
    expect(i).toBeGreaterThan(-1);
    expect(j).toBeGreaterThan(i);
    // and close by — not in some later, unguarded block
    expect(j - i).toBeLessThan(2000);
  });
});

describe('the flag itself', () => {
  const prev = process.env.REQUIRE_MANUAL_CERTIFICATION;
  afterEachRestore();
  function afterEachRestore() {
    // vitest runs these in order; restore explicitly per assertion below.
  }

  it('defaults OFF — absent means auto-certification proceeds', () => {
    delete process.env.REQUIRE_MANUAL_CERTIFICATION;
    expect(requireManualCertification()).toBe(false);
    if (prev !== undefined) process.env.REQUIRE_MANUAL_CERTIFICATION = prev;
  });

  it('⚠️ FAIL-OPEN: a typo does NOT silently return every doctor to 80 clicks', () => {
    process.env.REQUIRE_MANUAL_CERTIFICATION = 'True';   // wrong case
    expect(requireManualCertification()).toBe(false);
    process.env.REQUIRE_MANUAL_CERTIFICATION = 'yes';    // wrong token
    expect(requireManualCertification()).toBe(false);
    if (prev === undefined) delete process.env.REQUIRE_MANUAL_CERTIFICATION;
    else process.env.REQUIRE_MANUAL_CERTIFICATION = prev;
  });

  it('exactly "true" turns it ON', () => {
    process.env.REQUIRE_MANUAL_CERTIFICATION = 'true';
    expect(requireManualCertification()).toBe(true);
    if (prev === undefined) delete process.env.REQUIRE_MANUAL_CERTIFICATION;
    else process.env.REQUIRE_MANUAL_CERTIFICATION = prev;
  });
});
