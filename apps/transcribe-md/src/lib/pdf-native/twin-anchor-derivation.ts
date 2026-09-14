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
//     has no locatable label, so it is placed at its numbered MARKER. The twin
//     derived one Fill-in field per marker in READING ORDER, so the Nth Fill-in
//     field (by displayOrder) is the Nth bare marker (by reading order). The zip
//     is order-for-order; a count mismatch leaves the surplus UNLOCATABLE.
//
// A field that cannot be located (a label absent from the page, or a Fill-in
// with no matching marker) is returned in `unlocatable`. The caller treats a
// certified-twin field it cannot place as a fallback trigger (ruling #322: "a
// control with no anchor" → the structural styled render), so no clinical value
// is ever drawn in the wrong place or silently dropped.
// ============================================================================
import { extractPdfAnchors, type AnchorLabelSpec } from './anchors';
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

/** Minimal pdfjs proxy shape (same as anchors.ts consumes). */
interface PdfjsProxy {
  numPages: number;
  getPage(n: number): Promise<{
    getViewport(o: { scale: number }): { width: number; height: number };
    getTextContent(): Promise<{
      items: Array<{ str: string; transform: number[]; width: number; height: number }>;
    }>;
  }>;
}

/** A bare list/enumeration marker that is the WHOLE token — `1.`, `2)`, `3`,
 *  `•`, `-`, a checkbox. Mirrors S2's PDF_MARKER_ONLY_RE (pdf-to-prose-docx):
 *  the numbered fill SLOTS of an operative note. Trailing text disqualifies it
 *  (that is a labelled item like "1. Chief Complaint:", located by label). */
const MARKER_ONLY_RE = /^(?:\(?\d{1,2}[.)]?|[a-z][.)]|[ivx]{1,4}[.)]|[•·▪◦‣*+–—-]|[☐☑☒])$/i;

const norm = (s: string): string => s.toLowerCase().replace(/\s+/g, ' ').replace(/:\s*$/, '').trim();

/** Is this label a same-line ("inline") fill, or a below-the-label ("block")
 *  one? The twin's fields are label/marker fill-ins (value beside the label), so
 *  a colon label or a marker is inline; a bare section heading with no colon is
 *  block (its value flows beneath). Deterministic, label-only. */
function anchorKind(label: string): 'inline' | 'block' {
  const raw = label.trim();
  if (raw === FILL_IN_LABEL) return 'inline';
  if (/[:：]\s*$/.test(raw)) return 'inline';
  return 'block';
}

interface PlacedItem {
  str: string;
  x: number;
  y: number;
  width: number;
  height: number;
  page: number;
}

/** Flatten positioned text tokens across pages (same transform reading as
 *  anchors.ts::placedItems, kept local so this module owns its marker scan). */
async function placedItems(proxy: PdfjsProxy): Promise<{ items: PlacedItem[]; pageW: number[] }> {
  const items: PlacedItem[] = [];
  const pageW: number[] = [];
  for (let p = 1; p <= proxy.numPages; p += 1) {
    const page = await proxy.getPage(p);
    pageW[p - 1] = page.getViewport({ scale: 1 }).width;
    const content = await page.getTextContent();
    for (const it of content.items) {
      if (!it.str || !it.str.trim()) continue;
      const t = it.transform;
      items.push({
        str: it.str,
        x: t[4],
        y: t[5],
        width: it.width,
        height: Math.abs(t[3]) || it.height,
        page: p - 1,
      });
    }
  }
  return { items, pageW };
}

/** Bare numbered/blank markers, in READING ORDER (page, then y descending,
 *  then x ascending). One per Fill-in slot the twin derived. */
function markersInReadingOrder(items: PlacedItem[]): PlacedItem[] {
  return items
    .filter((it) => MARKER_ONLY_RE.test(it.str.trim()))
    .sort((a, b) => a.page - b.page || b.y - a.y || a.x - b.x);
}

export interface TwinAnchorResult {
  /** One anchor per twin field that could be located, keyed by `fieldId`. */
  anchors: PdfFillAnchor[];
  /** fieldIds that could NOT be located (label absent / no matching marker). */
  unlocatable: string[];
}

/**
 * Re-derive pdf-native anchors from the twin's fields. PURE (reads only the
 * proxy). Anchor `key` is the twin `fieldId`, so the value bridge is 1:1.
 */
export async function deriveTwinAnchors(
  proxy: PdfjsProxy,
  fields: readonly TwinAnchorField[],
): Promise<TwinAnchorResult> {
  const ordered = [...fields].sort((a, b) => a.displayOrder - b.displayOrder);
  const labelled = ordered.filter((f) => norm(f.label) !== norm(FILL_IN_LABEL));
  const slots = ordered.filter((f) => norm(f.label) === norm(FILL_IN_LABEL));

  // 1) LABELLED fields — locate each by its label (existing, tested path). A
  //    label that appears more than once in `fields` would collide on key, but
  //    the twin's fieldId is unique, so specs are unique by key.
  const specs: AnchorLabelSpec[] = labelled.map((f) => ({
    key: f.fieldId,
    label: f.label,
    kind: anchorKind(f.label),
  }));
  const labelledAnchors = await extractPdfAnchors(proxy, specs);
  const locatedKeys = new Set(labelledAnchors.map((a) => a.key));
  const unlocatable = labelled.filter((f) => !locatedKeys.has(f.fieldId)).map((f) => f.fieldId);

  // 2) NUMBERED SLOTS — zip the ordered Fill-in fields to the reading-order
  //    markers. Extra fields (more slots than markers) or extra markers are not
  //    forced: a slot with no marker is UNLOCATABLE (→ fallback), never guessed
  //    onto an unrelated marker.
  const { items, pageW } = await placedItems(proxy);
  const markers = markersInReadingOrder(items);
  const slotAnchors: PdfFillAnchor[] = [];
  slots.forEach((field, i) => {
    const marker = markers[i];
    if (!marker) {
      unlocatable.push(field.fieldId);
      return;
    }
    const pageWidth = pageW[marker.page] ?? 612;
    const size = Math.max(8, Math.min(marker.height || 11, 12));
    const firstLineX = marker.x + marker.width + 6; // just past the "1."
    slotAnchors.push({
      key: field.fieldId,
      label: `${FILL_IN_LABEL} ${i + 1}`,
      page: marker.page,
      yTop: marker.y,
      yBottom: marker.y - size * 1.2,
      firstLineX,
      wrapX: firstLineX,
      rightEdge: pageWidth - 54,
      fontSize: size,
    });
  });

  return { anchors: [...labelledAnchors, ...slotAnchors], unlocatable };
}
