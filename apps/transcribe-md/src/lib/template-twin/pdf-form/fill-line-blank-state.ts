// ============================================================================
// UPLOAD-AND-CERTIFIED · S2 — the materialised fill-line is the field's BLANK
// STATE (owner ruling, 2026-09-14, following #320).
// ----------------------------------------------------------------------------
// #320 makes S2 derive a control by MATERIALISING an underscore run on the label
// line ("PATIENT NAME: ______"), which S1 detects and turns into a control
// inserted AFTER the underscores. The underscores then sat in the label run,
// OUTSIDE the control — so a FILLED twin showed BOTH: "PATIENT NAME: ______John".
//
// THE RULING: a materialised line is shown when the field is BLANK and REPLACED
// by the value when FILLED — never both. So this moves the materialised line OFF
// the label and INTO the control's content. The renderer clears a filled control
// by "replacing its whole w:sdtContent subtree" (certification-lifecycle.ts, the
// #164 fix), so the line is replaced by the value on fill, and an unfilled
// control still shows the line. This is exactly the shape the hand-built twins
// use (#317 colon-operative-note, the integration fixtures): "LABEL: " + a
// control whose content is replaced on fill — never a standalone run beside it.
//
// ⚠️ S2 ONLY. It runs on the twin S2 SYNTHESISED (a PDF has no original bytes to
// preserve), never on an S1 doctor-uploaded DOCX whose underscores are the
// doctor's own bytes (byte-preserved by deriveProseTwin invariant #1).
//
// ⚠️ SELF-VERIFYING. It returns null unless the transformed package still
// re-compiles to EXACTLY the same controls (the caller's keystone). A shape it
// does not recognise leaves `xml` unchanged → null → the caller keeps the
// untransformed twin. It can only ever REMOVE the cosmetic, never break a twin.
// ============================================================================
import JSZip from 'jszip';

/** The visible blank line an unfilled control shows. The renderer replaces the
 *  WHOLE sdtContent on fill, so this never coexists with a value. Underscores are
 *  recognised as FURNITURE, not a dictated value (ruling #316), so a blank field
 *  showing this line is a blank, not an undictated default. */
export const FILL_LINE_BLANK = '____________________';

/**
 * Relocate every materialised fill-line from the label run INTO its control's
 * blank content. PURE except the injected `verify` (the caller's re-compile
 * keystone). Returns the transformed bytes, or null to fall back to the
 * untransformed twin (unrecognised shape, or the transform changed the controls).
 */
export async function relocateFillLinesToBlankState(
  twinBytes: Uint8Array,
  expectedControls: number,
  verify: (bytes: Uint8Array, expected: number) => Promise<boolean>,
): Promise<Uint8Array | null> {
  let zip: JSZip;
  try {
    zip = await JSZip.loadAsync(twinBytes);
  } catch {
    return null;
  }
  const entry = zip.file('word/document.xml');
  if (!entry) return null;
  const xml = await entry.async('string');

  // 1. Strip the materialised underscore run that sits at the END of a label run
  //    IMMEDIATELY before a derived control — "LABEL: ______" → "LABEL: ". The
  //    lookahead pins it to a run that is directly followed by a `<w:sdt>`, so no
  //    other underscores (a divider line, a body run) are touched.
  let out = xml.replace(/_{2,}(?=<\/w:t><\/w:r><w:sdt\b)/g, '');
  // 2. Replace each derived control's blank content ("Enter X" / "Enter value")
  //    with the fill line, so an unfilled control SHOWS the line and a fill
  //    replaces the whole subtree with the value. Matches only the exact
  //    proseControlSdt content shape.
  out = out.replace(
    /(<w:sdtContent><w:r><w:t xml:space="preserve">)[^<]*(<\/w:t><\/w:r><\/w:sdtContent>)/g,
    `$1${FILL_LINE_BLANK}$2`,
  );
  if (out === xml) return null; // nothing matched — not the shape we own

  zip.file('word/document.xml', out);
  const bytes = await zip.generateAsync({ type: 'uint8array' });

  // The transform must not change the control count, the kinds, or add blocking
  // — it only moves furniture. If it does anything else, discard it.
  const ok = await verify(bytes, expectedControls);
  return ok ? bytes : null;
}
