// ============================================================================
// F8-S1b — THE DROP RECORD. PURE, CLIENT-SAFE LEAF.
// ----------------------------------------------------------------------------
// F8's contract carries an owner-decided rule: **SHOW, never hide.** A candidate
// the pipeline threw away renders as a warn-state card NAMING THE REASON, rather
// than vanishing.
//
//   > "A suggester that silently loses candidates teaches the doctor to distrust
//   >  the list, and a distrusted list is worse than no list."
//   >  — docs/foundation/f8-icd-tab-design.md, "THE AMBER RULE"
//
// ⚠️ **THE RULE HAD NO SUBSTRATE.** `07a-icd-coding.ts` drops candidates at FOUR
// distinct exits and stored **none** of them: the first emitted an audit row, the
// other three a `console.info` line, and `icdCodes` was written as
// `{ codes: <survivors> }` with the losers discarded. So the surface had nothing
// to render and no amount of UI work could have produced it.
//
// ⚠️ **AND THE FOUR EXITS ARE NOT ONE BUCKET.** AGENTS.md records the cost of
// merging them (`notMentionedCount`: FIVE exits into one bucket named *not
// mentioned*, so a REFUSAL and an ABSENCE became the same number and could not
// answer the one question a count like that gets asked). Each exit carries its
// own reason token.
//
// ── ⚠️ THE TOKEN IS `not_in_verified_allowlist`, AND THE NAME IS THE FINDING ──
//
// **THE FIRST DRAFT OF THIS FILE CALLED IT `not_in_billable_set`, AND THE
// ADVERSARIAL PASS MEASURED THAT FALSE.** It is recorded here rather than
// quietly renamed, because the mistake is this file's own thesis turned on its
// author.
//
// `isValidIcd10` is `ICD10_ALLOWLIST.has(...)` over a **604-code STARTER SET**
// whose own header says it *"does NOT replace the full CMS list (~70 000
// codes)"*. So a refusal means **"absent from our verified list"**, which is a
// fact about OUR COVERAGE — not **"not a billable ICD-10-CM code"**, which is a
// fact about the CODE. Measured on production over all 64
// `CODING_COACH_REJECTED_INVALID_ICD` rows, 65 distinct codes, partition
// reconciling 12 + 2 + 51 = 65:
//
//   · 12 have since been added to the allowlist — no longer refused
//   · 2  are genuinely category-header-shaped (`I83.89`, `I83.9`)
//   · 51 are REAL, SUBMITTABLE codes absent from the starter set —
//     `Z48.815`, `I87.312`, `Z87.39`, `R59.0`, `F10.20`, `M17.11`, `D62`, …
//
// **Rendering "not billable" over those 51 would tell a physician something
// false about a code they may legitimately need, and the direction of harm is
// UNDER-CODING.** The contract's own verification badge already says the true
// thing — *"Not in verified set"* — so the honest token and the designed UI
// agree; only this file's first draft disagreed with both.
//
// > **THE ALLOWLIST KNOWS MEMBERSHIP. IT DOES NOT KNOW BILLABILITY, AND IT
// > ANSWERS ANYWAY.** AGENTS.md, *AN AUTHORITY ANSWERS SOME OF YOUR QUESTIONS,
// > NOT ALL OF THEM* — arriving inside the fix for the bucket-collapse class.
//
// ── ⚠️ AND `billableChildren` WAS DELETED FOR THE SAME REASON ───────────────
//
// The contract asks for a one-tap *"Use K21.00 instead"* chip, and a first draft
// derived it by prefix-scanning the allowlist. **The pass refuted it on the same
// axis and the fix is a REFUSAL, not a repair.** ICD-10-CM children do extend
// their parent's string, so the scan is *sound over the set it reads* — and that
// set is the starter list, so it returns every child WE HAPPEN TO CARRY. Then
// `length === 1` means *"only one sibling made our list"* and NOT *"there is
// only one answer"*, while the surface renders it as the latter. Measured:
//
//   billableChildrenOf('E66.0')  ->  ['E66.01']
//
// `E66.0` is obesity due to excess calories; `E66.01` is **MORBID (severe)**
// obesity, and its sibling `E66.09` is simply absent from the allowlist. **The
// one-tap chip would have upcoded plain obesity to morbid obesity** — the False
// Claims Act direction AGENTS.md's GI entry exists for. `E11.6` → `['E11.65']`
// offers hyperglycemia where the record may say hypoglycemia. 236 refused
// parents collapse to a singleton this way.
//
// The header this replaces claimed *"ALL of them, never one"* and cited the
// split-family rule. **The rule was right and the implementation could not
// honour it**, because the authority it consulted cannot enumerate siblings it
// does not contain. A suggestion that is right 236 times and upcodes once is not
// a feature; it is the wrong-field failure canon prices above an absent one.
//
// **RE-ARMING CONDITION, so this is a lookup rather than a judgement:** the
// allowlist becoming the full CMS billable set (its own header's "PHASE 7 PATH")
// — at which point membership and billability coincide, `not_in_verified_allowlist`
// may be re-read as `not_billable`, and a sibling derivation becomes sound.
// Until then the surface names the reason and offers no substitute.
//
// ── WHY THIS LIVES IN `icdCodes` AND DECISIONS DO NOT ──────────────────────
//
// Ruling #148(c) put the physician's DECISION in its own column precisely
// because `07a-icd-coding.ts` replaces `icdCodes` wholesale. The drop record has
// the OPPOSITE requirement and therefore the opposite home: it is L7a's own
// output, generated in the same pass as the survivors, and it MUST be replaced
// with them. A drop record that outlived the run that produced it would describe
// a note the suggester no longer sees — the orphan class, arriving by the door
// that ruling closed.
//
//   decision  -> `icdDecisions`  -> must SURVIVE a re-run  -> separate column
//   drop      -> `icdCodes`      -> must be REPLACED       -> same blob
//
// ── ⚠️ PHI POSTURE — CODES AND REASONS ONLY, NEVER MODEL PROSE ─────────────
//
// `07a-icd-coding.ts:471-473` already rules that **the AI-emitted `description`
// can carry patient context**, which is why the existing rejection audit row
// records `rejectedCodes` and deliberately not the descriptions. This record
// inherits that ruling rather than re-deciding it: a drop carries its CODE and
// its REASON TOKEN. **No model-authored string is stored here at all**, so the
// amber card's text is composed on the surface from a closed set of reasons.
//
// ⚠️ HONEST LIMIT, because the claim above is narrower than it sounds: the
// SURVIVORS in the same blob already carry `evidence_quote`, a verbatim note
// excerpt, written by the same statement and returned by the same route. This
// record adds no prose; it does not make the blob prose-free.
//
// ── ⚠️ A DROPPED CODE IS DISJOINT FROM A SURVIVING ONE, BY CONSTRUCTION ────
//
// **The pass found this and it is the clinical one.** The three coherence floors
// filter PER CANDIDATE OBJECT on that object's `evidence_quote`, while a drop
// record is keyed by CODE. So a model emitting one code TWICE with different
// evidence — legal, unconstrained by `IcdResult` — has one instance kept and one
// dropped, and the blob then says both *"E63.9 is suggested"* and *"E63.9 was
// suppressed as unsupported"*. Two records of one visit disagreeing, which is
// the failure this record exists to prevent.
//
// `buildIcdDropRecords` takes the SURVIVOR list and excludes it. That makes the
// safety claim — *a dropped code can never be accepted* — a property of the
// data rather than an accident of the model's output.
// ============================================================================

import { normalizeIcdCode } from './icd-decisions';

// ---------------------------------------------------------------------------
// Shapes
// ---------------------------------------------------------------------------

/**
 * Why a candidate did not survive to `codes[]`. FIVE tokens across FOUR
 * exits in `07a-icd-coding.ts` — the allowlist exit carries two sub-reasons
 * under #180 — and no two EXITS share one, which is the property #149(b)
 * protects.
 *
 * ⚠️ BOTH allowlist-exit tokens are the amber rule's case (#149(c) scopes
 * amber to the EXIT, and #180 split that exit's reason in two). The three
 * coherence floors are clinical suppressions and whether they surface at all is
 * a SURFACE decision that nothing has ruled on — recording them is not a
 * commitment to showing them.
 *
 * ⚠️ ORDER IS LOAD-BEARING, AND THE ARRAY IS NO LONGER THE ORDER. A code
 * claimed twice resolves to whichever bucket `buildIcdDropRecords` visits
 * first, and that function puts `header_use_billable_child` ahead of
 * `not_in_verified_allowlist` regardless of their positions here — deliberately,
 * because between those two the ACTIONABLE reason is the one worth keeping. The
 * resolution order lives at the `byReason` array in that function; this
 * declaration order is not it. Unreachable today (the buckets
 * are disjoint upstream) and deterministic if it ever is.
 */
export const ICD_DROP_REASONS = [
  /** Failed `isValidIcd10` AND the code is not an ICD-10-CM entry in any form —
   *  a fabrication or a typo. There is no substitute to offer. */
  'not_in_verified_allowlist',
  /** ⚠️ RULING #180 — THE SAME EXIT, A SUB-REASON WITHIN IT. Failed
   *  `isValidIcd10` because the code is a category HEADER: a real ICD-10-CM
   *  entry that is not valid for submission. Unlike a fabrication this is
   *  ACTIONABLE — a billable descendant always exists (0 of 23,467 headers have
   *  none, measured against FY2026) and `children` carries the enumerated set.
   *
   *  ⚠️ FIVE TOKENS, FOUR EXITS, AND #149(b) IS INTACT. That ruling forbids
   *  COLLAPSING exits into one bucket (`notMentionedCount` routed five exits
   *  into one, so a REFUSAL and an ABSENCE became the same number). It does not
   *  forbid sub-dividing one exit, and #149(e) permits exactly this re-reading.
   *  The property that matters is that no two EXITS share a token, and the gate
   *  asserts that rather than asserting a token count. */
  'header_use_billable_child',
  /** `dropIncoherentVaricoseCodes` — an asymptomatic varicose code alongside a
   *  symptomatic one. */
  'incoherent_asymptomatic_varicose',
  /** `dropDenialContradictedCodes` — the note explicitly denies the condition. */
  'contradicted_by_denial',
  /** `dropUnsupportedDeficiencyCodes` — E50–E64 supported only by prophylactic
   *  supplementation, ordered-but-unresulted labs, or missed doses. */
  'unsupported_deficiency',
] as const;

export type IcdDropReason = (typeof ICD_DROP_REASONS)[number];

export interface IcdDropRecord {
  /** Normalised through `normalizeIcdCode` — the SAME matcher the decision
   *  substrate keys on. A read path and a write path resolving one identifier
   *  with two matchers is a recorded failure class in this repository. */
  code: string;
  reason: IcdDropReason;
  /**
   * The billable codes beneath a header, enumerated by `billableDescendantsOf`.
   * Present only on `header_use_billable_child`; absent on every other reason.
   *
   * ⚠️ #149(d) RULED THE RECORD IS `{code, reason}` AND NOTHING ELSE, AND #180
   * ADDS THIS FIELD. The property #149(d) protects is that **no MODEL-AUTHORED
   * string is stored** — the model's `evidence_quote` and descriptions stay
   * out. These children are not model-authored: they are derived
   * deterministically from the CMS release by a pure function of `code`. So the
   * rule's product survives the addition, and saying which property is being
   * preserved is the point of writing this down rather than quietly widening
   * the shape.
   *
   * ⚠️ AND IT IS A WRITE-TIME SNAPSHOT OF AN ICD EDITION. Canon: *a decision
   * made at write time must be re-derived where it is used.* **FY2027 takes
   * effect 2026-10-01**, so a record written today can outlive the edition that
   * produced it, and a surface rendering a stale child list would offer a code
   * that no longer exists. A reader that can reach `billableDescendantsOf`
   * SHOULD prefer a fresh derivation from `code`; this field is the value at
   * the time of coding, not a promise about today. Filed rather than solved —
   * the ruling says carry them, and inventing an edition stamp is not something
   * this session was asked to decide.
   */
  children?: readonly string[];
}

/**
 * The runtime key list the narrower below writes, and the compile-time proof
 * that it is exactly `keyof IcdDropRecord`.
 *
 * ⚠️ THIS EXISTS BECAUSE THE NARROWER IS A SILENT STRIPPER. `readIcdDrops`
 * rebuilds each record field by field, so a field added to `IcdDropRecord` and
 * not added here would be dropped by every reader — and nothing would say so.
 * `_NoFieldUnwritten` fails when the interface gains a key the list lacks;
 * `_NoKeyUnknown` fails in the other direction.
 *
 * The same mechanism guards `IcdDecisionRecord` next door, where F8-S1 filed
 * this exact forward-compatibility residual and could not fix it.
 */
export const ICD_DROP_RECORD_KEYS = ['code', 'reason', 'children'] as const;

type _NoFieldUnwritten =
  Exclude<keyof IcdDropRecord, (typeof ICD_DROP_RECORD_KEYS)[number]> extends never
    ? true
    : never;
type _NoKeyUnknown =
  Exclude<(typeof ICD_DROP_RECORD_KEYS)[number], keyof IcdDropRecord> extends never
    ? true
    : never;
/* eslint-disable @typescript-eslint/no-unused-vars */
const _dropFieldsAreWritten: _NoFieldUnwritten = true;
const _dropKeysAreKnown: _NoKeyUnknown = true;
/* eslint-enable @typescript-eslint/no-unused-vars */

// ---------------------------------------------------------------------------
// Building — the WRITE half, pure and exported so it can be DRIVEN
// ---------------------------------------------------------------------------

/**
 * The four exits' outputs plus the survivors, as raw code strings.
 *
 * ⚠️ NAMED PROPERTIES, NOT POSITIONAL ARGUMENTS. Every field is
 * `readonly string[]`, so a caller that swapped two of them would be accepted
 * by `tsc` — and swapping two exits is precisely the regression that inverts
 * this slice's whole product (every varicose suppression reported as a denial).
 * A required NAMED property cannot be confused with a same-typed neighbour by a
 * reader, which is the best the type system offers here; the gate asserts the
 * binding by BEHAVIOUR on top of it.
 */
/**
 * The ICD-10-CM dotted shape: three characters, optionally a dot and up to four
 * more. Covers every real form — `I10`, `M54.51`, `I1A.0`, `S06.1X7A`,
 * `T82.6XXA`, `QA0.0151`.
 *
 * ⚠️ THIS IS A SHAPE CHECK, NOT A VALIDITY CHECK, AND THE DIFFERENCE IS THE
 * POINT. This module cannot ask whether a code exists — it is a client-safe
 * leaf with no allowlist access. What it CAN do is refuse anything that is not
 * code-shaped, which is what stops `children` becoming a prose channel.
 */
const ICD_CODE_SHAPE = /^[0-9A-Z]{3}(\.[0-9A-Z]{1,4})?$/;

/** One header drop: the refused code and the billable codes beneath it. */
export interface IcdHeaderDrop {
  code: string;
  children: readonly string[];
}

export interface IcdDropInputs {
  /** Failed `isValidIcd10` AND is not an ICD-10-CM entry in any form. */
  notInVerifiedAllowlist: readonly string[];
  /**
   * ⚠️ RULING #180. Failed `isValidIcd10` because the code is a category
   * HEADER, with its billable descendants enumerated.
   *
   * ⚠️ THE CLASSIFICATION IS THE CALLER'S JOB, DELIBERATELY, AND THIS FILE
   * CANNOT DO IT. Splitting here would need `isIcd10Header` and
   * `billableDescendantsOf` from `@meddoc/ai` — and this module is a CLIENT-SAFE
   * LEAF whose only import is `./icd-decisions`. `icd-coding-view.tsx` is a
   * `'use client'` component that imports `amberIcdDrops` from here, and no
   * client file imports `@meddoc/ai` today, so that import would pull the
   * Anthropic/OpenAI/Deepgram SDKs and ~700 KB of ICD data into a browser
   * bundle. `07a-icd-coding.ts` runs on the worker, already imports
   * `@meddoc/ai`, and owns the exit — so it classifies and passes both buckets.
   */
  headerUseBillableChild: readonly IcdHeaderDrop[];
  incoherentVaricose: readonly string[];
  contradictedByDenial: readonly string[];
  unsupportedDeficiency: readonly string[];
  /**
   * ⚠️ THE CODES THAT SURVIVED TO `codes[]`. A code here is NEVER recorded as
   * dropped, whatever bucket it also appears in — see the header. This is what
   * makes *"a dropped code can never be accepted"* a property rather than a
   * hope.
   */
  survivors: readonly string[];
}

/**
 * Build the stored drop list: normalised, DEDUPED by code, ordered by reason,
 * and disjoint from the survivors.
 *
 * Three properties the gate asserts by driving this function rather than by
 * reading the source that calls it:
 *
 *   1. every code carries the reason of the exit it arrived from
 *   2. no code appears twice — `07a`'s `IcdResult` places no uniqueness
 *      constraint on the model's array, and a real production response
 *      (`["I87.312","I87.312", …]`) shows duplicates are not hypothetical.
 *      The ACCEPTED side already dedupes (`suggestedIcdCodes`); the drop side
 *      now matches it, so a partition drawn across both reconciles
 *   3. no surviving code is also reported as dropped
 */
export function buildIcdDropRecords(inputs: IcdDropInputs): IcdDropRecord[] {
  const survivors = new Set(
    inputs.survivors.map((c) => normalizeIcdCode(c)).filter((c) => c.length > 0),
  );

  // ⚠️ THE HEADER BUCKET IS FIRST, AND THE ORDER IS LOAD-BEARING (see the header
  // comment on ICD_DROP_REASONS): a code claimed by two buckets resolves to the
  // FIRST. A code cannot be both a header and a fabrication — the classifier is
  // a total function on one exit — but if a caller ever passed both, the
  // ACTIONABLE reason is the one worth keeping.
  const headerChildren = new Map<string, readonly string[]>();
  for (const h of inputs.headerUseBillableChild) {
    const code = normalizeIcdCode(h.code);
    if (!code) continue;
    headerChildren.set(code, h.children);
  }

  const byReason: ReadonlyArray<readonly [IcdDropReason, readonly string[]]> = [
    ['header_use_billable_child', [...headerChildren.keys()]],
    ['not_in_verified_allowlist', inputs.notInVerifiedAllowlist],
    ['incoherent_asymptomatic_varicose', inputs.incoherentVaricose],
    ['contradicted_by_denial', inputs.contradictedByDenial],
    ['unsupported_deficiency', inputs.unsupportedDeficiency],
  ];

  const seen = new Set<string>();
  const out: IcdDropRecord[] = [];
  for (const [reason, codes] of byReason) {
    for (const raw of codes) {
      const code = normalizeIcdCode(raw);
      if (!code) continue;
      if (survivors.has(code)) continue;
      if (seen.has(code)) continue;
      seen.add(code);
      if (reason === 'header_use_billable_child') {
        // ⚠️ THE WRITER VALIDATES TOO, AND THE FIRST DRAFT DID NOT. Only the
        // reader shape-checked, so `buildIcdDropRecords` called directly with
        // prose children stored the prose verbatim — and the claim "children
        // cannot become a prose channel" was true of one path out of two. Its
        // real input is `billableDescendantsOf`, which is trusted; this is
        // defence in depth on a field that is rendered to a doctor.
        const kids = (headerChildren.get(code) ?? []).filter((raw) => {
          const k = normalizeIcdCode(raw);
          return (
            !!k && ICD_CODE_SHAPE.test(k) && k.startsWith(code) && k.length > code.length
          );
        });
        out.push({ code, reason, children: kids });
      } else {
        out.push({ code, reason });
      }
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Reading
// ---------------------------------------------------------------------------

function isDropReason(v: unknown): v is IcdDropReason {
  return typeof v === 'string' && (ICD_DROP_REASONS as readonly string[]).includes(v);
}

/**
 * The stored drop list, defensively narrowed, from the RAW `icdCodes` column.
 *
 * ⚠️ A MALFORMED ENTRY IS DROPPED RATHER THAN REPAIRED, and the asymmetry is
 * deliberate: this record exists to tell a physician *why a code is missing*,
 * and inventing a reason for an unparseable entry would put a sentence in front
 * of a doctor that nothing produced. An entry that cannot be read is one the
 * surface must not narrate.
 *
 * ⚠️ Unlike `readIcdDecisions`, narrowing here CANNOT delete anything: nothing
 * writes this column but L7a, and L7a replaces it wholesale from its own run.
 *
 * Returns `[]` for the legacy bare-array shape, which carries no drop record by
 * construction. Measured on production 2026-08-25: all 49 non-null rows are
 * objects whose ONLY top-level key is `codes`, so every existing row reads `[]`
 * here — the widening collides with nothing.
 */
export function readIcdDrops(rawIcdCodes: unknown): IcdDropRecord[] {
  if (!rawIcdCodes || typeof rawIcdCodes !== 'object' || Array.isArray(rawIcdCodes)) {
    return [];
  }
  const blob = rawIcdCodes as { dropped?: unknown };
  if (!Array.isArray(blob.dropped)) return [];

  const seen = new Set<string>();
  const out: IcdDropRecord[] = [];
  for (const entry of blob.dropped) {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) continue;
    const rec = entry as Record<string, unknown>;
    const code = normalizeIcdCode(rec.code);
    if (!code) continue;
    if (!isDropReason(rec.reason)) continue;
    // The writer dedupes; the READER does too, so a hand-edited or
    // pre-dedupe row cannot make the surface render one code twice.
    if (seen.has(code)) continue;
    seen.add(code);
    if (rec.reason === 'header_use_billable_child') {
      // ⚠️ SHAPE-VALIDATED, NOT MERELY NORMALISED — AND THE FIRST DRAFT WAS NOT.
      // `normalizeIcdCode` is `trim().toUpperCase()` and nothing else, so
      // "Mrs Patient of 4 Elm Street" survives it as a non-empty string. Passing
      // children through it alone made this field a PROSE CHANNEL into a record
      // whose entire posture (#149(d)) is that no model-authored string is
      // stored — and a surface would have rendered that prose as a billing code.
      // Caught by this file's own hostile-blob arm, which is why that arm was
      // widened to cover `children` when the field was added.
      //
      // The blob is JSONB and can have been hand-edited, and this leaf
      // deliberately cannot re-derive the true set (it has no allowlist access —
      // see IcdDropInputs). So each entry must match the ICD-10-CM SHAPE, be
      // deduped, and keep its order. Anything else is dropped silently, exactly
      // as a malformed `code` is.
      //
      // ⚠️ NOT TRUNCATED, deliberately: the real maximum is 3,096 (S82), and
      // capping the list is the shape #149(f) died on, one layer down.
      const kids: string[] = [];
      const kseen = new Set<string>();
      if (Array.isArray(rec.children)) {
        for (const raw of rec.children) {
          const k = normalizeIcdCode(raw);
          // ⚠️ AND IT MUST BE A DESCENDANT OF `code`, WHICH THIS LEAF CAN CHECK.
          // The first draft validated SHAPE only, so a hand-edited blob could
          // put the refused header back in its own substitute list, or an
          // ANCESTOR that is even less submittable: children
          // ['M54.5','A00.0','M54'] came straight back, and a surface would
          // print "M54.5 — not billable as written, use one of: M54.5, M54, …".
          // The stated "this leaf cannot re-derive the true set" limit is real
          // but does NOT cover this: strict prefix extension is pure string
          // logic and needs no allowlist. It cannot prove a child is BILLABLE;
          // it can prove it is not the code itself, not an ancestor, and not
          // from an unrelated chapter.
          if (!k || !ICD_CODE_SHAPE.test(k) || kseen.has(k)) continue;
          if (!k.startsWith(code) || k.length <= code.length) continue;
          kseen.add(k);
          kids.push(k);
        }
      }
      out.push({ code, reason: rec.reason, children: kids });
    } else {
      out.push({ code, reason: rec.reason });
    }
  }
  return out;
}

/**
 * The amber rule's own subset: drops a physician is meant to SEE.
 *
 * ⚠️ NAMED SEPARATELY FROM `readIcdDrops` ON PURPOSE. The contract's amber rule
 * is about the not-in-our-list case; the three coherence floors are clinical
 * suppressions whose surfacing nothing has decided. A caller that wants "the
 * amber cards" must ask for them by that name, so that widening the set later is
 * a visible edit here rather than a silent change of meaning at a call site.
 *
 * ⚠️ AND THE THREE IT EXCLUDES ARE NOTE-DEPENDENT, WHICH IS A SECOND REASON.
 * `contradicted_by_denial` and `unsupported_deficiency` are claims about the
 * note text at coding time, and `actions/soap.ts` rewrites `soapFinal` without
 * re-running L7a — so a stored suppression reason can outlive the sentence that
 * justified it. `not_in_verified_allowlist` is note-INDEPENDENT and cannot go
 * stale that way. **Any future caller that surfaces `readIcdDrops` instead of
 * this function inherits that staleness**, and that is the re-arming condition.
 */
export function amberIcdDrops(rawIcdCodes: unknown): IcdDropRecord[] {
  // ⚠️ BOTH ALLOWLIST-EXIT TOKENS, AND OMITTING THE NEW ONE WOULD BE A SILENT
  // REGRESSION WORSE THAN THE STATUS QUO. #149(c) rules that the amber case is
  // the ALLOWLIST EXIT — not one token — and #180 splits that exit's reason in
  // two without moving the exit. A filter still naming only the fabrication
  // token would make every HEADER drop invisible: the one case that is
  // actionable would be the one the doctor never sees.
  const AMBER: ReadonlySet<IcdDropReason> = new Set([
    'not_in_verified_allowlist',
    'header_use_billable_child',
  ]);
  return readIcdDrops(rawIcdCodes).filter((d) => AMBER.has(d.reason));
}

/**
 * The partition, by reason. Every token gets a key whether or not it occurred,
 * so a caller cannot mistake "this exit did not fire" for "this exit does not
 * exist" — and the total reconciles against `readIcdDrops().length`.
 */
export function icdDropCountsByReason(
  rawIcdCodes: unknown,
): Record<IcdDropReason, number> {
  const counts = Object.fromEntries(
    ICD_DROP_REASONS.map((r) => [r, 0]),
  ) as Record<IcdDropReason, number>;
  for (const d of readIcdDrops(rawIcdCodes)) counts[d.reason] += 1;
  return counts;
}
