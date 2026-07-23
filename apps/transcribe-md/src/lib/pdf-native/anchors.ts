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

  const anchors: PdfFillAnchor[] = [];
  for (const { spec, item } of located) {
    const pageWidth = pageW[item.page] ?? 612;
    const size = Math.max(8, Math.min(item.height || 11, 14));

    if (spec.kind === 'inline') {
      // Fill to the right of the label, same baseline row.
      const x = item.x + item.width + 6;
      anchors.push({
        key: spec.key,
        label: spec.label,
        page: item.page,
        x,
        yTop: item.y + size, // one line tall, centered on the label row
        yBottom: item.y - 2,
        width: Math.max(40, pageWidth - x - rightMargin),
        fontSize: size,
      });
    } else {
      // Block: fill below, down to the next located label on the same page, or
      // the page bottom margin.
      const below = located
        .filter((o) => o.item.page === item.page && o.item.y < item.y - 1)
        .map((o) => o.item.y)
        .sort((a, b) => b - a)[0];
      const yBottom = (below ?? bottomMargin) + 4;
      anchors.push({
        key: spec.key,
        label: spec.label,
        page: item.page,
        x: item.x,
        yTop: item.y - size * 1.2, // start just below the label
        yBottom,
        width: Math.max(40, pageWidth - item.x - rightMargin),
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
