// ============================================================================
// THE E2E TWIN-SEED PIN IS BOUND TO THE COMPILER, AND THIS ARM SAYS SO IN THE
// FAST SUITE.
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS EXISTS. `tests/e2e/fixtures/twin-certified-pins.json` carries a
// `templateSha256` that MUST equal `compileTemplateDocx(sample-form.docx)
// .structureSha256`. `seed-certified-twin.ts:152` refuses to seed when they
// diverge, and it is right to: `synthetic-test.ts` only reuses a pinned note
// when the hashes match, so a moved compiler would make the pin be SILENTLY
// IGNORED and certification would reach for a LIVE MODEL in CI.
//
// ⚠️ IT REFUSED FOR REAL ON 2026-08-24. F24-S5's compiler change — stripping
// Word's "Choose an item." placeholder from `allowedOptions` — moved the
// structure hash, and the E2E seed failed **ten minutes into the `e2e` job**
// with the whole pack behind it. The coupling is real and was invisible to
// every unit arm on the branch: the compiler's OUTPUT is an INPUT to a pinned
// fixture, and nothing in the fast suite watched that edge.
//
// This arm moves that failure from minute ten of `e2e` to two seconds of `CI`,
// and names the remedy in its own message. It is not a substitute for the seed's
// own refusal — that one is fail-closed at the point the live-model call would
// happen, and stays.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { compileTemplateDocx } from '@/lib/note-template-docx';

const FIXTURE_DOCX = path.resolve(
  process.cwd(),
  'tests/e2e/fixtures/sample-form.docx',
);
const PINS = path.resolve(
  process.cwd(),
  'tests/e2e/fixtures/twin-certified-pins.json',
);

describe('the certified-twin pin tracks the compiler', () => {
  it('⚠️ templateSha256 EQUALS the compiler’s structure hash for the seeded form', () => {
    const pins = JSON.parse(readFileSync(PINS, 'utf8')) as {
      templateSha256: string;
      sourceDocxSha256: string;
    };
    const bytes = new Uint8Array(readFileSync(FIXTURE_DOCX));
    const ir = compileTemplateDocx(bytes);

    // NON-VACUITY: a form that compiled to nothing would satisfy a hash compare
    // between two empty things without anyone noticing.
    expect(ir.fields.length).toBeGreaterThan(0);
    expect(pins.templateSha256).toMatch(/^[a-f0-9]{64}$/);

    expect(
      ir.structureSha256,
      'THE PIN AND THE COMPILER HAVE DIVERGED. `seed-certified-twin.ts` will ' +
        'refuse and the e2e pack will fail. Any change to the compiler’s IR ' +
        'shape moves this hash. Re-mint `templateSha256` in ' +
        'tests/e2e/fixtures/twin-certified-pins.json to the value reported as ' +
        '"received" here — and re-mint ONLY that field unless the note itself ' +
        'is genuinely stale, because the pinned note and entities are bound to ' +
        'the ENCOUNTER, not to the template structure.',
    ).toBe(pins.templateSha256);
  });

  it('the pinned source document is the one this arm compiled', () => {
    // Guards the other half: if somebody swaps the fixture docx, the hash above
    // moves for a reason this arm would otherwise attribute to the compiler.
    const pins = JSON.parse(readFileSync(PINS, 'utf8')) as { sourceDocxSha256: string };
    const bytes = readFileSync(FIXTURE_DOCX);
    const sha = require('node:crypto')
      .createHash('sha256')
      .update(bytes)
      .digest('hex');
    expect(sha).toBe(pins.sourceDocxSha256);
  });
});
