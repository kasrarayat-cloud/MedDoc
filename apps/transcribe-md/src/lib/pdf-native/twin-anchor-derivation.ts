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

/** Same-line ("inline") fill vs below-the-label ("block"). The twin's fields are
 *  label/marker fill-ins, so a colon label or a marker is inline; a bare section
 *  heading with no colon is block. Deterministic, label-only. */
function anchorKind(label: string): 'inline' | 'block' {
  const raw = label.trim();
  if (raw === FILL_IN_LABEL) return 'inline';
  if (/[:：]\s*$/.test(raw)) return 'inline';
  return 'block';
}

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
  const unlocatable: string[] = [];

  // 1) LABELLED fields — locate each by its label. ⚠️ A label that is NOT UNIQUE
  //    among the twin's fields is ambiguous: findLabel returns the FIRST match,
  //    so two same-label fields would BOTH draw onto the first occurrence and
  //    overprint (adversarial pass, 2026-09-15). Such fields are excluded from
  //    location → unlocatable → fallback, never a guessed overdraw.
  const labelCounts = new Map<string, number>();
  for (const f of labelled) labelCounts.set(norm(f.label), (labelCounts.get(norm(f.label)) ?? 0) + 1);
  const uniqueLabelled = labelled.filter((f) => (labelCounts.get(norm(f.label)) ?? 0) === 1);
  for (const f of labelled) {
    if ((labelCounts.get(norm(f.label)) ?? 0) !== 1) unlocatable.push(f.fieldId);
  }
  const specs: AnchorLabelSpec[] = uniqueLabelled.map((f) => ({
    key: f.fieldId,
    label: f.label,
    kind: anchorKind(f.label),
  }));
  const labelledAnchors = await extractPdfAnchors(proxy as never, specs);
  const locatedKeys = new Set(labelledAnchors.map((a) => a.key));
  for (const f of uniqueLabelled) if (!locatedKeys.has(f.fieldId)) unlocatable.push(f.fieldId);

  // 2) BLANK SLOTS — identified by S1's OWN predicate, not a re-detection.
  //    ⚠️ ONE READER OF "WHAT IS A FIELD" (adversarial pass ×3, 2026-09-15). A
  //    twin "Fill-in" field is exactly a line the S1 pipeline classifies 'blank'
  //    AFTER affordance annotation — a bare "1." whose blank was materialised, or
  //    a "1. ______" / "______" underscore blank. A marker-only regex drifted
  //    from that both ways (missed "1. ______", over-counted a no-affordance
  //    "3."), transposing clinical values. So this reconstructs the SAME line
  //    boxes, runs the SAME annotateAffordances + classifyParagraph, and takes
  //    the 'blank'-classified boxes in reading order — the twin's exact Fill-in
  //    set, same count AND same order.
  const segments = await extractRuleSegments(proxy as never).catch(() => []);
  const { items, pageW } = await readItems(proxy);
  const boxes = groupLineBoxes(items);
  const annotated = annotateAffordances(boxes, segments, (page) => pageW[page] ?? 612);
  const blankBoxes = boxes.filter((_, i) => classifyParagraph(annotated[i])?.kind === 'blank');

  // ⚠️ PLACEMENT GUARD. The box geometry is the RAW line, so the value's start is
  // unambiguous only for a bare MARKER ("1." → value to its right). A raw
  // underscore blank ("1. ______" / "______") has its box right-edge PAST the
  // blank, so the exact start is unknown from geometry alone — and a compile-time
  // stored position is the proper fix (future S2). Until then, if the counts
  // disagree (a divergence) OR any blank is not a bare marker (ambiguous start),
  // EVERY Fill-in field is left unlocatable and the caller falls back to the
  // styled render — never a value drawn on a guessed line. The owner's colon
  // form (6 bare markers == 6 Fill-ins) zips exactly.
  const slotAnchors: PdfFillAnchor[] = [];
  const placeable = blankBoxes.length === slots.length && blankBoxes.every((b) => PDF_MARKER_ONLY_RE.test(b.text));
  if (!placeable) {
    for (const field of slots) unlocatable.push(field.fieldId);
  } else {
    slots.forEach((field, i) => {
      const box = blankBoxes[i];
      const pageWidth = pageW[box.page] ?? 612;
      const size = Math.max(8, Math.min(box.height || 11, 12));
      const firstLineX = box.x1 + 6; // just past the bare marker "1."
      slotAnchors.push({
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

  return { anchors: [...labelledAnchors, ...slotAnchors], unlocatable };
}
