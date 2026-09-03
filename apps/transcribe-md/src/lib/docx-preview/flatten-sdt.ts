// ============================================================================
// FLATTEN CONTENT CONTROLS FOR PDF CONVERSION — AND ONLY FOR THAT.
// ----------------------------------------------------------------------------
// ⚠️ THE DEFECT THIS EXISTS FOR, MEASURED ON THE OWNER'S OWN VISIT. His signed
// export served byte-identical DOCX to Word and to the PDF converter. The DOCX
// carried 22 filled content controls and 7,603 visible characters. The PDF
// carried **0 of the 22** and 2,199 characters: every paragraph OUTSIDE a
// control rendered, every filled control rendered EMPTY. His words for it were
// "it changed my file again".
//
// So the doctor's deliverable — the thing he sends a referrer — had never once
// shown a filled value.
//
// ⚠️ AND THE CAUSE IS NOT OURS. The same emptiness reproduces on his BLANK
// uploaded form, untouched by any fill: 0 of 35 control texts render. Whatever
// this converter does with `w:sdt`, it did it before our renderer was involved.
//
// ── WHY FLATTENING, RATHER THAN A DIAGNOSIS ────────────────────────────────
// Four bisection harnesses were built to name the offending SDT sub-feature and
// FOUR WERE INVALIDATED BY THEIR OWN CONTROLS — synthetic pairs with no positive
// arm; a splice whose `indexOf('</w:sdt>')` closed the wrong tag when SDTs
// nest, which reported an empty `sdtPr` as fatal; and finally a result that
// contradicted the baseline outright. The honest position is a WORKAROUND with
// a clean measurement, not a diagnosis, and the LibreOffice question is FILED
// rather than closed — `DEPLOYMENT_RUNBOOK.md`, "the SDT rendering quirk".
//
// The argument for flattening is the one thing that held in EVERY trial:
//
//     PLAIN PARAGRAPH TEXT RENDERED, ALWAYS, IN EVERY EXPERIMENT.
//
// So the conversion input is made entirely of plain paragraph text. It cannot
// depend on which SDT sub-feature the converter drops, because there are no SDTs
// left in it.
//
// ── WHAT IT PRESERVES, AND WHAT IT COSTS ───────────────────────────────────
// It removes WRAPPERS ONLY. `w:sdtContent`'s children are kept verbatim and in
// order, so every run and every `w:t` survives byte-identical — measured on the
// owner's document: 79 `w:t` before, 79 after, 35 `w:sdt` before, 0 after, and
// the filled values went 0/22 -> 22/22 in the rendered PDF.
//
// ⚠️ THE COST, NAMED SO IT IS NOT DISCOVERED LATER: unwrapping removes the
// STRUCTURE that marks which text is a filled field. For a PDF that is correct —
// it is a RENDERING, not a data carrier — but anything that ever re-reads a
// generated PDF expecting controls will not find them. The DOCX remains the
// structured artifact; the PDF is presentation-only. That is a deliberate
// trade, and it is the reason this function is applied at the converter's input
// boundary and NOWHERE else: the bytes served to Word keep their controls.
// ============================================================================

/**
 * Unwrap every `w:sdt` in a WordprocessingML part, keeping `w:sdtContent`'s
 * children verbatim.
 *
 * ⚠️ IT WORKS INNERMOST-FIRST, BECAUSE CONTENT CONTROLS NEST. A regex that
 * pairs the first `<w:sdt>` with the first `</w:sdt>` closes the INNER control
 * and leaves an orphaned tag — which is exactly the bug that invalidated one of
 * this defect's bisection harnesses and made an empty `sdtPr` look fatal. An
 * innermost control is one whose next SDT-ish tag is its own close.
 *
 * `w:sdtPr` and `w:sdtEndPr` live outside `w:sdtContent` and are therefore
 * dropped with the wrapper, which is intended: they are the control's metadata,
 * not the doctor's text.
 */
export function flattenContentControls(xml: string): string {
  let out = xml;
  // A hard bound so a malformed part can never spin. Real documents are far
  // below it; the owner's is 35.
  const LIMIT = 10_000;
  for (let i = 0; i < LIMIT; i += 1) {
    const open = /<w:sdt(?:\s[^>]*)?>/g;
    let match: RegExpExecArray | null;
    let target: { start: number; end: number } | null = null;
    while ((match = open.exec(out)) !== null) {
      const after = out.slice(match.index + match[0].length);
      const nextOpen = after.search(/<w:sdt(?:\s[^>]*)?>/);
      const nextClose = after.indexOf('</w:sdt>');
      if (nextClose !== -1 && (nextOpen === -1 || nextClose < nextOpen)) {
        target = {
          start: match.index,
          end: match.index + match[0].length + nextClose + '</w:sdt>'.length,
        };
        break;
      }
    }
    if (!target) return out;
    const whole = out.slice(target.start, target.end);
    const content = /<w:sdtContent(?:\s[^>]*)?>([\s\S]*)<\/w:sdtContent>/.exec(whole);
    // ⚠️ A CONTROL WITH NO `w:sdtContent` CONTRIBUTES NOTHING, and that is the
    // correct reading rather than an error: there is no doctor text inside it.
    out = out.slice(0, target.start) + (content ? content[1]! : '') + out.slice(target.end);
  }
  throw new Error('flattenContentControls: did not converge');
}
