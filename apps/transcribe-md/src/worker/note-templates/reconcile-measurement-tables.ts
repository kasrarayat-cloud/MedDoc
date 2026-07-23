// ============================================================================
// Deterministic post-generation reconciler for venous-duplex measurement tables.
// ----------------------------------------------------------------------------
// The note-generation prompt emits a fixed, symmetric table skeleton per leg
// (every segment class as a row), but the model occasionally DROPS a row it also
// documented in prose — so a dictated value (e.g. right SSV proximal-calf 2.8,
// left GSV knee 3.4) lands only in the narrative, never in its cell, and the two
// leg tables end up asymmetric. This pure pass rebuilds every measurement table
// to ONE canonical symmetric row set and recovers any dropped, prose-documented
// measurement into its cell. It NEVER invents: a segment with no value in either
// the table or the prose stays "[not documented]".
// ============================================================================

const NOT_DOCUMENTED = '[not documented]';

// Vein detection — most specific first so "great saphenous" inside "anterior
// accessory great saphenous" does not win.
const VEIN_PATTERNS: Array<{ re: RegExp; key: string }> = [
  { re: /anterior accessory (great )?saphenous|\baagsv\b/i, key: 'AAGSV' },
  { re: /posterior accessory (great )?saphenous|\bpagsv\b/i, key: 'PAGSV' },
  { re: /small saphenous|\bssv\b/i, key: 'SSV' },
  { re: /great saphenous|\bgsv\b/i, key: 'GSV' },
];

// Segment detection — "below the knee" before "knee".
const SEGMENT_PATTERNS: Array<{ re: RegExp; key: string }> = [
  { re: /saphenofemoral junction|\bsfj\b/i, key: 'SFJ' },
  { re: /saphenopopliteal junction|\bspj\b/i, key: 'SPJ' },
  { re: /below[- ]the[- ]knee|below[- ]knee/i, key: 'BELOW_KNEE' },
  { re: /proximal calf/i, key: 'PROX_CALF' },
  { re: /proximal thigh|mid[- ]thigh/i, key: 'PROX_THIGH' },
  { re: /\bknee\b/i, key: 'KNEE' },
];

// (vein, segment) → the exact canonical row label the templates use.
const ROW_LABEL: Record<string, Record<string, string>> = {
  GSV: {
    SFJ: 'GSV at the SFJ',
    PROX_THIGH: 'GSV at the Proximal Thigh',
    KNEE: 'GSV at the Knee',
    BELOW_KNEE: 'GSV Below Knee',
  },
  SSV: {
    SPJ: 'SSV at the SPJ',
    PROX_CALF: 'SSV at the Proximal Calf',
  },
  AAGSV: {
    SFJ: 'AAGSV at the SFJ',
    PROX_THIGH: 'AAGSV at the Proximal Thigh',
  },
  PAGSV: {
    SFJ: 'PAGSV at the SFJ',
    PROX_THIGH: 'PAGSV at the Proximal Thigh',
  },
};

// The FIXED canonical row set for a lower-extremity venous reflux study — both
// legs always get exactly these 10 segments, in this order. Any extra row a
// venous table also defines is appended after these (first-seen order); the
// reconciler never drops a template-defined row.
const CANONICAL_ORDER = [
  'GSV at the SFJ',
  'GSV at the Proximal Thigh',
  'GSV at the Knee',
  'GSV Below Knee',
  'SSV at the SPJ',
  'SSV at the Proximal Calf',
  'AAGSV at the SFJ',
  'AAGSV at the Proximal Thigh',
  'PAGSV at the SFJ',
  'PAGSV at the Proximal Thigh',
];

interface Cell {
  diameter: string | null;
  reflux: string | null;
}

/** True only for the "no value here" tokens — empty or the not-assessed
 *  placeholder. ANY other existing cell content (a bare number, a number with a
 *  unit, "—", "competent", "<0.5") is a real documented value and is preserved
 *  verbatim — the reconciler recovers from prose ONLY into genuinely empty cells,
 *  so it can never overwrite a documented value with a false "[not documented]". */
function isEmptyCell(token: string | undefined): boolean {
  const t = (token ?? '').trim();
  return t === '' || t === NOT_DOCUMENTED;
}

/** Every non-overlapping match of a labelled pattern set, most-specific first.
 *  Patterns are given in specificity order (e.g. AAGSV before GSV, "below the
 *  knee" before "knee"); at any overlap the earlier-listed (more specific) match
 *  wins, so "great saphenous" inside "anterior accessory great saphenous" and
 *  "knee" inside "below the knee" never double-count. Returned in text order. */
function findSpans(
  text: string,
  patterns: ReadonlyArray<{ re: RegExp; key: string }>,
): Array<{ index: number; key: string }> {
  const raw: Array<{ start: number; end: number; key: string; order: number }> = [];
  patterns.forEach((p, order) => {
    for (const m of text.matchAll(new RegExp(p.re.source, 'gi'))) {
      const start = m.index ?? 0;
      raw.push({ start, end: start + m[0].length, key: p.key, order });
    }
  });
  raw.sort((a, b) => a.order - b.order || b.end - b.start - (a.end - a.start) || a.start - b.start);
  const kept: Array<{ start: number; end: number; key: string }> = [];
  for (const c of raw) {
    if (kept.some((k) => c.start < k.end && k.start < c.end)) continue; // overlaps a kept span
    kept.push(c);
  }
  return kept
    .sort((a, b) => a.start - b.start)
    .map((k) => ({ index: k.start, key: k.key }));
}

/** Nearest labelled span (by character distance) that each numeric value belongs
 *  to; the FIRST value assigned to a span wins. Position-based, so it is immune
 *  to clause structure: serial lists, value-first ("3.9 mm at the SFJ") vs
 *  segment-first ("at the SFJ 3.9 mm"), multiple segments in one sentence, and
 *  verbose connective prose ("…, tapering to 2.8 mm below the knee") all resolve
 *  correctly — a value lands on whichever segment it sits closest to. */
function assignNearest(
  spans: ReadonlyArray<{ index: number }>,
  values: ReadonlyArray<{ index: number; value: string }>,
): Map<number, string> {
  const out = new Map<number, string>();
  for (const v of values) {
    let best = -1;
    let bestDist = Infinity;
    spans.forEach((s, si) => {
      const dist = Math.abs(v.index - s.index);
      if (dist < bestDist) { bestDist = dist; best = si; }
    });
    if (best >= 0 && !out.has(best)) out.set(best, v.value);
  }
  return out;
}

const DIAMETER_RE = /(\d+(?:\.\d+)?)\s*(?:mm|millimet(?:er|re)s?)\b/gi;
const REFLUX_RE =
  /reflux[^.;]*?(\d+(?:\.\d+)?)\s*(?:s\b|sec\b|seconds?)|(\d+(?:\.\d+)?)\s*seconds?\s+of\s+reflux/gi;

function numbers(text: string, re: RegExp): Array<{ index: number; value: string }> {
  return [...text.matchAll(new RegExp(re.source, 'gi'))].map((m) => ({
    index: m.index ?? 0,
    value: (m[1] ?? m[2]) as string,
  }));
}

/**
 * Extract vein/segment measurements from one leg's findings prose. Two-stage,
 * so it is robust to BOTH well-separated measurements and dense multi-segment
 * sentences:
 *   1. split the prose into measurement clauses (sentence/`;` boundaries, plus a
 *      conjunction or bare comma that introduces the next measurement) — this
 *      bounds each measurement to a short span and threads the vein via anaphora;
 *   2. WITHIN each clause, SEGMENT-ANCHOR: bind every diameter/reflux to the
 *      segment it sits closest to. Over a short clause "nearest" is unambiguous,
 *      so a clause carrying two segments ("…at the knee 3.2 mm, tapering to 2.8 mm
 *      below the knee") places both values correctly, and knee vs below-knee is
 *      resolved by position, not pattern order.
 */
export function extractLegMeasurements(prose: string): Map<string, Cell> {
  const out = new Map<string, Cell>();
  const NEXT_MEASUREMENT = String.raw`(?:at\s+the|\d+(?:\.\d+)?\s*(?:mm|millimet(?:er|re)s?)\b)`;
  const clauses = prose.split(
    new RegExp(
      String.raw`(?<=[.;])\s+|[,;]?\s*\band\b(?=\s+${NEXT_MEASUREMENT})|,\s*(?=${NEXT_MEASUREMENT})`,
      'i',
    ),
  );
  let currentVein: string | null = null;
  for (const clause of clauses) {
    const veinsHere = findSpans(clause, VEIN_PATTERNS);
    const segs = findSpans(clause, SEGMENT_PATTERNS);
    // Vein for a segment: the most recent vein named before it IN THIS CLAUSE,
    // else the running vein carried across clauses by anaphora.
    const veinFor = (pos: number): string | null => {
      let before: string | null = null;
      for (const v of veinsHere) if (v.index <= pos) before = v.key;
      return before ?? currentVein;
    };
    // Carry the last-named vein forward BEFORE skipping a segment-less clause, so
    // a vein-only lead-in ("The great saphenous vein is incompetent.") still
    // anchors the anaphora for the measurement clauses that follow it.
    if (veinsHere.length > 0) currentVein = veinsHere[veinsHere.length - 1].key;
    if (segs.length === 0) continue;

    const segDiameter = assignNearest(segs, numbers(clause, DIAMETER_RE));
    const segReflux = assignNearest(segs, numbers(clause, REFLUX_RE));
    segs.forEach((s, si) => {
      const diameter = segDiameter.get(si);
      if (diameter === undefined) return; // a segment named with no diameter → skip
      const vein = veinFor(s.index);
      if (!vein) return;
      const label = ROW_LABEL[vein]?.[s.key];
      if (!label) return;
      // First mention wins (never overwrite an earlier explicit value).
      if (!out.has(label)) out.set(label, { diameter, reflux: segReflux.get(si) ?? null });
    });
  }
  return out;
}

interface ParsedTable {
  start: number; // line index of the header row
  end: number; // line index after the last data row (exclusive)
  header: string[];
  rows: Array<{ label: string; cells: string[] }>;
  dataCols: number; // number of non-label columns
}

const TABLE_LINE = /^\s*\|(.+)\|\s*$/;

function splitCells(line: string): string[] {
  const m = TABLE_LINE.exec(line);
  if (!m) return [];
  return m[1].split('|').map((c) => c.trim());
}

/** Locate every markdown table in the note and the leg each belongs to (from the
 *  nearest preceding "— Right/Left Leg" heading). */
function findTables(lines: string[]): Array<ParsedTable & { leg: string | null }> {
  const tables: Array<ParsedTable & { leg: string | null }> = [];
  let leg: string | null = null;
  for (let i = 0; i < lines.length; i++) {
    const h = lines[i].match(/—\s*(right|left)\s+leg/i) ?? lines[i].match(/\b(right|left)\s+leg\b/i);
    if (/^#/.test(lines[i]) && h) leg = h[1].toLowerCase();
    const header = splitCells(lines[i]);
    if (header.length < 2) continue;
    const sep = i + 1 < lines.length ? splitCells(lines[i + 1]) : [];
    if (sep.length === 0 || !sep.every((c) => /^:?-{2,}:?$/.test(c))) continue;
    const rows: Array<{ label: string; cells: string[] }> = [];
    let j = i + 2;
    for (; j < lines.length; j++) {
      const cells = splitCells(lines[j]);
      if (cells.length === 0) break;
      rows.push({ label: cells[0], cells });
    }
    // Data-column count. The generated header can omit the row-label column
    // header (its first cell is already a data column like "DIAMETER (mm)"),
    // while filled data rows carry label + N data cells. Reconcile both signals.
    const widest = rows.reduce((m, r) => Math.max(m, r.cells.length), 0);
    const headerHasLabelCol = header.length > 0 && !/diameter|reflux|\(mm\)|\(sec/i.test(header[0]);
    const headerDataCols = headerHasLabelCol ? header.length - 1 : header.length;
    const dataCols = Math.max(headerDataCols, widest - 1, 1);
    tables.push({ start: i, end: j, header, rows, dataCols, leg });
    i = j - 1;
  }
  return tables;
}

/** Is this a measurement table (has a DIAMETER or REFLUX column)? */
function isMeasurementTable(header: string[]): boolean {
  return header.some((h) => /diameter|reflux/i.test(h));
}

/** Is this specifically a VENOUS-DUPLEX leg table — the only kind the fixed
 *  saphenous-segment canon applies to? True when it has a REFLUX column or at
 *  least one canonical vein-segment row. A non-venous imaging table under the
 *  ultrasound specialty (e.g. an abdominal-aorta "Segment | Diameter (cm)"
 *  table) matches neither, so it is left completely untouched — the fixed venous
 *  canon is never imposed on non-venous anatomy. */
function isVenousTable(t: ParsedTable): boolean {
  return (
    t.header.some((h) => /reflux/i.test(h)) ||
    t.rows.some((r) => CANONICAL_ORDER.includes(r.label))
  );
}

/**
 * Rebuild every venous measurement table in the note to one canonical symmetric
 * row set, recovering any dropped, prose-documented measurement into its cell.
 * Pure. A no-op when the note has no measurement tables.
 *
 * SINGLE SOURCE (enforced): the ONLY input is `note` — the final adopted SOAP
 * body (worker: polished.soapFinal → the signed note). The reconciler NEVER
 * reads the set-aside/suggestions lane (suggestedClaims). A measurement demoted
 * out of the adopted note therefore does NOT reappear in a table — tables and
 * prose can only ever reflect the same adopted note, never disagree by pulling
 * unadopted content into a cell.
 */
export function reconcileMeasurementTables(note: string): string {
  const lines = note.split('\n');
  // Only VENOUS-duplex leg tables get the fixed saphenous canon + prose recovery.
  // A non-venous imaging table (aorta/thyroid/renal) under the ultrasound
  // specialty is left untouched — never rebuilt against vein anatomy.
  const tables = findTables(lines)
    .filter((t) => isMeasurementTable(t.header))
    .filter(isVenousTable);
  if (tables.length === 0) return note;

  // Canonical row set = the FIXED conventional segment sequence (CANONICAL_ORDER),
  // ALWAYS, for BOTH legs, in fixed order — NOT derived from whatever rows the
  // model happened to emit. Deriving it from the emitted tables (the old
  // behaviour) let a segment the model dropped from BOTH legs vanish entirely
  // (the KUK regression: neither leg emitted "GSV at the Knee", so no knee row
  // existed and the dictated knee diameters had nowhere to land). Any EXTRA row a
  // venous table defines that the convention doesn't name is preserved, appended
  // in first-seen order — the reconciler never drops a template-defined row.
  const extras: string[] = [];
  const seen = new Set<string>(CANONICAL_ORDER);
  for (const t of tables) {
    for (const r of t.rows) {
      if (!seen.has(r.label)) { seen.add(r.label); extras.push(r.label); }
    }
  }
  const canonical = [...CANONICAL_ORDER, ...extras];

  // Parse the FINDINGS prose into paragraphs, each with its own measurements.
  const paragraphs = parseFindingsParagraphs(note);

  // Rebuild each table in place (from the LAST table to the first, so earlier
  // line indices stay valid while we splice).
  const rebuilt = [...lines];
  for (let ti = tables.length - 1; ti >= 0; ti--) {
    const t = tables[ti];
    const existing = new Map<string, string[]>();
    for (const r of t.rows) existing.set(r.label, r.cells);
    // Attribute a findings paragraph to THIS leg table safely — see selectProse.
    const prose = selectProse(paragraphs, t.leg, existing);

    const newRows = canonical.map((label) => {
      const cells = existing.get(label);
      const recovered = prose.get(label);
      // Preserve ANY existing documented cell verbatim; recover from prose ONLY
      // into a genuinely empty / not-documented / missing cell (never overwrite).
      const diaCell = !isEmptyCell(cells?.[1])
        ? cells![1].trim()
        : (recovered?.diameter ?? NOT_DOCUMENTED);
      const refCell =
        t.dataCols >= 2
          ? (!isEmptyCell(cells?.[2]) ? cells![2].trim() : (recovered?.reflux ?? NOT_DOCUMENTED))
          : null;
      return t.dataCols >= 2 ? `| ${label} | ${diaCell} | ${refCell} |` : `| ${label} | ${diaCell} |`;
    });

    rebuilt.splice(t.start + 2, t.end - (t.start + 2), ...newRows);
  }
  return rebuilt.join('\n');
}

interface FindingsParagraph {
  leg: string | null; // explicit right/left marker on this paragraph, else null
  measurements: Map<string, Cell>;
  values: Set<string>; // every numeric value this paragraph reports
}

/** True right/left leg attribution for a paragraph, from an explicit heading /
 *  label / laterality phrase. Ambiguous (both or neither) → null. Leading
 *  markdown emphasis/heading/quote markers are stripped first so a bold
 *  "**Left Leg:**" or "### Right leg" label is detected the same as a bare one. */
function detectLeg(chunk: string): string | null {
  const t = chunk.toLowerCase().replace(/(^|\n)[ \t]*[*_#>]+[ \t]*/g, '$1');
  const r = /(^|\n)\s*right(\s+leg| lower extremity)?\b|\bon the right\b/.test(t);
  const l = /(^|\n)\s*left(\s+leg| lower extremity)?\b|\bon the left\b/.test(t);
  if (r && !l) return 'right';
  if (l && !r) return 'left';
  return null;
}

/** The FINDINGS body split into paragraphs (on blank lines OR "###" headings). */
function parseFindingsParagraphs(note: string): FindingsParagraph[] {
  const lines = note.split('\n');
  let start = -1;
  let end = lines.length;
  for (let i = 0; i < lines.length; i++) {
    if (/^##\s+findings\b/i.test(lines[i])) { start = i + 1; continue; }
    if (start >= 0 && /^##\s/.test(lines[i])) { end = i; break; }
  }
  if (start < 0) return [];
  const body = lines.slice(start, end).join('\n');
  const chunks = body.split(/\n(?=\s*###\s)|\n\s*\n/).map((c) => c.trim()).filter(Boolean);
  return chunks.map((chunk) => {
    const measurements = extractLegMeasurements(chunk);
    const values = new Set<string>();
    for (const c of measurements.values()) {
      if (c.diameter) values.add(c.diameter);
      if (c.reflux) values.add(c.reflux);
    }
    return { leg: detectLeg(chunk), measurements, values };
  });
}

/**
 * Choose the findings prose that belongs to a given leg table WITHOUT ever
 * guessing by position. Prefer a paragraph with an explicit matching leg marker;
 * otherwise pick the paragraph whose reported values overlap this table's already-
 * filled cells the most — but ONLY when that winner is unambiguous (strictly beats
 * every other paragraph). A tie / no overlap yields no prose, so a value stays
 * unrecovered ("[not documented]") rather than risk landing in the wrong leg.
 */
function selectProse(
  paragraphs: FindingsParagraph[],
  tableLeg: string | null,
  existing: Map<string, string[]>,
): Map<string, Cell> {
  if (paragraphs.length === 0) return new Map();
  // Candidate pool for the content match: a paragraph explicitly marked as the
  // OTHER leg is NEVER eligible (would contaminate this leg with the other's
  // values). Same-leg-marked or unmarked paragraphs remain.
  const candidates = tableLeg
    ? paragraphs.filter((p) => !p.leg || p.leg === tableLeg)
    : paragraphs;
  if (tableLeg) {
    const marked = candidates.find((p) => p.leg === tableLeg);
    if (marked) return marked.measurements;
  }
  const tableValues = new Set<string>();
  for (const cells of existing.values()) {
    for (const c of cells.slice(1)) {
      const v = c.trim();
      if (/^-?\d+(?:\.\d+)?$/.test(v)) tableValues.add(v);
    }
  }
  if (tableValues.size === 0) return new Map();
  const scored = candidates
    .map((p) => ({ p, score: [...p.values].filter((v) => tableValues.has(v)).length }))
    .sort((a, b) => b.score - a.score);
  if (scored.length > 0 && scored[0].score > 0 && (scored.length === 1 || scored[0].score > scored[1].score)) {
    return scored[0].p.measurements;
  }
  return new Map();
}
