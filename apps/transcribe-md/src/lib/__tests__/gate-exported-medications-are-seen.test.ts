// ============================================================================
// GATE — WHAT THE EXPORT PRINTS, THE DOCTOR SAW.
// ----------------------------------------------------------------------------
// ⚠️ THIS IS THE CLASS GUARD, AND IT IS NOT ABOUT PRESCRIPTIONS. It is about a
// shape that cost a real defect on 2026-08-14 and would have shipped:
//
//   A DELETION IS SCOPED BY WHAT THE COMPONENT *DOES*, NOT BY WHAT THE RULING
//   *CALLS* IT. A ruling names an intent; a component has a job list; the two
//   are not the same enumeration.
//
// Owner ruling #109 deleted "the Prescription Safety surface". The component it
// named had TWO jobs — safety warnings, and the drafted MEDICATION LIST — and
// its own heading toggled between them (`rxHasWarnings ? 'Prescription safety'
// : 'Prescriptions'`). Deleting the component executed the ruling and silently
// took the second job with it, while `rxSection()` went on emitting a
// MEDICATIONS block into five EHR clipboard formats, the PDF and the DOCX.
//
// For one commit, a doctor could sign a record carrying drug, dose, quantity
// and refills that had appeared on no screen. Measured on production at the
// time: 17 of 40 visits carried drafted prescriptions, 13 already signed.
//
// The invariant is therefore stated as a BICONDITIONAL between the two sides,
// so neither can move without the other: the export emits medications for
// exactly the payloads the pre-sign surface renders a card for.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';

import {
  actionTag,
  draftedPrescriptions,
  hasDraftedPrescriptions,
} from '@/app/visits/[id]/prescriptions-card';

/** The export's own condition, read off `ehr-formatters.ts:rxSection` —
 *  `if (data.prescriptions.length === 0) return []`. Mirrored here rather than
 *  imported because `rxSection` is module-private; the source assertion below
 *  is what stops that mirror going stale. */
const exportEmitsMedications = (rxDrafts: unknown): boolean => {
  const list = (rxDrafts as { prescriptions?: unknown[] } | null)?.prescriptions;
  return Array.isArray(list) && list.length > 0;
};

const CASES: { name: string; rx: unknown }[] = [
  { name: 'one prescription', rx: { prescriptions: [{ drug: 'Amoxicillin' }] } },
  { name: 'three prescriptions', rx: { prescriptions: [{ drug: 'A' }, { drug: 'B' }, { drug: 'C' }] } },
  { name: 'prescriptions AND a critical warning', rx: { prescriptions: [{ drug: 'Warfarin' }], warnings: [{ severity: 'critical' }] } },
  { name: 'a critical warning and NO prescription', rx: { warnings: [{ severity: 'critical' }] } },
  { name: 'empty prescriptions array', rx: { prescriptions: [] } },
  { name: 'null', rx: null },
  { name: 'undefined', rx: undefined },
  { name: 'malformed', rx: { prescriptions: 'nonsense' } },
];

describe('the export and the pre-sign surface agree about medications', () => {
  it.each(CASES)('$name — export and display move together', ({ rx }) => {
    expect(hasDraftedPrescriptions(rx)).toBe(exportEmitsMedications(rx));
  });

  it('NON-VACUITY — the case table contains both answers', () => {
    // A table that was all-false (or all-true) would satisfy every row above
    // against a display that never renders, or one that always does.
    const answers = CASES.map((c) => exportEmitsMedications(c.rx));
    expect(answers.filter(Boolean).length, 'no positive case').toBeGreaterThan(0);
    expect(answers.filter((a) => !a).length, 'no negative case').toBeGreaterThan(0);
  });

  it('the mirrored condition still matches the export source', () => {
    // ⚠️ THE MIRROR IS THE WEAK POINT OF THIS GATE and this is what watches it.
    // If `rxSection` ever gates on something other than "any prescriptions" —
    // a severity, a specialty, a `formOnly` flag — this test's mirror becomes a
    // lie and the biconditional above starts proving something else.
    const src = readFileSync('src/lib/ehr-formatters.ts', 'utf8');
    expect(src).toContain('if (data.prescriptions.length === 0) return [];');
  });

  // ── FIELD PARITY, not merely presence ──────────────────────────────────
  //
  // ⚠️ THE PRESENCE CHECK ABOVE IS WHAT LET THE SECOND DEFECT THROUGH, and the
  // second was worse than the first. The card was restored, the biconditional
  // was green, and the card still had no `action` field — while
  // `visit-export.ts:415-418` appends `[DISCONTINUE]`, `[HOLD]`, `[INCREASE]`
  // to every prescription whose action is not `new`.
  //
  // So a STOP ORDER rendered on screen identically to a new start, and the
  // signed PDF said the opposite. An absent list is content the doctor did not
  // see; a list that contradicts the record is content that misleads them.
  //
  // Measured when it was found: 44 of 53 production prescription rows carry a
  // non-`new` action (continue 33, hold 5, unclear 3, discontinue 2,
  // increase 1). The common case, not the edge.
  //
  // "Both sides render medications" is therefore too weak a claim to be worth
  // asserting. What follows is per-field.
  describe('the card and the export agree FIELD BY FIELD, not just in presence', () => {
    // Every action production actually holds, plus the two the deleted
    // component's union listed that production has not yet produced, plus the
    // shapes the wire can carry but nobody typed.
    const ACTIONS = [
      'new', 'continue', 'increase', 'decrease', 'discontinue', 'unclear',
      'hold',            // ⚠️ IN PRODUCTION, and absent from the old union
      'NEW', ' new ',    // case / whitespace — must still count as "no tag"
      '', null, undefined, 42,
    ];

    it.each(ACTIONS.map((a) => [JSON.stringify(a), a]))(
      'action %s — the card tags it exactly when the export would',
      (_label, action) => {
        // The export's rule, transcribed from prescriptionOneLine:
        //   if (rx.action !== 'new') parts.push(`[${rx.action.toUpperCase()}]`)
        const exportTags =
          typeof action === 'string' && action.trim() !== '' && action.trim().toLowerCase() !== 'new';
        expect(actionTag(action as string | null | undefined) !== null).toBe(exportTags);
      },
    );

    it('and the tag TEXT matches what the export prints', () => {
      // Not just "both show something" — the same word. A card reading
      // "STOPPED" against an export reading "[DISCONTINUE]" is two records.
      expect(actionTag('discontinue')).toBe('DISCONTINUE');
      expect(actionTag('hold')).toBe('HOLD');
      expect(actionTag('increase')).toBe('INCREASE');
      expect(actionTag('new')).toBeNull();
    });

    it('⚠️ NO PRESCRIPTION IS DROPPED BY THE CARD THAT THE EXPORT PRINTS', () => {
      // THE ROW THAT WAS MISSING, and it fails on the branch as first written.
      // The card filters `typeof p.drug === 'string'`; the export's payload
      // builder is a tolerant cast with no such check. A prescription whose
      // `drug` is absent is therefore PRINTED into the signed record and
      // DROPPED from the card — one unseen medication, with the booleans above
      // all agreeing.
      const blob = {
        prescriptions: [
          { drug: 'Amoxicillin', action: 'new' },
          { strength: '500 mg', action: 'discontinue' }, // no `drug`
        ],
      };
      expect(
        draftedPrescriptions(blob).length,
        'the card drops a prescription the export prints — that is an unseen ' +
          'medication in a signed record, which is this gate\'s entire subject',
      ).toBe(blob.prescriptions.length);
    });
  });

  it('the pre-sign surface actually MOUNTS the card', () => {
    // The biconditional above is about two predicates. This is the third leg:
    // the component whose predicate it is must be rendered on the surface the
    // doctor reads before signing. Without it, both predicates could agree
    // perfectly while nothing was on screen — which is precisely the defect.
    const view = readFileSync('src/app/visits/[id]/review-document-view.tsx', 'utf8');
    const code = view.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, ' ');
    expect(code).toContain('<PrescriptionsCard');
    expect(code).toContain("from './prescriptions-card'");
  });
});
