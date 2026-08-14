// ============================================================================
// L4 WRITES REVIEW STATE ADDITIVELY — a safety warning is never deleted by a
// formatting banner.
// ----------------------------------------------------------------------------
// ⚠️ THE SILENTLY-DESTROYED-SIGNAL CLASS, found by an adversarial pass.
// `04-generate-soap.ts` wrote `reviewReason` inside a plain
// `prisma.transcribeVisit.update` — a REPLACE. Two reasons are set BEFORE L4:
//
//   · worker.ts — "Conflicting allergy statements were detected in this visit
//     — verify the allergy list before signing." Written with a COALESCE
//     **specifically so it could not be clobbered.** The plain update clobbered
//     it anyway.
//   · detectTemplateFallback — "Your note format could not be loaded…".
//     Destroying it makes the new banner's own "Your template …" and its
//     Settings link a dead end.
//
// PRE-EXISTING: L4 has always replaced here, and the item-3 change only altered
// the string. The cure is migration to the pattern L6 was already moved to
// (#315 obs#1) — never a second implementation, because two copies drift the
// day either is fixed.
//
// ⚠️ ASSERTED THROUGH THE SQL THE HELPER ACTUALLY EMITS, not through a mock of
// it. Mocking `applyAdditiveReviewState` would prove L4 CALLS something named
// additive; it would not prove the row survives.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';

const L4 = readFileSync('src/worker/layers/04-generate-soap.ts', 'utf8');
const CODE = L4.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, ' ');

describe('L4 no longer REPLACES review state', () => {
  it('NON-VACUITY — the stripper left the layer behind', () => {
    expect(CODE).toContain('prisma.transcribeVisit.update');
  });

  it('every reviewReason L4 writes goes through applyAdditiveReviewState', () => {
    // Each `reviewReason:` must sit inside an `applyAdditiveReviewState({…})`
    // call, never inside a `prisma…update({ data: {…} })`.
    const occurrences = [...CODE.matchAll(/reviewReason\s*:/g)].map((m) => m.index!);
    expect(occurrences.length, 'no reviewReason writes found — this test is measuring nothing')
      .toBeGreaterThan(0);
    for (const at of occurrences) {
      const before = CODE.slice(Math.max(0, at - 600), at);
      const lastAdditive = before.lastIndexOf('applyAdditiveReviewState');
      const lastUpdate = before.lastIndexOf('transcribeVisit.update');
      expect(
        lastAdditive,
        `a reviewReason at offset ${at} is not inside applyAdditiveReviewState — ` +
          'a plain update REPLACES, and would delete the allergy-conflict warning',
      ).toBeGreaterThan(lastUpdate);
    }
  });

  it('the data-write no longer carries needsReview or reviewReason', () => {
    // The `update` keeps soapDraft/provenance; review state left it entirely.
    const updates = [...CODE.matchAll(/transcribeVisit\.update\(\{[\s\S]{0,700}?\}\);/g)];
    expect(updates.length, 'no update blocks found').toBeGreaterThan(0);
    for (const u of updates) {
      expect(u[0]).not.toMatch(/reviewReason\s*:/);
      expect(u[0]).not.toMatch(/needsReview\s*:/);
    }
  });

  it('it uses the SAME helper as L6 — not a second implementation', () => {
    expect(CODE).toContain("from '@/worker/finalize-review-state'");
    const l6 = readFileSync('src/worker/layers/06-polish.ts', 'utf8');
    expect(l6).toContain("from '@/worker/finalize-review-state'");
  });
});

describe('the helper it now uses is genuinely additive', () => {
  const HELPER = readFileSync('src/worker/finalize-review-state.ts', 'utf8');

  it('needsReview can only be turned ON', () => {
    expect(HELPER).toMatch(/"needsReview"\s*=\s*"needsReview"\s*OR/);
  });

  it('reviewReason CONCATENATES, existing first', () => {
    // Existing first is deliberate: it was set earlier in the pipeline and is
    // usually the more safety-relevant of the two.
    expect(HELPER).toMatch(/"reviewReason"\s*\|\|\s*' '\s*\|\|/);
    // NULL-safe: `a || NULL` is NULL in Postgres, so COALESCE must walk.
    expect(HELPER).toMatch(/COALESCE\(/);
  });

  it('it is SQL-side — atomic, no read-modify-write race', () => {
    expect(HELPER).toContain('$executeRaw');
  });
});
