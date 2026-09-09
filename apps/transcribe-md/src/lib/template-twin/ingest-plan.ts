// ============================================================================
// RULING #274 — THE INGEST ENTRY POINT: bytes in, a new compiled version out,
// and every certified disposition that still has a home carried across.
// ----------------------------------------------------------------------------
// A SERVER-SIDE FUNCTION, NOT A ROUTE — so the in-container door
// (`run-ruled-mutation.sh --in transcribe-md-worker`) can drive it under a
// committed declaration, and so the ordinary upload path can reuse it later.
//
// ── WHY A NEW `NoteTemplate` AND NOT A SECOND COMPILED VERSION ──────────────
// `TemplateTwinCompiledVersion.noteTemplateId` is **@unique**: one compiled
// version per template, and the only `create` is the first-upload path. So
// "a new draft compiled version" cannot mean a row beside the certified one.
// Updating in place is worse than wrong — it would destroy the very version
// the transfer reads its certified dispositions FROM.
//
// Owner ruling (READING A): mint a new `NoteTemplate` + its compiled version,
// transfer, activate, and DEMOTE the old one — never delete it. The frozen
// per-visit fill manifests keep pointing at whatever they were filled against,
// which is why demotion is safe and deletion never would be.
//
// ⚠️ THE ACTIVE-TEMPLATE ID ROTATES, AND THAT IS THE ESTABLISHED SHAPE — it
// rotated on the 2026-09-03 transfer and again when `939aa9ea` replaced the
// 35-control form. Anything holding a template id by literal is a defect, not
// a constraint on this function.
//
// ── ⚠️ THE MATCH IS STRUCTURAL, NOT BY `fieldId` — MEASURED, NOT ASSUMED ────
// `fieldId = sha256(sourceSha256 ‖ partName ‖ path ‖ kind)` (compiler.ts:885,
// via `stableId`), and `sourceSha256` is the sha of the WHOLE PACKAGE
// (package-security.ts:177). So **any** byte change rotates **every** fieldId.
//
// Measured on the 80-control `WM IOV Template.docx`, compiling twice and then
// once more after adding a single space inside `word/document.xml`:
//
//   key                          matched   distinct
//   fieldId                        0/80      80/80  (unique, and useless here)
//   partName|path|ordinal|kind    80/80      80/80  (unique ✓)
//   label|kind                    80/80      26/80  ⚠️ NOT UNIQUE
//   displayOrder|kind             80/80      80/80  (unique, but shifts on insert)
//
// Matching on `fieldId` would therefore transfer **nothing** the moment the
// bytes differ by so much as a space — the "changed bytes" half of this
// primitive would be dead on arrival while looking correct for the re-issue,
// whose bytes are identical.
//
// ⚠️ AND `label|kind` IS THE TRAP: it matches 80/80 and looks like a perfect
// key, while carrying only **26 distinct values**. Set-membership is not a
// pairing — it would mis-pair 54 controls and hand one control's certified
// clinical disposition to another. The uniqueness column is the only reason
// that was visible.
//
// So the key is the renderer binding's structural position — which is exactly
// `stableId`'s own inputs minus the package sha. ONE mechanism serves both
// halves of the ruling: identical bytes match everywhere, so everything
// transfers; changed bytes match wherever the control did not move, so what
// matches transfers and the rest re-proposes.
// ============================================================================
// ⚠️ THIS MODULE IMPORTS NOTHING BUT TYPES, AND THAT IS LOAD-BEARING RATHER
// THAN TIDY. The correspondence rule is the part that can be subtly wrong — a
// mis-pairing hands one control's certified clinical meaning to another — so it
// must be reachable by an arm that stands up no database and no auth.
//
// Measured, not asserted: while these lived in `ingest.ts`, importing
// `planTransfer` pulled in `create-draft.ts` -> `next-auth`, and the arms died
// on `Cannot find module '.../next/server'` before a single expectation ran.
// An arm that cannot load is an arm nobody writes for the awkward cases, which
// is exactly where this rule is dangerous.
import {
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
} from './ir';

/**
 * A field's IDENTITY. Two of them, both SEMANTIC, and nothing else.
 *
 * ══ FOUR ROUNDS OF REFUTATION, FOUR BLOCKING DEFECTS, ONE ERROR ════════════
 *
 * R1 · `partName + path + ordinal + kind`. Both moving parts are positional and
 *      shift in lockstep; one inserted control mis-paired 3 of 3 on the real
 *      form.
 * R2 · the replacement claimed "a collision never mis-transfers". FALSE — first
 *      wins guarded the SOURCE map only, so two controls claimed one certified
 *      row and a LEFT leg finding was certified to print the RIGHT leg's.
 * R3 · `sdtId` called STABLE on a `28/80, 28 distinct` measurement taken from
 *      ONE document. The owner's form assigns ids with `nextId += 1` per control
 *      IN DOCUMENT ORDER, so one dropped clause renumbered everything and walked
 *      the exam narrative fifteen rows sideways, every one `certified`.
 * R4 · pairing `sdtId` with the LABEL was supposed to refuse that renumber,
 *      because "control N inherits N-1's id, whose LABEL is a different
 *      question". ⚠️ THAT SENTENCE IS FALSE ON THE REAL DOCUMENT. Measured:
 *
 *        80 fields · 26 distinct labels · 14 ADJACENT pairs sharing a label
 *        1 tag · 1 alias · 28 sdtIds · only 10 with an sdtId AND a unique label
 *
 *      Six consecutive controls read "CLINICAL INDICATIONS: Choose an item.…"
 *      and eight read "The … from the … to the …", because 79 of 80 carry no
 *      alias and the compiler derives their label from surrounding text. On real
 *      bytes re-stamped with the owner's id scheme, a single deletion mis-paired
 *      **14 of 14** transfers, all `certified`, every bijection guard satisfied.
 *
 * ⚠️ THE SAME ERROR EVERY TIME: A PROPERTY MEASURED ON ONE DOCUMENT AND STATED
 * AS UNIVERSAL — and `sdtId` produced a blocking defect in TWO CONSECUTIVE
 * ROUNDS, once alone and once paired.
 *
 * ══ SO THE ID PATH IS DELETED, NOT NARROWED ════════════════════════════════
 *
 * A label-uniqueness precondition would make the pairing sound and would buy
 * TEN controls of eighty, while adding a fourth chance for a subtle hole in the
 * one function that decides which clinical meaning lands on which control.
 * That is not a trade worth taking here. What remains is:
 *
 *   1. `fieldId` — universal and EXACT, true only for identical bytes. This is
 *      the re-issue act in full: same artifact, same 53 ids, everything
 *      transfers, nothing inferred.
 *
 *   2. `tag` — the author's SEMANTIC name (`exam_lungs`, `telehealth_consent`).
 *      It means the same control wherever it moves and whatever it is renamed
 *      to, because a human wrote it to mean that.
 *
 * ⚠️ AND THE COST IS REAL, SO IT IS WRITTEN DOWN RATHER THAN DISCOVERED. On
 * CHANGED bytes, a control with no tag does not transfer — it re-proposes. On
 * `WM IOV Template.docx` that is 79 of 80. On the owner's consult form the 18
 * controls its generator adds all carry tags and survive; whatever the blank
 * source contributes does not, unless it carries tags of its own.
 *
 * That is a smaller transfer than every earlier key CLAIMED, and the only one
 * that has not been shown to hand a patient's clinical value to the wrong
 * question. **A re-proposal is a question to the doctor; a mis-transfer is a
 * wrong answer wearing a certification.**
 */
export type IdentityKey = string & { readonly __brand: 'IdentityKey' };

/**
 * The key AMBIGUITY is counted on — deliberately WITHOUT `kind`.
 *
 * ⚠️ ROUND FIVE: `kind` IN THE COUNTED KEY DEFEATED THE BIJECTION. It is
 * CONTENT-DERIVED and MUTABLE — `compiler.ts:854-858` computes it from
 * `isScaffolded(properties, content)` and a label heuristic, so clearing a
 * control's pre-filled sentence, or adding `w:showingPlcHdr`, re-types it.
 *
 * So two controls sharing ONE tag but differing in kind produced two DISTINCT
 * keys, each unique, and "a key non-unique on either side carries nothing"
 * never fired. Measured on real bytes with the shipped generator's own tag
 * `ros_gi_weight`: the ROS alarm-feature clause inherited a DELETED weight
 * MEASUREMENT control's certified disposition, arriving `certified`, while its
 * own was discarded. The transfer count was 2 where a correct run returns 1 —
 * and the upload path passes no `expectTransferCount`.
 *
 *     A TAG THAT NAMES TWO CONTROLS IS AMBIGUOUS. Whether those controls
 *     currently look like prose or like a measurement is not the question, and
 *     letting a MUTABLE attribute answer it re-opened the hole four rounds of
 *     deletion had closed.
 *
 * ⚠️ AND THE FIX IS A NARROW, NOT A DELETE — dropping `kind` from the match as
 * well would red a deliberate arm: *"a kind CHANGE on the same TAG does not
 * inherit — same name, different question"*. A text box the doctor turned into
 * a dropdown genuinely is a different question, and its certified
 * `expectedDataType` and `allowedOptions` no longer describe it.
 *
 * Two questions, two keys: **AMBIGUITY is counted without `kind`; MATCHING
 * still requires it.**
 */
/**
 * The identity keys a field answers to, each PAIRED with the key its
 * uniqueness is COUNTED under.
 *
 * ⚠️ ONE CONSTRUCTION SITE, DELIBERATELY — AND THE PREVIOUS SHAPE IS WHY.
 * The pairing used to be recovered AFTER the fact by re-parsing the joined
 * match key (`ambiguityKeyFor`: split on NUL, keep the first three fields).
 * That is a LOSSY PARSE OF ITS OWN DELIMITER: a `w:tag` containing U+0000
 * yields more than four fields, so the "ambiguity key" recovered from it was a
 * TRUNCATION — a key describing a DIFFERENT control. A genuinely ambiguous tag
 * could then read as unique and claim a certified clinical disposition.
 *
 * Found by the refutation pass over #1087 and LATENT rather than live: the
 * act's only caller pins the artifact by sha and passes `expectFieldIds`, so
 * every control matches on its own `fid` and no tag key is consulted. It goes
 * live the moment the ordinary upload path uses this primitive — which is
 * exactly the path #274 split it out to serve.
 *
 * Building both keys together removes the parse, and with it the class: the
 * two keys cannot disagree about which control they describe, whatever bytes
 * the tag contains. The readers are now ONE.
 *
 * The distinction the pair encodes is unchanged and is round five's finding:
 * **AMBIGUITY is counted WITHOUT `kind`; MATCHING still requires it**, because
 * `kind` is content-derived and mutable.
 */
export interface IdentityKeyPair {
  /** what a match must equal — carries `kind` on the tag key. */
  readonly match: IdentityKey;
  /** what uniqueness is counted under — no `kind`. */
  readonly ambiguity: IdentityKey;
}

export function identityKeyPairs(field: TemplateField): IdentityKeyPair[] {
  const b = field.rendererBinding;
  const fid = `fid\u0000${field.fieldId}` as IdentityKey;
  const pairs: IdentityKeyPair[] = [{ match: fid, ambiguity: fid }];

  // ⚠️ TRIMMED AND CASE-SENSITIVE, AND EMPTY IS NOT AN IDENTITY. A tag of ""
  // or "   " names nothing; treating it as a key would collapse every untagged
  // control in the document into one identity.
  const tag = (b.tag ?? '').trim();
  if (tag !== '') {
    pairs.push({
      match: `tag\u0000${b.partName}\u0000${tag}\u0000${field.kind}` as IdentityKey,
      ambiguity: `tag\u0000${b.partName}\u0000${tag}` as IdentityKey,
    });
  }
  return pairs;
}

export function ambiguityKeys(field: TemplateField): IdentityKey[] {
  return identityKeyPairs(field).map((p) => p.ambiguity);
}

export function identityKeys(field: TemplateField): IdentityKey[] {
  return identityKeyPairs(field).map((p) => p.match);
}

export type IngestGuardFailure =
  | { code: 'SOURCE_SHA_MISMATCH'; expected: string; actual: string }
  | { code: 'FIELD_IDS_NOT_SET_EQUAL'; missing: string[]; unexpected: string[] }
  | { code: 'TRANSFER_SOURCE_NOT_FOUND'; compiledVersionId: string }
  | { code: 'TRANSFER_SOURCE_WRONG_PRACTICE'; compiledVersionId: string }
  | { code: 'NO_FILLABLE_FIELDS' }
  | { code: 'TRANSFER_COUNT_MISMATCH'; expected: number; actual: number }
  | { code: 'TRANSFER_TARGET_ALREADY_CERTIFIED'; compiledVersionId: string }
  | { code: 'TRANSFER_PLAN_STALE'; fieldId: string };

export class TemplateTwinIngestRefused extends Error {
  constructor(readonly failure: IngestGuardFailure) {
    super(`template-twin ingest REFUSED: ${failure.code}`);
    this.name = 'TemplateTwinIngestRefused';
  }
}

export interface IngestTemplateTwinInput {
  /** The stored artifact's bytes. Read back, never re-derived. */
  source: Uint8Array;
  actor: { userId: string; userEmail: string; practiceId: string };
  /** Name for the new template row. */
  templateName: string;

  /**
   * The compiled version whose CERTIFIED dispositions are carried across. Its
   * IR supplies the structural keys; its mappings supply the dispositions.
   */
  transferFrom?: string;

  /**
   * ⚠️ PRE-GUARDS. Every one of these is checked BEFORE a single row is
   * written, which is the whole reason this function exists rather than a
   * wrapper around `createTemplateTwinDraft`: that path stores the artifact
   * and only then can fail (`PERSISTENCE_FAILED`), and source deletion is
   * INTENTIONALLY UNAVAILABLE — so a post-write guard leaves an orphan object
   * that nothing can remove.
   *
   * They are OPTIONAL because the primitive serves two callers with different
   * strictness, and conflating them would break one of them:
   *
   *   · THE RE-ISSUE ACT passes both. The bytes are the pinned artifact, so
   *     the field ids must come back identical — anything else means the
   *     compiler moved under us and the act must not proceed.
   *   · THE UPLOAD PATH passes neither. Its bytes are new by definition, so a
   *     set-equality guard would refuse every legitimate re-upload.
   */
  guards?: {
    expectSourceSha256?: string;
    expectFieldIds?: readonly string[];
    /** How many dispositions the caller believes will transfer. */
    expectTransferCount?: number;
  };
}

export interface IngestTemplateTwinResult {
  noteTemplateId: string;
  compiledVersionId: string;
  sourceSha256: string;
  fieldCount: number;
  /** Certified dispositions carried across, by structural correspondence. */
  transferred: number;
  /** Fields with no certified counterpart — these re-propose. */
  reproposed: number;
  /** Demoted, never deleted. Null when nothing was superseded. */
  demotedNoteTemplateId: string | null;
}

/** What the transfer decided, per field, before anything is written. */
export interface TransferPlan {
  readonly transferred: ReadonlyArray<{
    fieldId: string;
    fromFieldId: string;
    mapping: SemanticMapping;
  }>;
  readonly reproposed: ReadonlyArray<string>;
}

/**
 * Decide, WITHOUT TOUCHING THE DATABASE, which of the new document's fields
 * inherit a certified disposition and which must be proposed afresh.
 *
 * ⚠️ SPLIT OUT AND EXPORTED SO ITS ARMS NEED NO DATABASE. The correspondence
 * rule is the part that can be subtly wrong — a mis-pairing hands one control's
 * clinical meaning to another — and an arm that has to stand a schema up to
 * reach it is an arm nobody writes for the awkward cases.
 */
export function planTransfer(input: {
  target: TemplateDocIR;
  sourceIr: TemplateDocIR | null;
  certifiedByFieldId: ReadonlyMap<string, SemanticMapping>;
}): TransferPlan {
  const { target, sourceIr, certifiedByFieldId } = input;

  // ══════════════════════════════════════════════════════════════════════════
  // ⚠️ A TRANSFER REQUIRES A BIJECTION. AN AMBIGUOUS KEY TRANSFERS TO NOBODY.
  // --------------------------------------------------------------------------
  // The first version of this function asserted, in its own comment, that
  // "first wins, and a collision NEVER mis-transfers — the loser surfaces as a
  // re-proposal". THAT CLAIM WAS FALSE, and a refutation pass proved it.
  //
  // First-wins guarded the SOURCE map. Nothing guarded the TARGET side, so two
  // target fields sharing one key BOTH looked it up and BOTH transferred from
  // the same row. Measured, on a section the doctor copy-pasted so Word kept
  // the `w:id` on both halves:
  //
  //     "Right leg findings"  <-  venous.reflux.RIGHT
  //     "Left leg findings"   <-  venous.reflux.RIGHT      <- laterality swapped
  //     transferred = 2, distinct source rows consumed = 1
  //
  // A left-leg finding certified to print the right leg's concept, arriving
  // `CERTIFIED` so it never reaches a confirmation list. Nothing downstream
  // could catch it: the COUNT is 2, which is what a correct run also returns,
  // so `expectTransferCount` passes; both fields exist, so `TRANSFER_PLAN_STALE`
  // does not fire.
  //
  // So the rule is now structural rather than asserted: a key must appear
  // EXACTLY ONCE on each side to carry a disposition. Ambiguity on either side
  // re-proposes, which is a question to the doctor rather than a wrong answer
  // presented as certified.
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠️ COUNTED ON `ambiguityKeys` (no `kind`), MATCHED ON `identityKeys` (with
  // it). See the note on `ambiguityKeys`: counting with a MUTABLE attribute let
  // one tag name two controls without ever reading as ambiguous.
  const countKeys = (fields: ReadonlyArray<TemplateField>): Map<IdentityKey, number> => {
    const counts = new Map<IdentityKey, number>();
    for (const field of fields) {
      for (const key of ambiguityKeys(field)) counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return counts;
  };

  /**
   * Is THIS key unique in that document?
   *
   * ⚠️ PER-KEY, NOT PER-FIELD — AND THE FIRST VERSION WAS PER-FIELD, WHICH THE
   * RULED ACT'S OWN GUARD CAUGHT BEFORE A ROW MOVED.
   *
   * It asked whether EVERY key a field answers to is unique, and disqualified
   * the field entirely if any one was shared. On the owner's form that is
   * catastrophic for no reason: the 53 controls carry 53 tags but only **35
   * DISTINCT** ones. Their `fieldId`s are unique and EXACT (the re-issue
   * re-ingests the very artifact the certified version was compiled from), yet
   * every control with a shared tag was refused because a DIFFERENT key of
   * theirs was ambiguous.
   *
   * ⚠️ MEASURED ON THE CERTIFIED VERSION ITSELF (`18a7ae19`), NOT INFERRED —
   * and the first version of this comment got it wrong, which is why the
   * numbers are now written down with their query. **EIGHT** tags are shared,
   * not three: `plan`×5, `impression`×4, `patient_is_a_pleasant_age_...`×4,
   * `family_history`×3, `past_medical_history`×3, `past_surgical_history`×3,
   * `allergies`×2, `the_patient_medications_were_reviewed_an`×2. That is
   * **26 controls sharing a tag with a sibling**, of which **23** are among the
   * 43 `extraction` rows the act transfers.
   *
   *     18 IS THE SURPLUS (53 − 35), NOT A CONTROL COUNT. Both members of a
   *     shared pair are refused, not just the extra one — which is exactly the
   *     arithmetic the earlier sentence lost.
   *
   * And that is what reconciles the refusal: of the 43 extraction rows, 20 had
   * a unique tag and survived, 23 did not. The act planned **20** transfers
   * where the declaration said 43, and refused —
   * `TRANSFER_COUNT_MISMATCH expected 43 actual 20`. 43 − 23 = 20, exactly.
   *
   *     AMBIGUITY IS A PROPERTY OF A KEY, NOT OF A CONTROL. A shared tag makes
   *     THAT TAG useless for identifying anyone; it says nothing about whether
   *     the control's own `fieldId` names it exactly.
   *
   * The safety property is unchanged: a match still requires the MATCHED key to
   * be unique on both sides, and a certified row is still consumed once. What
   * changes is that a control is no longer punished for a key it did not use.
   */
  const keyIsUnique = (key: IdentityKey, counts: Map<IdentityKey, number>): boolean =>
    counts.get(key) === 1;

  const sourceCounts = sourceIr ? countKeys(sourceIr.fields) : new Map<IdentityKey, number>();
  const targetCounts = countKeys(target.fields);

  const oldByIdentity = new Map<IdentityKey, string>();
  if (sourceIr) {
    for (const field of sourceIr.fields) {
      for (const pair of identityKeyPairs(field)) {
        // Only an UNAMBIGUOUS key carries an identity. A shared key names no one
        // control, so it is simply not registered; the field's other keys still
        // are.
        if (!keyIsUnique(pair.ambiguity, sourceCounts)) continue;
        oldByIdentity.set(pair.match, field.fieldId);
      }
    }
  }

  const transferred: Array<{ fieldId: string; fromFieldId: string; mapping: SemanticMapping }> = [];
  const reproposed: string[] = [];
  // ⚠️ CONSUMED ONCE. Belt to the braces above: even if both uniqueness checks
  // were somehow satisfied, one certified disposition can be claimed by exactly
  // one control. Two controls wearing one clinical meaning is the failure this
  // whole guard exists to prevent, and it costs one Set to make impossible.
  const consumed = new Set<string>();

  for (const field of target.fields) {
    let fromFieldId: string | undefined;
    let mapping: SemanticMapping | undefined;
    for (const pair of identityKeyPairs(field)) {
      // ambiguous on the target side: several controls here answer to this key,
      // so THIS key cannot claim a disposition. Another key of this field may
      // still be able to.
      if (!keyIsUnique(pair.ambiguity, targetCounts)) continue;
      const candidate = oldByIdentity.get(pair.match);
      if (candidate === undefined || consumed.has(candidate)) continue;
      const found = certifiedByFieldId.get(candidate);
      if (found) {
        fromFieldId = candidate;
        mapping = found;
        break;
      }
    }
    if (!fromFieldId || !mapping) {
      reproposed.push(field.fieldId);
      continue;
    }
    consumed.add(fromFieldId);
    // ⚠️ THE DISPOSITION IS RE-KEYED TO THE NEW FIELD ID AND OTHERWISE CARRIED
    // WHOLE. Every column moves — `conceptScope` and `unmentionedPolicy`
    // included — because a hand-rolled subset already erased a ruled `omit` on
    // a live certified row once. `fromPersistedMapping` is the one projector;
    // this must never grow a second.
    transferred.push({ fieldId: field.fieldId, fromFieldId, mapping: { ...mapping, fieldId: field.fieldId } });
  }

  return { transferred, reproposed };
}

