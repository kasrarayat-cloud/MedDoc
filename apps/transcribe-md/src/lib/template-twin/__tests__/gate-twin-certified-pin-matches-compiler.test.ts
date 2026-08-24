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
//
// ============================================================================
// ⚠️ AND ITS ADVICE WAS HALF THE ANSWER — THE HALF THAT COST NOTHING.
// ----------------------------------------------------------------------------
// This arm DID fire on `f340c589`, exactly as designed. It was answered by
// re-minting `templateSha256`, which is correct FOR THE SEEDER and completely
// silent on the larger consequence:
//
//   > **`structureSha256` is not only a fixture pin. `renderer.ts:
//   > assertSourceMatchesIr` re-compiles the immutable source on EVERY fill and
//   > compares it against the STORED IR of every template already compiled. A
//   > moved structure hash does not just stale a pin — it ORPHANS EVERY
//   > CERTIFIED TWIN IN THE DATABASE.**
//
// Measured on QA by driving the real fill (F24-S5 ITEM A): 10 of 10 CERTIFIED
// twins began failing `SOURCE_IR_MISMATCH`, and production's only certified twin
// carries the identical shape. Every recompute path then degrades SILENTLY to
// the styled export, and a signature freezes a NULL pointer — permanently.
//
// So the message below now asks the SECOND question too. A detector whose
// remedy is "update the expected value" cannot, on its own, protect an
// invariant about artifacts that already exist — and re-minting a pin is
// exactly the kind of change that feels like housekeeping.
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
      'THE PIN AND THE COMPILER HAVE DIVERGED. Any change to the compiler’s IR ' +
        'shape moves this hash.\n\n' +
        '⚠️ ASK THE SECOND QUESTION BEFORE RE-MINTING ANYTHING. This hash is ' +
        'also what `renderer.ts:assertSourceMatchesIr` compares on EVERY fill, ' +
        'against the STORED IR of every template ALREADY COMPILED. If your ' +
        'change moved it, you have not staled a fixture — you have made every ' +
        'CERTIFIED TWIN IN THE DATABASE unfillable, production’s included, and ' +
        'every recompute path degrades SILENTLY to the styled export while a ' +
        'signature freezes a NULL pointer forever. Measured on QA 2026-08-24: ' +
        '10 of 10. So: is the compiler change one that may move persisted IR ' +
        'at all? If it is only about what a READER shows, filter at the reader ' +
        'and leave the stored array alone (see compiler.ts, F24-S5 ITEM A).\n\n' +
        'ONLY IF the shape change is genuinely intended: `seed-certified-twin.ts` ' +
        'will refuse and the e2e pack will fail until you re-mint ' +
        '`templateSha256` in tests/e2e/fixtures/twin-certified-pins.json to the ' +
        'value reported as "received" here — and re-mint ONLY that field unless ' +
        'the note itself is genuinely stale, because the pinned note and ' +
        'entities are bound to the ENCOUNTER, not to the template structure. ' +
        'And every existing compiled version needs a recompile plan.',
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
