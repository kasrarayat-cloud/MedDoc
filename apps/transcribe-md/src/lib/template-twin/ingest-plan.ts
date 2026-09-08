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
 * A field's IDENTITY — never its position.
 *
 * ⚠️ THE FIRST VERSION OF THIS KEY WAS `partName + path + ordinal + kind`, AND
 * A REFUTATION PASS PROVED IT CLINICALLY UNSAFE. Measured, by execution, on the
 * real 80-control document: insert ONE control at the top of the body and
 *
 *     transferred = 3,  paired with the same control = 0,  MIS-PAIRED = 3
 *
 * with every mis-paired row carrying `status: 'certified'`:
 *
 *     "ULTRASOUND TECHNOLOGIST"  <-  the certified concept of  "MACHINE"
 *     "MACHINE"                  <-  the certified concept of  "LOCATION"
 *     "LOCATION"                 <-  the certified concept of  "CLINICAL INDICATIONS"
 *
 * The cause is that BOTH components shift together: `path` is a SIBLING-INDEX
 * XPath (`compiler.ts:1742`) and `ordinal` is a DOCUMENT-WIDE counter
 * (`compiler.ts:103, 902, 1058, 1311`). So control N in the edited document
 * inherits exactly the key of control N-1 in the original, and the deletion
 * direction is symmetric.
 *
 * ⚠️ AND NOTHING DOWNSTREAM WOULD HAVE CAUGHT IT. The count is right — only the
 * pairing is wrong — so `expectTransferCount` passes. The row lands `CERTIFIED`,
 * so it never reaches a confirmation list. That is a control the doctor has
 * never seen, certified to print a different question's clinical value.
 *
 * ── SO POSITION IS GONE, AND ONLY TRUE IDENTITIES REMAIN ────────────────────
 * Measured on the same document, one control inserted:
 *
 *   key           usable   distinct   matched after insert
 *   sdtId         28/80    28/28      28    <- Word's own control id: STABLE
 *   tag            1/80     1/1        1
 *   alias          1/80     1/1        1
 *   label|kind    80/80    26/80      80    <- ⚠️ matches everything, pairs nothing
 *
 * `label|kind` is the trap twice over: it appears to match 80/80 while carrying
 * 26 distinct values, and this document's labels are mostly the literal
 * placeholder "Choose an item." — so two controls with the same label can mean
 * entirely different things, and a shifted neighbour matches just as well as the
 * real counterpart.
 *
 * **There is no key that is both universal and stable.** So the honest rule is:
 * transfer ONLY on a true identity, and re-propose everything else.
 *
 *   1. the same `fieldId`  — identical bytes, which is the re-issue act exactly
 *   2. the same `sdtId`    — Word persists it across edits; unique where present
 *
 * A field with neither re-proposes. That is a smaller transfer than a positional
 * key would claim, and it is the only version that cannot hand one control's
 * clinical meaning to another.
 */
export type IdentityKey = string & { readonly __brand: 'IdentityKey' };

/**
 * The identities this field can be recognised by, strongest first. A field may
 * offer more than one; a match on ANY of them is a match.
 *
 * ⚠️ IT RETURNS A LIST RATHER THAN ONE STRING BECAUSE THE TWO IDENTITIES HAVE
 * DIFFERENT COVERAGE — `fieldId` is universal but survives only identical bytes,
 * `sdtId` survives edits but exists on 28 of 80. Collapsing them into a single
 * key would mean choosing which case to serve, and the ruling asks for both.
 */
export function identityKeys(field: TemplateField): IdentityKey[] {
  const keys: IdentityKey[] = [`fid\u0000${field.fieldId}` as IdentityKey];
  const sdtId = field.rendererBinding.sdtId;
  // ⚠️ `kind` RIDES ALONG WITH `sdtId`. A content control that Word kept the id
  // of but the doctor changed from a text box to a dropdown is a different
  // question with the same name, and its certified disposition — expectedDataType,
  // allowedOptions, polarity — no longer describes it.
  if (sdtId !== null && sdtId !== '') {
    // ⚠️ `partName` IS PART OF THE IDENTITY, AND LEAVING IT OUT WAS A DEFECT.
    // The compiler walks the body, then every header, then every footer into
    // ONE field list with no id-uniqueness check across parts, and `w:id` is
    // only unique within a part. Measured: a body control and a letterhead
    // control sharing `w:id 201` produced ONE identity, and the letterhead
    // inherited the body's certified CLINICAL concept — with nothing inserted,
    // deleted, moved or reordered. `partName` is already an input to `fieldId`'s
    // own hash (compiler.ts:885); dropping it from the key that has to survive a
    // byte change was the asymmetry.
    keys.push(`sdt\u0000${field.rendererBinding.partName}\u0000${sdtId}\u0000${field.kind}` as IdentityKey);
  }
  return keys;
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
  const countKeys = (fields: ReadonlyArray<TemplateField>): Map<IdentityKey, number> => {
    const counts = new Map<IdentityKey, number>();
    for (const field of fields) {
      for (const key of identityKeys(field)) counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return counts;
  };

  const sourceCounts = sourceIr ? countKeys(sourceIr.fields) : new Map<IdentityKey, number>();
  const targetCounts = countKeys(target.fields);

  const oldByIdentity = new Map<IdentityKey, string>();
  if (sourceIr) {
    for (const field of sourceIr.fields) {
      for (const key of identityKeys(field)) {
        // ambiguous on the source side: two old controls answer to this key, so
        // it names no one control and must carry nothing.
        if (sourceCounts.get(key) !== 1) continue;
        oldByIdentity.set(key, field.fieldId);
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
    for (const key of identityKeys(field)) {
      // ambiguous on the target side: this control is one of several answering
      // to the key, so it cannot claim the disposition.
      if (targetCounts.get(key) !== 1) continue;
      const candidate = oldByIdentity.get(key);
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

