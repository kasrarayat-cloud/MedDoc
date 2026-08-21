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
