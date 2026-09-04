// ============================================================================
// ICD-10-CM validation — the deterministic floor under the AI codes layer
// ----------------------------------------------------------------------------
// T8, 2026-09-04. This file is now an API over the COMPLETE official CMS
// ICD-10-CM FY2026 release. It used to BE the data.
//
// ── THE EPITAPH ─────────────────────────────────────────────────────────────
//
// What stood here was a hand-curated list, and it said so itself. Verbatim,
// from the header this replaces:
//
//   > "SCOPE LIMITATION (intentional for pre-pilot)
//   >  This is a STARTER SET — ~120 of the most-common ICD-10-CM codes
//   >  covering pilot specialties (family medicine, internal medicine,
//   >  pediatrics, OB/GYN, orthopedics, cardiology, psychiatry, pain
//   >  management). It does NOT replace the full CMS list (~70 000 codes)."
//
//   > "PHASE 7 PATH (post-pilot): swap this file for a fs-loaded subset of
//   >  the full CMS canonical list (icd10cm_codes_2026.txt, ~1.4 MB). Same
//   >  validator API; the call sites don't change."
//
// This is that swap. The API is unchanged and no call site moved.
//
// ⚠️ THE DISCLAIMER OUTLIVED ITS OWN ACCURACY, WHICH IS THE FIRST FINDING.
// It said "~120". The list it described had grown to **604** across SEVEN
// later commits, and nobody updated the sentence. (Measured by replaying the
// array length at each commit that touched the file: 119 at creation, then
// 152, 195, 418, 562, 566, 599, 604. An earlier draft of this paragraph said
// "five", which was itself an unchecked number in the paragraph diagnosing
// unchecked numbers — corrected by the adversarial pass.) AGENTS.md, "AN
// EXEMPTION'S REASON IS PROSE, AND PROSE DECAYS SILENTLY" — the number a
// reader would have quoted was wrong by 5x, and the file still read as
// authoritative. Ruling #149(e) and `icd-drops.ts` both cite this header;
// both quote the "~70 000" clause, which was right, and neither noticed the
// "~120", which was not.
//
// ── WHAT THE STARTER SET ACTUALLY CONTAINED, MEASURED AGAINST CMS ──────────
//
// All 604 were partitioned against the official FY2026 release. The partition
// reconciles to 604, so there is no unnamed bucket:
//
//   566  BILLABLE — real, valid-for-submission codes            (kept, and
//                   pinned as a no-regression fixture in the gate test)
//    32  HEADER   — real ICD-10-CM entries that are NOT valid for submission
//     6  ABSENT   — not ICD-10-CM codes at all, in any form
//
// ⚠️ **THIRTY-EIGHT NON-SUBMITTABLE CODES WERE ON THE ACCEPTED SIDE OF THE
// BILLING FLOOR**, in the one module whose entire purpose is to be that floor.
// The direction of harm is the False Claims Act direction this file's own GI
// block was written to prevent — it warned, about K21.0, that "admitting the
// header would put a non-submittable code on the accepted side of the billing
// floor" — and then admitted 32 others, including `Z86.010`, which that same
// GI block added.
//
// The 32 headers include some of the most-used codes in primary care:
// `M54.5` (low back pain, split into M54.50/51/59 in FY2022), `I47.1`
// (supraventricular tachycardia, split in FY2023), SEVEN of the twelve `I71.x`
// aortic entries, and `I83.20/.21/.22` + `I87.30/.31/.32/.33` — the varicose
// vein and venous hypertension families that the ultrasound specialty bills.
//
// ⚠️ "Seven of twelve", not "the whole family" — an earlier draft said the
// latter and it is false. `I71.00`, `I71.02`, `I71.03`, `I71.8` and `I71.9`
// were correct billable codes all along, and the last two appear in this
// commit's own no-regression fixture, so the sentence contradicted the test
// beside it. (`I71.01` is also a DISSECTION, not an aneurysm.) The general
// lesson is the one this file is about: a family-shaped claim is a claim about
// every member, and it has to be measured member by member.
//
// The 6 absent ones are authoring errors of three distinct shapes, and naming
// the shape is what stops them recurring:
//   · `K58.3`    — invented. "Other irritable bowel syndrome" is **K58.8**.
//                  The GI block added K58.3 with that exact description, so
//                  the phantom was admitted AND the real code left uncovered.
//   · `I83.810`  — invented sibling. The family is I83.811/812/813/819.
//   · `S83.20XA`, `T81.32XA` — an `X` placeholder written where a REAL 6th
//                  character belongs (S83.200A, T81.320A).
//   · `T82.510X` — the inverse: `X` written where the 7th-character extension
//                  (A/D/S) belongs.
//   · `T82.61XA` — a FOURTH shape, and the true mirror of the first: a real
//                  digit written where an `X` placeholder belongs. The correct
//                  code is `T82.6XXA`, differing in exactly ONE position (the
//                  5th: `1` where CMS has `X`). An earlier draft called this
//                  one "compounds both", which it does not — it exhibits
//                  neither. Recorded rather than quietly fixed, because the
//                  paragraph's whole claim is that naming the shape is what
//                  stops the error recurring, and a wrong taxonomy on its own
//                  example teaches the next author the wrong thing.
//
// Every one of these is now refused, and refused for a reason the data can
// name. That is the change this file makes.
//
// ── WHY BILLABLE-ONLY, AND WHY THAT IS NOT A JUDGEMENT CALL ────────────────
//
// CMS ships two sets: 74 719 codes valid for submission and 23 467 category
// HEADERS that are not. Admitting the union would be a larger list and a worse
// floor. Ruling **#149(f)**'s re-arming condition names the target precisely —
// *"the allowlist becoming the full CMS **billable** set"* — so refusing
// headers is the RULED behaviour, not a preference exercised here. (The
// condition is written inside RULED (f) and speaks to BOTH clauses: *"(e)'s
// token may be re-read as `not_billable`, and (f)'s derivation becomes
// sound."* An earlier draft here attributed it to (e) alone. In a programme
// where a ruling is cited by clause, the clause is part of the citation.)
//
// The headers are still ingested, as a SEPARATE set, because a refusal that
// can say "this is a category header; bill one of its children" is worth more
// than one that can only say "no". Nothing calls `isIcd10Header` yet; it ships
// with no caller, the same way #148(b) and #149 did.
//
// ── PROVENANCE ─────────────────────────────────────────────────────────────
// Pinned in `icd10cm-fy2026-provenance.json` and asserted by the generator on
// every run: source URL, the CMS page that lists it, retrieval date, sha256 of
// the archive AND of both extracted members, and the effective window
// (2025-10-01 .. 2026-09-30).
//
// ⚠️ THE APRIL 1 2026 UPDATE WAS CHECKED AND CARRIES NO CODE CHANGES. CMS now
// publishes a mid-year revision, and today's date falls inside its window, so
// the October baseline could have been five months stale. It is not: the April
// archive's `icd10cm_codes_2026.txt` and `icd10cm_order_2026.txt` are
// BYTE-IDENTICAL (same sha256) and its own addenda read "0 additions, 0
// deletions, 0 revisions". Recorded because the question is cheap to re-ask
// and expensive to re-answer. AGENTS.md, "RECORD A HYPOTHESIS *BECAUSE* IT WAS
// REFUTED".
//
// ⚠️ FY2027 EXISTS AND TAKES EFFECT 2026-10-01 — under a month from this
// commit. `2027-code-descriptions-tabular-order.zip` is already published. The
// re-ingestion is: download it, update the pinned block in the generator, re-run,
// commit. The gate below fails loudly on a count mismatch, so a stale set
// cannot pass silently — but nothing here *notices the date*, and that gap is
// filed rather than hidden.
// ============================================================================

import { ICD10CM_FY2026_BILLABLE_RAW } from './icd10cm-fy2026-billable.generated';
import { ICD10CM_FY2026_HEADERS_RAW } from './icd10cm-fy2026-headers.generated';

/** Edition this module carries. Bump with the data, never on its own. */
export const ICD10_EDITION = 'ICD-10-CM FY2026 (CMS, effective 2025-10-01 .. 2026-09-30)';

/**
 * Every ICD-10-CM code that is VALID FOR SUBMISSION in FY2026 — 74 719 of them.
 * Stored DOTTED and UPPERCASE (`K63.5`, `I10`), which is the form this codebase
 * has always used and which existing callers depend on:
 * `icd10-allowlist-gastroenterology.test.ts` calls `ICD10_ALLOWLIST.has('K63.5')`
 * directly.
 *
 * ⚠️ Membership means VALID FOR SUBMISSION. It does not mean *appropriate*,
 * *covered*, or *documented* — those are clinical and payer questions this set
 * cannot answer and must not be read as answering.
 */
export const ICD10_ALLOWLIST: ReadonlySet<string> = new Set(
  ICD10CM_FY2026_BILLABLE_RAW.split('\n')
);

/**
 * Category HEADERS — real ICD-10-CM entries that are NOT valid for submission
 * because they require further specificity (`M54.5` -> M54.50/51/59). 23 467
 * of them. Disjoint from {@link ICD10_ALLOWLIST} by construction; the generator
 * asserts the intersection is empty.
 */
export const ICD10_HEADERS: ReadonlySet<string> = new Set(
  ICD10CM_FY2026_HEADERS_RAW.split('\n')
);

/**
 * Validates an ICD-10-CM code against the FY2026 valid-for-submission set.
 *
 * ⚠️ NORMALISATION IS DELIBERATELY UNCHANGED FROM THE STARTER-SET ERA: trim,
 * uppercase, and nothing else. In particular an UNDOTTED code (`E119`) is
 * still refused, exactly as it was before this file grew a complete data set.
 * Widening what the floor accepts is a separate decision from widening what it
 * knows about, and only the second one was asked for. The gate test pins this
 * so it stays a decision rather than becoming an accident.
 *
 * @param code e.g. "E11.9", "I10". Whitespace and case are normalised;
 *             null/undefined/empty return false.
 */
export function isValidIcd10(code: string | null | undefined): boolean {
  if (!code) return false;
  const trimmed = code.trim().toUpperCase();
  if (trimmed.length === 0) return false;
  return ICD10_ALLOWLIST.has(trimmed);
}

/**
 * True when `code` is a real ICD-10-CM entry that is NOT valid for submission —
 * a category header needing further specificity.
 *
 * ⚠️ SHIPS WITH NO CALLER. It exists so a refusal can eventually distinguish
 * *"that is a header, bill one of its children"* from *"that is not a code"*.
 * Wiring it into the drop record's reason token is ruled territory (#149(b)
 * fixed the tokens, #149(e) fixed their wording) and is filed as a follow-up,
 * not done here.
 */
export function isIcd10Header(code: string | null | undefined): boolean {
  if (!code) return false;
  const trimmed = code.trim().toUpperCase();
  if (trimmed.length === 0) return false;
  return ICD10_HEADERS.has(trimmed);
}

/**
 * Total size of the valid-for-submission set.
 *
 * ⚠️ NOTHING READS THIS OUTSIDE TESTS. The line it replaces said "Surfaced in
 * admin diagnostics", which was already false when this file was rewritten and
 * was carried forward unchecked — measured: no route, page or component under
 * `apps/` references it. Kept as a public export because the gate test asserts
 * it and removing an export is a wider change than correcting a sentence, but
 * NOT described as a surface it does not have. This is the same class the
 * epitaph above is about, caught by the adversarial pass in the very commit
 * that diagnoses it.
 */
export const ICD10_ALLOWLIST_SIZE = ICD10_ALLOWLIST.size;

/** Total size of the header set. */
export const ICD10_HEADERS_SIZE = ICD10_HEADERS.size;
