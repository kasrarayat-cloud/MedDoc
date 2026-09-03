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
// ⚠️ AND THE CAUSE IS NOT OURS. The same emptiness reproduces on his BLANK
// uploaded form, untouched by any fill: on the real customer template only
// **1 of 28** control texts render — the single BLOCK-level one. Whatever this
// converter does with `w:sdt`, it did it before our renderer was involved. The
// LibreOffice question is FILED, not diagnosed: `DEPLOYMENT_RUNBOOK.md` §11.2.
//
// ── THE RULE THIS FILE OBEYS, AND WHY IT IS THE SECOND ATTEMPT ─────────────
//
//     REMOVE WRAPPER TAGS. NEVER SELECT A SUBTREE.
//
// ⚠️ THE FIRST VERSION SELECTED A SUBTREE AND DELETED A DRUG NAME. It located
// each control, captured `w:sdtContent`'s children, and replaced the whole
// control with that capture. Three demonstrated failures, all found by the
// mandatory refutation pass over the finished diff, all on this exact input
// shape family:
//
//   1 · A `w:sdt` may carry children AFTER `w:sdtContent`. Ruling #174 refuses
//       such a control at ADMISSION and KEEPS the doctor's text verbatim as
//       static content, so it reaches the served document. Selecting the
//       subtree threw the trailing run away:
//         <w:sdt>…<w:sdtContent><w:r><w:t>placeholder</w:t></w:r></w:sdtContent>
//                 <w:r><w:t>WARFARIN 5 MG DAILY</w:t></w:r></w:sdt>
//       rendered as `placeholder`. **The drug name was gone**, the output was
//       well-formed, nothing threw, so the fail-open never engaged, and the
//       PDF was a valid document with a medication missing.
//   2 · TWO `w:sdtContent` children (also a #174 shape) made the greedy capture
//       span from the first open to the LAST close, emitting an orphan
//       `</w:sdtContent>` and an unclosed `<w:sdtContent>`. Unparseable — so
//       the converter refused and the doctor got NO PDF where before they got
//       a hollow one.
//   3 · `<w:sdt />` — self-closing WITH a space — matched the opening-tag
//       pattern, and the splice ran to the enclosing control's close, deleting
//       `PATIENT ALLERGIC TO PENICILLIN`.
//
// Removing only the WRAPPER TAGS cannot do any of that. Nothing between tags is
// ever examined, chosen, or discarded, so no child can be dropped by a pairing
// mistake — the property holds by CONSTRUCTION rather than by a case analysis
// that has now been falsified three times. It is also nesting-agnostic (no
// pairing to get wrong) and single-pass, which retires the quadratic rescan the
// same pass measured at 34 seconds of blocked event loop on 5,000 controls.
//
// ── WHAT IT PRESERVES, AND WHAT IT COSTS ───────────────────────────────────
// `w:sdtPr` / `w:sdtEndPr` are the control's METADATA — alias, id, dropdown
// list items, placeholder reference — and they carry no rendered text, which is
// why they go with the wrapper. Everything else survives byte-for-byte.
//
// ⚠️ THE COST, NAMED SO IT IS NOT DISCOVERED LATER: unwrapping removes the
// STRUCTURE that marks which text is a filled field. For a PDF that is correct —
// it is a RENDERING, not a data carrier — but anything that ever re-reads a
// generated PDF expecting controls will not find them. The DOCX remains the
// structured artifact; the PDF is presentation-only. That is a deliberate
// trade, and it is why this runs at the converter's input boundary and NOWHERE
// else: the bytes served to Word keep their controls.
// ============================================================================

/** Every text carrier this codebase has been bitten by. Used as a TRIPWIRE. */
const TEXT_CARRIERS = /<w:(?:t|delText|instrText)(?:\s[^>]*)?>[\s\S]*?<\/w:(?:t|delText|instrText)>/g;

const carriers = (xml: string): string[] => xml.match(TEXT_CARRIERS) ?? [];

// Metadata subtrees. Self-closing forms are removed FIRST, so that by the time
// the paired form runs, every remaining `<w:sdtPr` provably has a partner —
// otherwise a lone `<w:sdtPr/>` would let the non-greedy match run on to some
// LATER `</w:sdtPr>` and swallow a doctor's paragraph on the way.
const SDT_PR_SELF = /<w:sdt(?:End)?Pr(?:\s[^>]*?)?\/>/g;
const SDT_PR_PAIR = /<w:sdtPr(?:\s[^>]*)?>[\s\S]*?<\/w:sdtPr>/g;
const SDT_ENDPR_PAIR = /<w:sdtEndPr(?:\s[^>]*)?>[\s\S]*?<\/w:sdtEndPr>/g;

// ⚠️ `[^>]*[^/]` IS LOAD-BEARING: it stops the OPEN patterns matching a
// self-closing `<w:sdt />`, which is defect 3 above. `<w:sdtContent>` is not
// matched by the `w:sdt` pattern either — the character after `sdt` is `C`,
// neither whitespace nor `>`.
const SDT_SELF = /<w:sdt(?:\s[^>]*?)?\/>/g;
const SDT_CONTENT_SELF = /<w:sdtContent(?:\s[^>]*?)?\/>/g;
const WRAPPER_TAGS = /<w:sdt(?:\s[^>]*[^/])?>|<\/w:sdt>|<w:sdtContent(?:\s[^>]*[^/])?>|<\/w:sdtContent>/g;

/**
 * Unwrap every `w:sdt` in a WordprocessingML part by deleting its wrapper tags
 * and metadata, leaving ALL other content exactly where it was.
 *
 * @throws when the part cannot be flattened safely — the caller
 * (`convertDocxToPdf`) catches and converts the ORIGINAL bytes. A hollow PDF is
 * the defect being fixed; a PDF missing a drug name is worse than either.
 */
export function flattenContentControls(xml: string): string {
  if (!xml.includes('<w:sdt')) return xml;

  const before = carriers(xml);

  let out = xml.replace(SDT_PR_SELF, '');

  // ⚠️ ADMIT ONLY WHAT YOU UNDERSTAND. An unbalanced metadata block is a shape
  // nobody here has characterised, and the non-greedy delete would silently
  // reach past it. Refuse the part instead — the original bytes still convert.
  const prOpens = (out.match(/<w:sdtPr(?:\s[^>]*)?>/g) ?? []).length;
  const prCloses = (out.match(/<\/w:sdtPr>/g) ?? []).length;
  const endOpens = (out.match(/<w:sdtEndPr(?:\s[^>]*)?>/g) ?? []).length;
  const endCloses = (out.match(/<\/w:sdtEndPr>/g) ?? []).length;
  if (prOpens !== prCloses || endOpens !== endCloses) {
    throw new Error(
      `flattenContentControls: unbalanced control metadata (sdtPr ${prOpens}/${prCloses}, sdtEndPr ${endOpens}/${endCloses})`,
    );
  }

  out = out.replace(SDT_PR_PAIR, '').replace(SDT_ENDPR_PAIR, '');
  // An empty control carries nothing; the tag itself is all there is to remove.
  out = out.replace(SDT_SELF, '').replace(SDT_CONTENT_SELF, '');
  out = out.replace(WRAPPER_TAGS, '');

  // ⚠️ THE TRIPWIRE, NOT THE GUARANTEE. Content preservation is a property of
  // removing only tags; this catches the case where one of those patterns
  // matches something that is NOT a wrapper tag. It compares the ORDERED list
  // both ways, because a rule about faithfulness forbids REMOVING as well as
  // manufacturing, and a subset check only ever constrains one direction.
  const after = carriers(out);
  if (after.length !== before.length || after.some((c, i) => c !== before[i])) {
    throw new Error(
      `flattenContentControls: text carriers changed (${before.length} -> ${after.length}); refusing to convert this part`,
    );
  }
  // Nothing may survive that would put us back where we started.
  if (/<w:sdt[ />]|<\/w:sdt>/.test(out)) {
    throw new Error('flattenContentControls: a control survived flattening');
  }
  return out;
}
