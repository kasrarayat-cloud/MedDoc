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

// ============================================================================
// billableDescendantsOf — the derivation ruling #149(f) DELETED, rebuilt now
// that the condition that ruling named has been met.
// ----------------------------------------------------------------------------
// #149(f) refused a one-tap "use K21.00 instead" chip and deleted the
// `billableChildren` prefix scan rather than repairing it. The scan was sound
// OVER THE SET IT READ, and that set was a 604-code starter list — so it
// returned every child WE HAPPENED TO CARRY, and `length === 1` meant "only one
// sibling made our list" while the surface rendered it as "there is only one
// answer". Measured then:
//
//     billableChildrenOf('E66.0')  ->  ['E66.01']
//
// `E66.0` is obesity due to excess calories; `E66.01` is MORBID (severe)
// obesity, and `E66.09` was simply absent. The chip would have upcoded plain
// obesity to morbid obesity — the False Claims Act direction. 236 refused
// parents collapsed to a singleton that way.
//
// The ruling wrote its own re-arming condition, so this is a lookup and not a
// judgement:
//
//   > "RE-ARMING CONDITION, so this is a lookup: the allowlist becoming the
//   >  full CMS billable set (its own header's "PHASE 7 PATH") — at which point
//   >  membership and billability coincide, (e)'s token may be re-read as
//   >  `not_billable`, and (f)'s derivation becomes sound."
//
// T8 met it. Re-measured against the complete FY2026 release:
//
//     billableDescendantsOf('E66.0')  ->  ['E66.01', 'E66.09']   both siblings
//     billableDescendantsOf('K21.0')  ->  ['K21.00', 'K21.01']
//     billableDescendantsOf('M54.5')  ->  ['M54.50', 'M54.51', 'M54.59']
//
// ⚠️ IT IS NAMED FOR WHAT IT COMPUTES, AND THE OLD NAME WAS WRONG. `I71.0` is a
// header whose child `I71.01` is ALSO a header, so a prefix scan returns
// GRANDCHILDREN. For a substitute list that is the right answer — every entry
// is submittable — but "children" was a claim the code did not honour, and this
// programme has already paid for one name that outlived its accuracy.
//
// ── FOUR MEASUREMENTS THIS RESTS ON, ALL RE-DERIVED AGAINST FY2026 ──────────
//
//   1. ZERO of the 23,467 headers have zero billable descendants. So "this is a
//      header — bill one of these" is an answer that ALWAYS EXISTS. ⚠️ That is a
//      POPULATION FACT about FY2026, not a property of ICD-10-CM, and it
//      re-arms on every future edition — which is why the empty case below
//      still fails closed rather than being treated as unreachable.
//   2. Only 45 headers (0.19%) have EXACTLY ONE billable descendant, and every
//      one is a COMPLETE set of one rather than a truncated set — which is the
//      property that was false before. Measured by shape: 43 are a 6-character
//      header gaining a 7th-character extension (`S06.1X7` -> `S06.1X7A`); the
//      other TWO gain a 4th character carrying a distinct clinical concept —
//      `I1A` (other hypertension) -> `I1A.0` (RESISTANT hypertension), and
//      `U09` -> `U09.9`.
//      ⚠️ An earlier draft called all 45 "a parent whose only specificity is a
//      7th-character extension". That is true of 43 and was inferred from the
//      majority rather than measured — and `I1A.0` is exactly the case it would
//      have waved through, since a lone descendant that ESCALATES the parent is
//      the shape #149(f) died on. It is still the complete and correct answer;
//      what it is not is clinically neutral. See "BILLABLE IS NOT APPROPRIATE".
//   3. ZERO billable codes have a billable descendant — billable codes are
//      leaves. So a submittable code correctly yields NO substitutes.
//   4. Dotted-prefix and undotted-prefix agree on all 242,114 real
//      (header, billable) descendant pairs, in BOTH directions. The stored form
//      is dotted; the hierarchy is defined undotted; scanning the dotted form
//      is therefore sound rather than merely convenient.
//
// ── WHAT THIS DOES NOT KNOW, STATED SO NOBODY READS IT WIDER ────────────────
//
// **BILLABLE IS NOT APPROPRIATE.** Every entry returned is valid for
// submission. Which one the chart supports is a clinical question this set
// cannot answer. A surface may PRESENT these; it may NEVER AUTO-APPLY one.
//
// ⚠️ THE REFUSED POPULATION IS 6,257, AND AN EARLIER DRAFT SAID 4,553. That
// figure counted prefixes of the UNDOTTED CMS strings — a universe this module
// never sees. The guard reads the DOTTED form, where the same enumeration
// yields 6,257: the extra 1,704 are the `A00.`-shaped trailing-dot prefixes
// that exist only once a dot has been inserted. The number was measured
// correctly and then quoted about the wrong set.
//
// **AND "ALL OF THEM, NEVER ONE" IS NOW THE UI'S OBLIGATION.** This returns the
// complete set — the largest header expands to 3,096 entries. A surface that
// shows the first three of those has reintroduced #149(f)'s defect one layer up,
// with the data blameless.
//
// ⚠️ SHIPS WITH NO CALLER, as `isIcd10Header`, #148(b) and #149 all did.
// Whether the substitute chip exists at all is a product decision parked under
// #148, and this file does not make it.
// ============================================================================

/**
 * Billable codes sorted for binary search. Built once at module load; the
 * lookup is O(log n + k) rather than a 74,719-entry scan per call.
 */
const BILLABLE_SORTED: readonly string[] = Object.freeze(
  [...ICD10_ALLOWLIST].sort()
);

/**
 * The single frozen empty result.
 *
 * ⚠️ EVERY RETURN PATH IS FROZEN, AND THE REFUSAL PATHS WERE NOT. The scan path
 * returned `Object.freeze(out)` while the three refusal paths returned a bare
 * `[]`, so `push()` SUCCEEDED on a refusal and THREW on an answer — the same
 * caller operation behaving differently by input. The path where a caller could
 * write a fabricated substitute into the array was precisely the path the
 * function had refused to answer. The gate now has an arm for this; it had none.
 */
const NO_DESCENDANTS: readonly string[] = Object.freeze([]);

/**
 * Every VALID-FOR-SUBMISSION code that sits underneath `code` in the ICD-10-CM
 * hierarchy — the complete set, sorted, never truncated.
 *
 * - a **header** returns its billable descendants (at least one, in FY2026)
 * - a **billable** code returns `[]` — it is a leaf, and needs no substitute
 * - **anything else** returns `[]`
 *
 * ⚠️ THE INPUT MUST BE A CODE THIS MODULE KNOWS. A string that is neither a
 * header nor billable returns `[]` even when it is a prefix of real codes, so
 * `S82.62X` — what you get by dropping a required 7th character, and a prefix
 * of sixteen real billable codes — can never be answered as though it were a
 * real category. *Admit only what you understand.*
 *
 * ⚠️ AN EARLIER DRAFT USED `I83.8` AS THAT EXAMPLE AND IT IS A REAL HEADER:
 * `billableDescendantsOf('I83.8')` correctly returns EIGHT codes. The same
 * wrong guess was made in the gate's fixture, caught there by an assertion,
 * and **fixed in the test while this sentence kept the false claim** — the
 * exact prose-decay this module's own epitaph is about, committed inside the
 * commit that diagnoses it. Recorded rather than quietly corrected.
 *
 * @param code e.g. "M54.5". Whitespace and case are normalised exactly as
 *             {@link isValidIcd10} normalises them, and no more.
 */
export function billableDescendantsOf(
  code: string | null | undefined
): readonly string[] {
  if (!code) return NO_DESCENDANTS;
  const trimmed = code.trim().toUpperCase();
  if (trimmed.length === 0) return NO_DESCENDANTS;
  // Refuse to answer about a string we cannot characterise.
  if (!ICD10_HEADERS.has(trimmed) && !ICD10_ALLOWLIST.has(trimmed)) return NO_DESCENDANTS;

  // Binary search to the first candidate, then walk while the prefix holds.
  let lo = 0;
  let hi = BILLABLE_SORTED.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (BILLABLE_SORTED[mid] < trimmed) lo = mid + 1;
    else hi = mid;
  }
  const out: string[] = [];
  for (let i = lo; i < BILLABLE_SORTED.length; i++) {
    const c = BILLABLE_SORTED[i];
    if (!c.startsWith(trimmed)) break;
    // STRICTLY longer: a code is never its own descendant.
    if (c.length > trimmed.length) out.push(c);
  }
  return Object.freeze(out);
}
