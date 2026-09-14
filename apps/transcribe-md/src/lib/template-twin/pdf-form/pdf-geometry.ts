// ============================================================================
// UPLOAD-AND-CERTIFIED · S2 — DRAWN RULE-LINE geometry (ruling #320, branch (b)).
// ----------------------------------------------------------------------------
// A PDF form can draw a fill blank as a VECTOR line — a Word field with a
// bottom border, an underline shape — that carries no text-layer character. This
// reads the page's operator list and returns the VISIBLE horizontal segments in
// page space, so the affordance annotator (pdf-to-prose-docx) can pair a segment
// to the label above/beside it and derive a control (ruling #320 (1)(b)).
//
// ⚠️ FAIL-SAFE BY CONSTRUCTION. The operator-list decode is pdfjs-internal and
// version-sensitive, and it is NOT on the critical path: branch (a) (colon/number
// + empty writable span) already recovers a text-labelled form with no visible
// lines — which is exactly the owner's file (46 of 48 segments are WHITE
// field-box backgrounds). So ANY failure here returns [] and the annotator falls
// back to branch (a). It NEVER throws and NEVER blocks an upload.
//
// ⚠️ ONLY VISIBLE (INKED) HORIZONTAL SEGMENTS. A near-white stroke/fill is
// invisible on paper and is NOT a rule line — it is the field-box shading this
// very form uses. We keep only segments whose colour is meaningfully darker than
// the page, and only near-horizontal runs of real length. Page-frame borders are
// not filtered here (they carry no label) — the annotator's label-pairing drops
// them because no label sits on their row.
// ============================================================================

/** A visible horizontal rule segment, in page space (origin bottom-left, y up —
 *  the same space `pdf-to-prose-docx` PlacedItem `y` lives in). */
export interface RuleSegment {
  page: number; // 0-based, matching PlacedItem.page
  y: number;
  x0: number;
  x1: number;
}

/** The loose shape of the pdfjs page proxy that exposes an operator list — a
 *  superset of `pdf-to-prose-docx`'s `PdfjsProxy` page. Kept structural so this
 *  module imports neither unpdf nor pdfjs at the top level. */
interface OpProxy {
  numPages: number;
  getPage(n: number): Promise<{
    getViewport(o: { scale: number }): { width: number; height: number };
    getOperatorList(): Promise<{ fnArray: number[]; argsArray: unknown[] }>;
  }>;
}

type Mat = [number, number, number, number, number, number];
function mul(a: Mat, b: Mat): Mat {
  return [
    a[0] * b[0] + a[2] * b[1],
    a[1] * b[0] + a[3] * b[1],
    a[0] * b[2] + a[2] * b[3],
    a[1] * b[2] + a[3] * b[3],
    a[0] * b[4] + a[2] * b[5] + a[4],
    a[1] * b[4] + a[3] * b[5] + a[5],
  ];
}
function apply(m: Mat, x: number, y: number): [number, number] {
  return [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]];
}

/** Is this colour meaningfully darker than white paper? A near-white stroke/fill
 *  is a field-box background, not an inked rule line. Accepts `#rrggbb`, a small
 *  set of names, or anything unparseable (treated as inked — fail toward keeping,
 *  since the annotator still requires a label to pair it). */
function isInked(color: unknown): boolean {
  if (typeof color !== 'string') return true;
  const c = color.trim().toLowerCase();
  if (c === 'white' || c === '#fff' || c === '#ffffff') return false;
  const m = /^#([0-9a-f]{6})$/.exec(c);
  if (m) {
    const n = parseInt(m[1], 16);
    const r = (n >> 16) & 0xff, g = (n >> 8) & 0xff, b = n & 0xff;
    // luminance close to white → not inked
    return 0.299 * r + 0.587 * g + 0.114 * b < 235;
  }
  return true;
}

const H_TOL = 2; // a segment is "horizontal" if |Δy| ≤ this after transform
const MIN_LEN = 15; // ignore hairline artifacts / tick marks shorter than this

/**
 * Extract the visible horizontal rule segments across all pages. Fail-safe:
 * returns [] on any error (a malformed op list, a pdfjs version whose OPS differ,
 * a proxy without `getOperatorList`). Pure-ish (only reads the proxy).
 */
export async function extractRuleSegments(proxy: OpProxy): Promise<RuleSegment[]> {
  let OPS: Record<string, number>;
  try {
    // Dynamic import so pdfjs stays out of the bundle graph (unpdf is a
    // serverExternalPackage; this rides the same install).
    const mod = (await import('pdfjs-dist/legacy/build/pdf.mjs')) as unknown as {
      OPS: Record<string, number>;
    };
    OPS = mod.OPS;
    if (!OPS || typeof OPS.constructPath !== 'number') return [];
  } catch {
    return [];
  }

  const segs: RuleSegment[] = [];
  try {
    for (let p = 1; p <= proxy.numPages; p++) {
      const page = await proxy.getPage(p);
      const ol = await page.getOperatorList();
      let ctm: Mat = [1, 0, 0, 1, 0, 0];
      const stack: Array<{ ctm: Mat; stroke: unknown; fill: unknown }> = [];
      let stroke: unknown = '#000000';
      let fill: unknown = '#000000';

      const push = (x0: number, y0: number, x1: number, y1: number, color: unknown): void => {
        const [ax, ay] = apply(ctm, x0, y0);
        const [bx, by] = apply(ctm, x1, y1);
        if (Math.abs(by - ay) > H_TOL) return;
        if (Math.abs(bx - ax) < MIN_LEN) return;
        if (!isInked(color)) return;
        segs.push({
          page: p - 1,
          y: Math.round((ay + by) / 2),
          x0: Math.round(Math.min(ax, bx)),
          x1: Math.round(Math.max(ax, bx)),
        });
      };

      for (let i = 0; i < ol.fnArray.length; i++) {
        const fn = ol.fnArray[i];
        const a = ol.argsArray[i] as unknown;
        if (fn === OPS.save) stack.push({ ctm, stroke, fill });
        else if (fn === OPS.restore) {
          const s = stack.pop();
          if (s) { ctm = s.ctm; stroke = s.stroke; fill = s.fill; }
        } else if (fn === OPS.transform) {
          if (Array.isArray(a) && a.length === 6) ctm = mul(ctm, a as Mat);
        } else if (fn === OPS.setStrokeRGBColor) {
          if (Array.isArray(a)) stroke = a[0];
        } else if (fn === OPS.setFillRGBColor) {
          if (Array.isArray(a)) fill = a[0];
        } else if (fn === OPS.constructPath) {
          // args = [drawKindOps, subpaths, bbox]; `subpaths` is an array whose
          // elements are each a flat [op, x, y, op, x, y, …] list (0=moveTo,
          // 1=lineTo, 5=rectangle). ⚠️ EACH ELEMENT IS ARRAY-*LIKE*, NOT a plain
          // Array: pdfjs emits a Float32Array/typed array for a path built from
          // vector ops, and `Array.isArray(typedArray)` is FALSE — so a plain
          // `Array.isArray` skip silently dropped every segment on pdf-lib-
          // authored forms (adversarial pass, 2026-09-14). Accept any indexable
          // with a numeric length.
          const subpaths = Array.isArray(a) ? (a[1] as unknown) : null;
          if (!subpaths || typeof (subpaths as ArrayLike<unknown>).length !== 'number') continue;
          const sub = subpaths as ArrayLike<ArrayLike<number>>;
          for (let s = 0; s < sub.length; s += 1) {
            const sp = sub[s];
            if (!sp || typeof sp.length !== 'number') continue;
            let ci = 0, cx = 0, cy = 0;
            while (ci < sp.length) {
              const op = sp[ci++];
              if (op === 0) { cx = sp[ci++]; cy = sp[ci++]; }
              else if (op === 1) { const nx = sp[ci++], ny = sp[ci++]; push(cx, cy, nx, ny, stroke); cx = nx; cy = ny; }
              else if (op === 2 || op === 3) { ci += 6; }
              else if (op === 5) {
                const rx = sp[ci++], ry = sp[ci++], rw = sp[ci++], rh = sp[ci++];
                if (Math.abs(rh) < 8) push(rx, ry, rx + rw, ry, fill);
              } else if (op === 4) { /* close */ }
              else break;
            }
          }
        }
      }
    }
  } catch {
    return [];
  }
  return segs;
}
