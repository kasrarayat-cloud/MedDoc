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

/**
 * Every text carrier this codebase has been bitten by, used as a BACKSTOP only.
 *
 * ⚠️ IT IS NOT THE SAFETY ARGUMENT, AND IT MUST NOT BE READ AS ONE. Round two
 * of the refutation pass showed this list is three names out of the ~40 that
 * PRINT (`note-template-docx/compiler.ts`'s `CONTENT_CARRIERS`, a set that
 * exists because a Wingdings tick was measured surviving inside `w:rPr`). A
 * guard built on it would be blind to `w:sym`, `w:drawing`, `w:pict` and the
 * rest. Safety comes from deleting no content at all; this only catches a
 * wrapper pattern that has started matching something it should not.
 */
const TEXT_CARRIERS = /<w:(?:t|delText|instrText)(?:\s[^>]*)?>[\s\S]*?<\/w:(?:t|delText|instrText)>/g;

const carriers = (xml: string): string[] => xml.match(TEXT_CARRIERS) ?? [];

/**
 * The four wrapper tag forms, and NOTHING else.
 *
 * ⚠️ `(?![A-Za-z])` IS LOAD-BEARING TWICE OVER. It stops `<w:sdt` matching
 * `<w:sdtPr>`, `<w:sdtEndPr>` or `<w:sdtContent>` — the property blocks are
 * KEPT, and a pattern that ate them would be the exact defect this version
 * exists to remove.
 *
 * ⚠️ AND NO ATTRIBUTES ARE ADMITTED. Neither element takes an attribute in the
 * OOXML schema, and the real customer form is 56 of 56 bare — measured, not
 * assumed. Admitting them would mean `[^>]*` stopping at the FIRST `>`, so a
 * value containing `>` would leave the tail behind as character data: text
 * MANUFACTURED into a clinical document. An unrecognised form is left in place
 * and then caught by the survivor check below, which refuses the part.
 *
 * ⚠️ `\s*` IN THE CLOSING FORMS IS ALSO LOAD-BEARING. `</w:sdt >`, `<w:sdt\t>`
 * and `<w:sdtContent >` are legal XML, and an earlier version matched the
 * partner tag while leaving these — shipping malformed XML with no throw, so
 * the converter refused and the doctor got NO pdf at all.
 */
const WRAPPER_TAGS =
  /<w:sdt(?![A-Za-z])\s*\/?>|<\/w:sdt\s*>|<w:sdtContent(?![A-Za-z])\s*\/?>|<\/w:sdtContent\s*>/g;

/** The same forms, for asserting none survived. */
const ANY_WRAPPER =
  /<w:sdt(?![A-Za-z])|<\/w:sdt\s*>|<w:sdtContent(?![A-Za-z])|<\/w:sdtContent\s*>/;

/**
 * Unwrap every `w:sdt` in a WordprocessingML part by removing its wrapper TAGS.
 * Nothing else is touched: no subtree is selected, examined, or deleted.
 *
 * @throws when the part cannot be flattened safely — the caller
 * (`convertDocxToPdf`) catches and converts the ORIGINAL bytes. A hollow PDF is
 * the defect being fixed; a PDF missing a drug name is worse than either.
 */
export function flattenContentControls(xml: string): string {
  if (!xml.includes('<w:sdt')) return xml;

  const before = carriers(xml);
  const out = xml.replace(WRAPPER_TAGS, '');

  // ⚠️ A BACKSTOP, NOT THE GUARANTEE — see TEXT_CARRIERS. Content preservation
  // is a property of removing only tags. This fires if a wrapper pattern has
  // started matching something that is not a wrapper tag, and it compares the
  // ORDERED list BOTH ways, because a rule about faithfulness forbids removing
  // as well as manufacturing.
  //
  // ⚠️ AND NO INPUT CAN TRIP IT — SAID PLAINLY, BECAUSE DELETING IT REDS ZERO
  // ARMS AND A READER WILL EVENTUALLY NOTICE THAT. It is a CODE-CHANGE
  // detector, not an input detector: with tag-only removal there is no document
  // that reaches it, which is the point of the design. Its proof is a mutation,
  // recorded here rather than left to be rediscovered — widening WRAPPER_TAGS
  // to also match `<w:r>`/`<w:t>` makes it, and ONLY it, refuse:
  //     flattenContentControls: text carriers changed (1 -> 0)
  // If you are tempted to delete it because nothing exercises it, that mutation
  // is what you are removing.
  const after = carriers(out);
  if (after.length !== before.length || after.some((c, i) => c !== before[i])) {
    throw new Error(
      `flattenContentControls: text carriers changed (${before.length} -> ${after.length}); refusing to convert this part`,
    );
  }
  if (ANY_WRAPPER.test(out)) {
    throw new Error('flattenContentControls: a control wrapper survived flattening');
  }
  return out;
}
