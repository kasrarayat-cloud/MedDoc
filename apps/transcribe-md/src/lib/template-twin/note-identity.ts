// ============================================================================
// THE NOTE A FILL RAN AGAINST — one derivation, both sides.
// ----------------------------------------------------------------------------
// ⚠️ WHY. A VERIFIED fill manifest used to be served forever, with no predicate
// tying it to the note. The worker filled from note v1, the doctor edited to v2,
// and the download was still v1 — and after signing, `native-export` refuses to
// recompute (`visit_not_eligible`), so the stored bytes and `soapFinal` could
// disagree permanently with NOTHING on any surface revealing it.
//
// Word carried this from the start; routing the PDF onto the same artifact is
// what made it visible. Found by the mandatory refutation pass over that change.
//
// ⚠️ ONE FUNCTION, BOTH SIDES — the writer stamps it and the reader recomputes
// it. Two independent renderings of "which note is this" is the same defect
// class #135 fixed for cell values, and it is why this lives here rather than
// being inlined at each site.
import { createHash } from 'node:crypto';

/**
 * Identity of the note text a fill ran against.
 *
 * Null in, null out: a visit with no note has no identity to prove, and the
 * caller must treat that as UNPROVABLE rather than as a match.
 */
export function noteIdentity(soapFinal: string | null | undefined): string | null {
  if (typeof soapFinal !== 'string' || soapFinal.length === 0) return null;
  return createHash('sha256').update(soapFinal, 'utf8').digest('hex');
}

/**
 * May a stored manifest be served for this visit's current note?
 *
 * ⚠️ FAIL-CLOSED ON EVERY UNPROVABLE CASE, and each one is distinct:
 *   · a manifest written before `noteSha256` existed  -> unprovable
 *   · a visit with no note                            -> unprovable
 *   · a mismatch                                      -> stale
 * All three decline. A "probably fine" here is a signed record that silently
 * disagrees with itself.
 */
export function manifestMatchesNote(
  manifestNoteSha256: string | null | undefined,
  soapFinal: string | null | undefined,
): { ok: boolean; reason: 'match' | 'manifest_note_unknown' | 'visit_note_absent' | 'note_changed' } {
  if (!manifestNoteSha256) return { ok: false, reason: 'manifest_note_unknown' };
  const current = noteIdentity(soapFinal);
  if (!current) return { ok: false, reason: 'visit_note_absent' };
  if (current !== manifestNoteSha256) return { ok: false, reason: 'note_changed' };
  return { ok: true, reason: 'match' };
}

// ============================================================================
// F24-S5 — THE OVERRIDE HALF OF THE BOUND IDENTITY.
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS EXISTS. `noteIdentity` is sha256(soapFinal) AND NOTHING ELSE, and
// a clinician's correction to a FORM CONTROL deliberately never touches
// `soapFinal`. `edit_form_control` is the first editor intent that changes the
// DOCUMENT without changing the NOTE — so every gate keyed on the note alone
// read `match` while the stored artifact was already out of date:
//
//   pre-sign preview (recomputes) -> the correction    ✓
//   GET /export/docx and /pdf     -> the stored bytes  ✗
//   sign -> freeze returns already_fresh -> the pre-override manifest, FOREVER
//
// That was measured, not read: the freeze was driven under a mocked prisma and
// returned `already_fresh` with `processTemplateTwinVisit` called 0 times.
//
// ⚠️ THE GATES ARE NOT LOOSENED TO FIX IT. Making a gate skip or tolerate an
// override would admit every stale manifest those gates exist to refuse. The
// BOUND IDENTITY widens instead: `noteSha256` keeps its exact meaning and no
// reader of it is re-interpreted, and a SIBLING carries the overlay state the
// fill actually ran against. A new override moves the sibling, the pair
// disagrees, the manifest reads STALE, and the recompute re-applies it.
//
// ⚠️ ONE DERIVATION, ALL CALLERS (#135). The writer stamps it and every reader
// recomputes it from this function. Two renderings of "which overrides is this"
// drift, and a drifted identity serves a stale document as fresh — which is the
// defect this module already exists to prevent for the note.
// ============================================================================

/**
 * The identity-bearing part of one stored override.
 *
 * ⚠️ THE ORDINAL IS THE VALUE, and `optionValue` is deliberately NOT here.
 * `optionValue` is denormalised for audit only; including it would make a
 * template recompile that merely re-words an option read as a changed
 * correction, forcing a re-fill that changes nothing.
 */
export interface OverrideIdentityMember {
  fieldId: string;
  selectedOptionOrdinal: number;
}

/**
 * Identity of the override SET a fill ran against.
 *
 * ⚠️ CANONICAL BY CONSTRUCTION — sorted by `fieldId`, so the hash cannot depend
 * on the order rows came back from the database. A `findMany` without an
 * `orderBy`, or a future index change, must not be able to move this value.
 */
export function overridesIdentity(
  overrides: readonly OverrideIdentityMember[],
): string {
  const canonical = [...overrides]
    .map((o) => [o.fieldId, o.selectedOptionOrdinal] as const)
    .sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  return createHash('sha256')
    .update(JSON.stringify(canonical), 'utf8')
    .digest('hex');
}

/**
 * The identity of "no overrides", precomputed.
 *
 * ⚠️ THIS IS WHAT A NULL SIBLING MEANS, AND IT IS PROVABLE RATHER THAN ASSUMED —
 * which is the whole reason it does not fail closed the way a null `noteSha256`
 * does. A null `noteSha256` means *we do not know which note this was*. A null
 * `overridesSha256` can only mean *this manifest predates the migration that
 * created `template_twin_field_overrides`*, and no override row can exist before
 * the table that holds it. So "no overrides existed when this was filled" is
 * true BY CONSTRUCTION, not inferred — ruling: legacy manifests are vacuously
 * fresh and are NEVER backfilled, because a backfilled identity would assert a
 * correspondence nobody verified.
 *
 * ⚠️ AND THIS IS NOT THE "NORMALISE AN IMPOSSIBLE VALUE" ANTIPATTERN, though it
 * has its shape. That rule forbids converting *"this instrument is broken"* into
 * a plausible number. Here the null carries a known, single meaning. The case
 * the rule warns about — a fill path that FORGOT to stamp the sibling, making
 * null mean "unknown" again — is closed separately, by the gate arm asserting
 * every newly written manifest carries a non-null sibling.
 */
export const EMPTY_OVERRIDES_SHA256: string = overridesIdentity([]);

export type DocumentFreshnessReason =
  | 'match'
  | 'manifest_note_unknown'
  | 'visit_note_absent'
  | 'note_changed'
  | 'overrides_changed';

/**
 * May a stored manifest be served for this visit's current NOTE **and** current
 * OVERRIDE SET?
 *
 * ⚠️ THE PAIR, NOT THE NOTE. This supersedes `manifestMatchesNote` at every gate
 * that decides whether a fill runs. `manifestMatchesNote` is kept and unchanged
 * because it still answers its own narrower question honestly — but a caller
 * that only asks it is asking about half the document.
 */
export function manifestMatchesDocument(input: {
  manifestNoteSha256: string | null | undefined;
  manifestOverridesSha256: string | null | undefined;
  soapFinal: string | null | undefined;
  currentOverrides: readonly OverrideIdentityMember[];
}): { ok: boolean; reason: DocumentFreshnessReason } {
  const note = manifestMatchesNote(input.manifestNoteSha256, input.soapFinal);
  if (!note.ok) return note as { ok: false; reason: DocumentFreshnessReason };
  const stamped = input.manifestOverridesSha256 ?? EMPTY_OVERRIDES_SHA256;
  if (stamped !== overridesIdentity(input.currentOverrides)) {
    return { ok: false, reason: 'overrides_changed' };
  }
  return { ok: true, reason: 'match' };
}
