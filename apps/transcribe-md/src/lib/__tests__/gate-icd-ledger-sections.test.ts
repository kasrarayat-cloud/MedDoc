// ============================================================================
// THE RECEIPT'S TWO BUCKETS REPRODUCE THE FRAMES EXACTLY
// ----------------------------------------------------------------------------
// The owner's frames group the ledger by clinical category. This gate pins the
// rule against THE FRAMES' OWN NINE CODES, read from the extract that landed in
// docs/design/, so the arm cannot drift from the spec it claims to implement.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { ledgerSections, isHistoryOrScreeningCode } from '@/lib/icd-ledger-sections';

// ⚠️ READ FROM THE LANDED EXTRACT, NOT TRANSCRIBED. A transcription is a second
// copy of the spec and drifts from it silently; canon 91 is about exactly this.
const EXTRACT = readFileSync(
  path.resolve(__dirname, '../../../../../docs/design/t2-figma-raw-extract.txt'),
  'utf8'
);

function framesBuckets(): { diagnoses: string[]; history: string[] } {
  const ready = EXTRACT.split('claim-summary-signed')[0];
  const parts = ready.split(/section-header-(Diagnoses|History & Screening)/);
  const out: Record<string, string[]> = {};
  for (let i = 1; i < parts.length; i += 2) {
    out[parts[i]] = [...parts[i + 1].matchAll(/ledger-row-([A-Z0-9.]+)/g)].map((m) => m[1]);
  }
  return { diagnoses: out['Diagnoses'] ?? [], history: out['History & Screening'] ?? [] };
}

describe('the ledger buckets match the frames', () => {
  it('the extract still contains both sections — the fixture is real', () => {
    // Non-vacuity: if the extract moved or its shape changed, every arm below
    // would compare two empty arrays and pass.
    const { diagnoses, history } = framesBuckets();
    expect(diagnoses.length, 'no Diagnoses rows found in the extract').toBeGreaterThan(0);
    expect(history.length, 'no History & Screening rows found in the extract').toBeGreaterThan(0);
  });

  it('reproduces the frames bucket-for-bucket, in order', () => {
    const { diagnoses, history } = framesBuckets();
    const sections = ledgerSections([...diagnoses, ...history]);
    expect(sections.map((s) => s.label)).toEqual(['Diagnoses', 'History & Screening']);
    expect(sections[0].codes).toEqual(diagnoses);
    expect(sections[1].codes).toEqual(history);
  });

  it('the rule is Z-vs-not, and the frames agree with it nine for nine', () => {
    const { diagnoses, history } = framesBuckets();
    for (const c of history) expect(isHistoryOrScreeningCode(c), `${c} should be history`).toBe(true);
    for (const c of diagnoses) expect(isHistoryOrScreeningCode(c), `${c} should be a diagnosis`).toBe(false);
  });

  it('ORDER IS PRESERVED, never sorted', () => {
    // The suggester's order carries meaning — the primary diagnosis leads. A
    // display that re-sorted would silently re-rank a claim.
    const s = ledgerSections(['R63.4', 'I10', 'K21.9']);
    expect(s[0].codes).toEqual(['R63.4', 'I10', 'K21.9']);
  });

  it('an EMPTY bucket is omitted, never rendered as a heading over nothing', () => {
    // The frames only ever show both populated. A heading over nothing tells a
    // doctor a category was considered and found empty — a claim the frame
    // never makes.
    expect(ledgerSections(['I10', 'K21.9']).map((x) => x.id)).toEqual(['diagnoses']);
    expect(ledgerSections(['Z12.11']).map((x) => x.id)).toEqual(['history-screening']);
    expect(ledgerSections([])).toEqual([]);
  });

  it('classification uses the SAME matcher the decisions substrate keys on', () => {
    // One identifier, one matcher. A lower-cased or padded code must land in the
    // same bucket as its canonical form, or a card renders under a heading its
    // decision record does not share.
    expect(isHistoryOrScreeningCode(' z12.11 ')).toBe(true);
    expect(isHistoryOrScreeningCode('z12.11')).toBe(true);
    expect(isHistoryOrScreeningCode('i10')).toBe(false);
  });
});

// ============================================================================
// ⚠️ THE SECTION ORDER FOLLOWS THE PRIMARY DIAGNOSIS — a pass finding.
// ----------------------------------------------------------------------------
// A FIXED section order re-ranks the claim, which this file's header forbids in
// bold. The counterexample is the product's commonest encounter.
// ============================================================================

describe('the section order follows the suggester, not a constant', () => {
  it('⚠️ a SCREENING COLONOSCOPY keeps its Z code first', () => {
    const out = ledgerSections(['Z12.11', 'D12.5', 'K64.8']);
    expect(out.map((s) => s.id)).toEqual(['history-screening', 'diagnoses']);
    expect(out.flatMap((s) => s.codes)).toEqual(['Z12.11', 'D12.5', 'K64.8']);
  });

  it('a diagnosis-led visit still puts Diagnoses first', () => {
    const out = ledgerSections(['K21.00', 'Z79.01']);
    expect(out.map((s) => s.id)).toEqual(['diagnoses', 'history-screening']);
    expect(out.flatMap((s) => s.codes)).toEqual(['K21.00', 'Z79.01']);
  });

  it('⚠️ the suggester’s ORDER survives the round trip whichever section leads', () => {
    // The property the header actually states: the first code the suggester
    // emitted is the first code the doctor reads.
    for (const order of [
      ['Z12.11', 'D12.5', 'K64.8'],
      ['K21.00', 'Z79.01', 'E11.9'],
      ['Z00.00'],
      ['K21.00'],
    ]) {
      expect(ledgerSections(order)[0]?.codes[0], `first code changed for ${order.join()}`).toBe(order[0]);
    }
  });
});
