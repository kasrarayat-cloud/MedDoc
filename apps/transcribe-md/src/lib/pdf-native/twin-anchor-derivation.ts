// ============================================================================
// UPLOAD-AND-CERTIFIED · S2-4 — re-derive the pdf-native anchors FROM the
// certified twin's fields (owner ruling #322, 2026-09-14).
// ----------------------------------------------------------------------------
// Before S2-4 the pdf-native anchors were located from the NOTE-TEMPLATE's
// section/header labels — a derivation that DISAGREES with the twin's fields
// (measured on the owner's colon form: 21 twin fields vs 12 anchors, only 7
// labels aligned). The owner's ruling: the TWIN decides WHAT fills, so the
// anchors are re-derived from the twin's OWN field list — one anchor per field,
// keyed by the field's `ttf_…` id, located at that field's position on the
// doctor's ORIGINAL PDF page. The twin's resolved value then fills its anchor
// 1:1 (see twin-value-bridge.ts).
//
// Two location strategies, because the S2 derivation itself uses two:
//   • a LABELLED field ("PATIENT NAME", "PROCEDURE", "DD (dictated)") is located
//     by its label in the PDF text layer — the existing `extractPdfAnchors`.
//   • a bare NUMBERED SLOT (a twin "Fill-in" field, from a `1.`/`2.`/`3.` line)
//     has no locatable label, so it is placed at its numbered MARKER.
//
// ⚠️ ONE READER OF "WHAT IS A MARKER", NOT TWO (adversarial pass, 2026-09-15).
// The twin's Fill-in fields were derived by S2 over RECONSTRUCTED LINES
// (`groupLineBoxes`): "1. Chief Complaint:" is ONE labelled line, never a bare
// marker. This module therefore reconstructs the SAME line boxes and applies
// S2's OWN `PDF_MARKER_ONLY_RE` — so a labelled numbered item is never mistaken
// for a slot, and the Nth Fill-in field (reading order) is the Nth bare-marker
// line (reading order). A first version scanned RAW pdfjs items with a broader
// regex and drifted, drawing Fill-in values onto labelled rows.
//
// A field that cannot be located UNIQUELY (a label absent, a label that appears
// more than once so its position is ambiguous, or a Fill-in with no matching
// marker) is returned in `unlocatable`. The caller treats a certified-twin field
// it cannot place as a fallback trigger (ruling #322), so no clinical value is
// ever drawn in the wrong place or silently dropped.
// ============================================================================
import {
  groupLineBoxes,
  annotateAffordances,
  PDF_MARKER_ONLY_RE,
  type PlacedItem as GeomItem,
} from '@/lib/template-twin/pdf-form/pdf-to-prose-docx';
import { extractRuleSegments } from '@/lib/template-twin/pdf-form/pdf-geometry';
import { classifyParagraph } from '@/lib/template-twin/prose-form/derive-prose-twin';
import type { PdfFillAnchor } from './fill-engine';

/** The generic label S2 gives a bare numbered/blank slot (derive-prose-twin). */
export const FILL_IN_LABEL = 'Fill-in';

/** A twin field, reduced to what anchor derivation needs. `label` is the field
 *  definition's originalLabel; `displayOrder` is its position in the compiled
 *  twin (reading order). */
export interface TwinAnchorField {
  fieldId: string;
  label: string;
  displayOrder: number;
}

interface PdfjsProxy {
  numPages: number;
  getPage(n: number): Promise<{
    getViewport(o: { scale: number }): { width: number; height: number };
    getTextContent(): Promise<{
      items: Array<{ str: string; transform: number[]; width: number; height: number }>;
    }>;
  }>;
}

const norm = (s: string): string => s.toLowerCase().replace(/\s+/g, ' ').replace(/:\s*$/, '').trim();

/** Positioned tokens (S2's `PlacedItem` shape) + per-page width. */
async function readItems(proxy: PdfjsProxy): Promise<{ items: GeomItem[]; pageW: number[] }> {
  const items: GeomItem[] = [];
  const pageW: number[] = [];
  for (let p = 1; p <= proxy.numPages; p += 1) {
    const page = await proxy.getPage(p);
    pageW[p - 1] = page.getViewport({ scale: 1 }).width;
    const content = await page.getTextContent();
    for (const it of content.items) {
      if (!it.str || !it.str.trim()) continue;
      const t = it.transform;
      items.push({ str: it.str, x: t[4], y: t[5], height: Math.abs(t[3]) || it.height, page: p - 1 });
    }
  }
  return { items, pageW };
}

export interface TwinAnchorResult {
  /** One anchor per twin field that could be located, keyed by `fieldId`. */
  anchors: PdfFillAnchor[];
  /** fieldIds that could NOT be located uniquely (absent / ambiguous / no marker). */
  unlocatable: string[];
}

/** One reconstructed line the S1 pipeline classified as a field, with its box. */
interface FieldBox {
  box: { text: string; page: number; y: number; x0: number; x1: number; height: number };
  alias: string;
  kind: 'label' | 'blank';
}

/**
 * Re-derive pdf-native anchors from the twin's fields. PURE (reads only the
 * proxy). Anchor `key` is the twin `fieldId`, so the value bridge is 1:1.
 *
 * ⚠️ ONE READER OF "WHAT IS A FIELD" (four adversarial passes, 2026-09-15). Both
 * LABELLED and BLANK fields are located by running the SAME S1 pipeline the twin
 * was compiled with — groupLineBoxes → annotateAffordances → classifyParagraph —
 * over the doctor's page, then matching the twin's fields to the classified boxes
 * by EXACT alias (labels) and reading ORDER (blank slots). This replaced
 * `extractPdfAnchors`/`findLabel`, which matched a label by PREFIX + first
 * occurrence and drew "DATE" onto an earlier "DATE OF BIRTH:" line. Anything the
 * one-reader match cannot resolve UNIQUELY and UNAMBIGUOUSLY is unlocatable → the
 * caller falls back to the styled render, never a value on a guessed line.
 */
export async function deriveTwinAnchors(
  proxy: PdfjsProxy,
  fields: readonly TwinAnchorField[],
): Promise<TwinAnchorResult> {
  const ordered = [...fields].sort((a, b) => a.displayOrder - b.displayOrder);
  const unlocatable: string[] = [];

  // Run the SAME pipeline S1 used to mint the twin's fields.
  const segments = await extractRuleSegments(proxy as never).catch(() => []);
  const { items, pageW } = await readItems(proxy);
  const boxes = groupLineBoxes(items);
  const annotated = annotateAffordances(boxes, segments, (page) => pageW[page] ?? 612);
  const fieldBoxes: FieldBox[] = [];
  boxes.forEach((box, i) => {
    const cls = classifyParagraph(annotated[i]);
    if (cls) fieldBoxes.push({ box, alias: cls.alias, kind: cls.kind });
  });

  const anchors: PdfFillAnchor[] = [];

  // The nearest FORM INK below a y (a block region must stop above the next
  // label/footer) — mirrors anchors.ts::nearestInkYBelow.
  const nearestInkYBelow = (page: number, y: number): number | undefined =>
    items
      .filter((it) => it.page === page && it.y < y - 2)
      .map((it) => it.y)
      .sort((a, b) => b - a)[0];
  const INK_CLEAR = 14;

  // ⚠️ INLINE vs BLOCK IS DECIDED FROM THE RAW BOX TEXT, NOT THE ALIAS. The alias
  // from classifyParagraph has its trailing colon STRIPPED, so testing the alias
  // for a colon made the inline branch DEAD and forced every labelled field onto
  // the block path — whose nearestInkYBelow floor INVERTS when the next line is
  // <INK_CLEAR below, silently dropping the value (adversarial pass, 2026-09-15).
  // A colon in the raw line means the value fills to the RIGHT (a header field);
  // a colon-less label fills BELOW (a section heading). And a block region with
  // no room (inverted / < one line) returns null → the field is UNLOCATABLE → the
  // caller falls back to the styled render, never a silent drop.
  const anchorForLabel = (fieldId: string, fb: FieldBox): PdfFillAnchor | null => {
    const pageWidth = pageW[fb.box.page] ?? 612;
    const size = Math.max(8, Math.min(fb.box.height || 11, 12));
    const firstLineX = fb.box.x1 + 6; // just past the printed label
    const rightEdge = pageWidth - 54;
    if (/[:：]/.test(fb.box.text)) {
      // Inline (header field): STRICTLY one line to the right of the label. ⚠️ A
      // 1pt-tall region so capacity() is 1 for EVERY font size (a taller region
      // makes capacity() return 2 via its +1, and the shrink-to-fit loop grows it
      // further — a wrapping value then drew a 2nd line one row DOWN, over the
      // next form row; adversarial pass, 2026-09-15). A value too long for one
      // line overflows to the continuation page, never onto the next row.
      return { key: fieldId, label: fb.alias, page: fb.box.page, yTop: fb.box.y, yBottom: fb.box.y - 1, firstLineX, wrapX: firstLineX, rightEdge, fontSize: size };
    }
    const inkY = nearestInkYBelow(fb.box.page, fb.box.y);
    const yBottom = inkY !== undefined ? inkY + INK_CLEAR : 40;
    if (fb.box.y - yBottom < size) return null; // no room below → unlocatable (fallback)
    return { key: fieldId, label: fb.alias, page: fb.box.page, yTop: fb.box.y, yBottom, firstLineX, wrapX: fb.box.x0, rightEdge, fontSize: size };
  };

  // 1) LABELLED fields — match to a classified 'label' box by EXACT alias. An
  //    alias that matches ZERO or MORE THAN ONE box (a duplicate label, or a
  //    label that is not on the page) is ambiguous → unlocatable, never guessed.
  const labelBoxes = fieldBoxes.filter((fb) => fb.kind === 'label');
  const labelled = ordered.filter((f) => norm(f.label) !== norm(FILL_IN_LABEL));
  for (const field of labelled) {
    const matches = labelBoxes.filter((fb) => norm(fb.alias) === norm(field.label));
    const anchor = matches.length === 1 ? anchorForLabel(field.fieldId, matches[0]) : null;
    if (anchor) anchors.push(anchor);
    else unlocatable.push(field.fieldId);
  }

  // 2) BLANK SLOTS — the 'blank'-classified boxes in reading order are the twin's
  //    exact Fill-in set (same count + order; verified). ⚠️ PLACEMENT GUARD: the
  //    box geometry is the RAW line, so the value's start is unambiguous only for
  //    a bare MARKER ("1." → value to its right); a raw underscore blank has its
  //    box right-edge PAST the blank. If counts disagree OR any blank is not a
  //    bare marker, EVERY Fill-in falls back to the styled render (the proper fix
  //    for underscore blanks is a compile-time stored position, future S2). The
  //    owner's colon form (6 bare markers == 6 Fill-ins) zips exactly.
  const blankBoxes = fieldBoxes.filter((fb) => fb.kind === 'blank');
  const slots = ordered.filter((f) => norm(f.label) === norm(FILL_IN_LABEL));
  const placeable = blankBoxes.length === slots.length && blankBoxes.every((fb) => PDF_MARKER_ONLY_RE.test(fb.box.text));
  if (!placeable) {
    for (const field of slots) unlocatable.push(field.fieldId);
  } else {
    slots.forEach((field, i) => {
      const { box } = blankBoxes[i];
      const pageWidth = pageW[box.page] ?? 612;
      const size = Math.max(8, Math.min(box.height || 11, 12));
      const firstLineX = box.x1 + 6; // just past the bare marker "1."
      anchors.push({
        key: field.fieldId,
        label: `${FILL_IN_LABEL} ${i + 1}`,
        page: box.page,
        yTop: box.y,
        yBottom: box.y - size * 1.2,
        firstLineX,
        wrapX: firstLineX,
        rightEdge: pageWidth - 54,
        fontSize: size,
      });
    });
  }

  return { anchors, unlocatable };
}
