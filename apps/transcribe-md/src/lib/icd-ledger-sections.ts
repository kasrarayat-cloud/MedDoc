// ============================================================================
// icd-ledger-sections — the Receipt's two section buckets
// ----------------------------------------------------------------------------
// The owner's frames (`claim-summary-ready` / `claim-summary-signed`, file
// vDPGIxwPmm08BTzBD99vfQ, extracted at docs/design/t2-figma-raw-extract.txt)
// group the ledger by CLINICAL CATEGORY, where the surface it replaces grouped
// by DECISION STATE:
//
//     DIAGNOSES              K21.9  I10  R10.13  R63.4  K29.70  M25.561
//     HISTORY & SCREENING    Z87.891  Z12.11  Z79.01
//
// ⚠️ THE RULE IS DERIVED, AND IT IS DERIVED FROM A STANDARD RATHER THAN FROM
// THE NINE EXAMPLES. Every code in the second bucket begins with Z and no code
// in the first does — nine for nine — but a rule fitted to nine points would be
// a guess. The reason to believe it is external: ICD-10-CM **chapter 21**, codes
// Z00–Z99, is *"Factors influencing health status and contact with health
// services"*, which is exactly what the frame's own label names. The frames and
// the standard agree, and that agreement is the evidence.
//
// ⚠️ AND THE CODEBASE HAS NO CHAPTER CLASSIFIER TO REUSE — measured: no
// `chapter`, `category` or equivalent concept exists for ICD anywhere in
// `apps/transcribe-md/src` or `packages/*/src`; the allowlist reasons about
// BILLABLE-vs-HEADER, which is a different axis entirely. So this file is the
// first place the product makes this distinction, which is why it is one named
// function with its rule stated rather than an inline `startsWith('Z')` at a
// render site.
//
// ⚠️ WHAT THE FRAMES DO NOT SETTLE, AND WHICH IS THEREFORE CONSERVATIVE HERE:
// they only ever show BOTH buckets populated. An empty bucket renders NO header
// (a heading over nothing tells a doctor a category was considered and found
// empty, which the frame never claims), and the ordering is fixed rather than
// data-driven. Both are on the owner's list.
// ============================================================================

import { normalizeIcdCode } from '@/lib/icd-decisions';

export type LedgerSectionId = 'diagnoses' | 'history-screening';

export interface LedgerSection {
  id: LedgerSectionId;
  /** The frame's own label text, verbatim. Rendered uppercase by CSS, not here —
   *  the DOM keeps the readable form for assistive technology. */
  label: string;
  codes: string[];
}

/** ICD-10-CM chapter 21 — "Factors influencing health status and contact with
 *  health services". The frames call this bucket "History & Screening". */
export function isHistoryOrScreeningCode(code: string): boolean {
  const c = normalizeIcdCode(code);
  return c.startsWith('Z');
}

/**
 * Split codes into the frames' two buckets, preserving the caller's order
 * within each.
 *
 * ⚠️ ORDER IS PRESERVED, NEVER SORTED. The suggester emits codes in an order
 * that carries meaning — the primary diagnosis leads — and a display that
 * re-sorts them alphabetically would silently re-rank a claim.
 *
 * A bucket with no codes is OMITTED rather than emitted empty.
 */
export function ledgerSections(codes: readonly string[]): LedgerSection[] {
  const diagnoses: string[] = [];
  const history: string[] = [];
  for (const code of codes) {
    (isHistoryOrScreeningCode(code) ? history : diagnoses).push(code);
  }
  const out: LedgerSection[] = [];
  if (diagnoses.length) out.push({ id: 'diagnoses', label: 'Diagnoses', codes: diagnoses });
  if (history.length) {
    out.push({ id: 'history-screening', label: 'History & Screening', codes: history });
  }
  return out;
}
