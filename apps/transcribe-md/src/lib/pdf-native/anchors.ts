// ============================================================================
// PDF anchor extraction (feat/pdf-native-fill, 2026-07-23).
// ----------------------------------------------------------------------------
// Reads the template PDF's TEXT LAYER (via unpdf's pdfjs document proxy) and
// maps each parsed label → its (x,y) position + the blank region to fill
// (bounded below/beside by the next label). Deterministic; runs once at
// certify time; the result is stored + re-derivable, never client-trusted.
//
// Two region shapes:
//  - 'block'  (section headings, e.g. PROCEDURE:): fill the space BELOW the
//    label, down to the next label/anchor or the page bottom margin.
//  - 'inline' (short header fields, e.g. PATIENT NAME:): fill the space to the
//    RIGHT of the label on the same line, to the next column/right margin.
// ============================================================================
import type { PdfFillAnchor } from './fill-engine';

/** A label to locate, with its intended region shape. */
export interface AnchorLabelSpec {
  key: string;
  /** The label text as it appears on the form (matched case-insensitively,
   *  whitespace-normalized; a trailing colon is optional). */
  label: string;
  kind: 'block' | 'inline';
}

interface PlacedItem {
  str: string;
  x: number;
  y: number;
  width: number;
  height: number; // font size ≈ transform[3]
  page: number;
}

/** Minimal shape of the pdfjs document proxy unpdf returns. */
interface PdfjsProxy {
  numPages: number;
  getPage(n: number): Promise<{
    getViewport(o: { scale: number }): { width: number; height: number };
    getTextContent(): Promise<{ items: Array<{ str: string; transform: number[]; width: number; height: number }> }>;
  }>;
}

const norm = (s: string): string => s.toLowerCase().replace(/\s+/g, ' ').replace(/:\s*$/, '').trim();

/** Flatten every text item across pages into positioned tokens. */
async function placedItems(proxy: PdfjsProxy): Promise<{ items: PlacedItem[]; pageW: number[] }> {
  const items: PlacedItem[] = [];
  const pageW: number[] = [];
  for (let p = 1; p <= proxy.numPages; p++) {
    const page = await proxy.getPage(p);
    const vp = page.getViewport({ scale: 1 });
    pageW[p - 1] = vp.width;
    const content = await page.getTextContent();
    for (const it of content.items) {
      if (!it.str || !it.str.trim()) continue;
      const t = it.transform; // [a,b,c,d,e,f]
      items.push({ str: it.str, x: t[4], y: t[5], width: it.width, height: Math.abs(t[3]) || it.height, page: p - 1 });
    }
  }
  return { items, pageW };
}

/** Find the label's leading item. Matches a single item, or a run of adjacent
 *  same-line items whose concatenation starts with the label (labels can be
 *  split across text items). Returns the leftmost/top item of the match. */
function findLabel(items: PlacedItem[], label: string): PlacedItem | null {
  const target = norm(label);
  // Group by (page, rounded y) into lines, left-to-right.
  const byLine = new Map<string, PlacedItem[]>();
  for (const it of items) {
    const k = `${it.page}:${Math.round(it.y)}`;
    (byLine.get(k) ?? byLine.set(k, []).get(k)!).push(it);
  }
  for (const line of byLine.values()) {
    line.sort((a, b) => a.x - b.x);
    for (let i = 0; i < line.length; i++) {
      let acc = '';
      for (let j = i; j < line.length && acc.length <= target.length + 4; j++) {
        acc = norm(`${acc} ${line[j].str}`);
        if (acc === target || acc.startsWith(target)) return line[i];
      }
    }
  }
  return null;
}

/**
 * Extract fill anchors for the given labels. `rightMargin`/`bottomMargin` bound
 * the regions; `lineGap` sets the vertical start below a block label.
 */
export async function extractPdfAnchors(
  proxy: PdfjsProxy,
  specs: readonly AnchorLabelSpec[],
  opts: { rightMargin?: number; bottomMargin?: number } = {}
): Promise<PdfFillAnchor[]> {
  const { items, pageW } = await placedItems(proxy);
  const rightMargin = opts.rightMargin ?? 54;
  const bottomMargin = opts.bottomMargin ?? 40;

  // Locate each label.
  const located = specs
    .map((s) => ({ spec: s, item: findLabel(items, s.label) }))
    .filter((l): l is { spec: AnchorLabelSpec; item: PlacedItem } => l.item !== null);

  // The nearest FORM INK below a y on a page — a block region must stop above it
  // (the next section label OR the form's own footer, e.g. "Electronically
  // Signed -" / "DD:" / "DT:"), so fill text never overlaps his printed ink.
  const nearestInkYBelow = (page: number, y: number): number | undefined =>
    items
      .filter((it) => it.page === page && it.y < y - 2)
      .map((it) => it.y)
      .sort((a, b) => b - a)[0];
  const INK_CLEAR = 14; // vertical clearance above the next ink (≈1.2 line @12pt)

  const anchors: PdfFillAnchor[] = [];
  for (const { spec, item } of located) {
    const pageWidth = pageW[item.page] ?? 612;
    const size = Math.max(8, Math.min(item.height || 11, 12));
    const firstLineX = item.x + item.width + 6; // just past the printed label
    const rightEdge = pageWidth - rightMargin;

    if (spec.kind === 'inline') {
      // One-line region to the RIGHT of the label (header fields).
      anchors.push({
        key: spec.key,
        label: spec.label,
        page: item.page,
        yTop: item.y,
        yBottom: item.y - size * 1.2,
        firstLineX,
        wrapX: firstLineX,
        rightEdge,
        fontSize: size,
      });
    } else {
      // Block: first line right of the label, wrapping BELOW at the label's left
      // edge, down to a clear gap above the next FORM INK (next label or footer).
      const inkY = nearestInkYBelow(item.page, item.y);
      const yBottom = inkY !== undefined ? inkY + INK_CLEAR : bottomMargin;
      anchors.push({
        key: spec.key,
        label: spec.label,
        page: item.page,
        yTop: item.y,
        yBottom,
        firstLineX,
        wrapX: item.x,
        rightEdge,
        fontSize: size,
      });
    }
  }
  return anchors;
}

/** Which specs were NOT found on the page — surfaced so certify can warn the
 *  doctor a region didn't anchor (never a silent drop). */
export async function missingAnchors(
  proxy: PdfjsProxy,
  specs: readonly AnchorLabelSpec[]
): Promise<string[]> {
  const { items } = await placedItems(proxy);
  return specs.filter((s) => findLabel(items, s.label) === null).map((s) => s.key);
}
