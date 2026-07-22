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

// Conventional vein-segment ordering for a lower-extremity venous reflux study.
// The canonical row union is sorted by this so a recovered row lands in its
// proper place (e.g. SSV proximal calf directly after SSV SPJ), not appended.
// Rows not in this list keep their first-seen relative order, after the known
// ones — the reconciler never drops a row a template defines.
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

function isBareNumber(s: string): boolean {
  return /^-?\d+(?:\.\d+)?$/.test(s.trim());
}

/** A cell token is a real value only if bare-numeric; "—"/"[not documented]"/
 *  blank/prose are treated as "no value" for recovery purposes. */
function valueOrNull(token: string | undefined): string | null {
  if (token == null) return null;
  const t = token.trim();
  return isBareNumber(t) ? t : null;
}

/** Parse one clinical sentence-ish clause for a measurement. Reads the diameter
 *  ("6.2 mm" / "measures 6.2 millimeters") and reflux ("reflux of 3.4 seconds")
 *  nearest the clause. Returns null when no diameter number is present. */
function parseMeasurement(clause: string): { diameter: string; reflux: string | null } | null {
  const dia = clause.match(/(\d+(?:\.\d+)?)\s*(?:mm|millimet(?:er|re)s?)\b/i);
  if (!dia) return null;
  const ref = clause.match(/reflux[^.]*?(\d+(?:\.\d+)?)\s*(?:s\b|sec\b|seconds?)/i);
  return { diameter: dia[1], reflux: ref ? ref[1] : null };
}

/** Extract vein/segment measurements from one leg's findings prose. Tracks the
 *  current vein across anaphora ("it measures …" keeps the last-named vein). */
export function extractLegMeasurements(prose: string): Map<string, Cell> {
  const out = new Map<string, Cell>();
  // Split into clauses on sentence/segment boundaries so each measurement is
  // scoped to one vein+segment mention.
  const clauses = prose.split(/(?<=[.;])\s+|(?:,\s*and\b)|(?:\band\b(?=\s+at\s+the))/i);
  let currentVein: string | null = null;
  for (const clause of clauses) {
    for (const v of VEIN_PATTERNS) {
      if (v.re.test(clause)) { currentVein = v.key; break; }
    }
    if (!currentVein) continue;
    let segment: string | null = null;
    for (const s of SEGMENT_PATTERNS) {
      if (s.re.test(clause)) { segment = s.key; break; }
    }
    if (!segment) continue;
    const label = ROW_LABEL[currentVein]?.[segment];
    if (!label) continue;
    const m = parseMeasurement(clause);
    if (!m) continue;
    // First mention wins (never overwrite an earlier explicit value).
    if (!out.has(label)) out.set(label, { diameter: m.diameter, reflux: m.reflux });
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

/** Is this a venous measurement table (has a DIAMETER or REFLUX column)? */
function isMeasurementTable(header: string[]): boolean {
  return header.some((h) => /diameter|reflux/i.test(h));
}

/**
 * Rebuild every venous measurement table in the note to one canonical symmetric
 * row set, recovering any dropped, prose-documented measurement into its cell.
 * Pure. A no-op when the note has no measurement tables.
 */
export function reconcileMeasurementTables(note: string): string {
  const lines = note.split('\n');
  const tables = findTables(lines).filter((t) => isMeasurementTable(t.header));
  if (tables.length === 0) return note;

  // Canonical row set = union of every measurement table's rows, in first-seen
  // order (so a row one leg dropped is still contributed by the other leg). The
  // template emits both legs identically, so this recovers the full set.
  const union: string[] = [];
  const seen = new Set<string>();
  for (const t of tables) {
    for (const r of t.rows) {
      if (!seen.has(r.label)) { seen.add(r.label); union.push(r.label); }
    }
  }
  // Order by the conventional segment sequence; keep first-seen order for any
  // label the convention list doesn't name (stable sort).
  const rank = (label: string) => {
    const i = CANONICAL_ORDER.indexOf(label);
    return i < 0 ? CANONICAL_ORDER.length + union.indexOf(label) : i;
  };
  const canonical = [...union].sort((a, b) => rank(a) - rank(b));

  // Per-leg prose measurements, from the FINDINGS section (first non-empty
  // paragraph = right leg, second = left — matching the per-limb organisation).
  const legMeasurements = extractFindingsByLeg(note);

  // Rebuild each table in place (from the LAST table to the first, so earlier
  // line indices stay valid while we splice).
  const rebuilt = [...lines];
  for (let ti = tables.length - 1; ti >= 0; ti--) {
    const t = tables[ti];
    const existing = new Map<string, string[]>();
    for (const r of t.rows) existing.set(r.label, r.cells);
    const prose = (t.leg && legMeasurements.get(t.leg)) || new Map<string, Cell>();

    const newRows = canonical.map((label) => {
      const cells = existing.get(label);
      const diaExisting = valueOrNull(cells?.[1]);
      const refExisting = t.dataCols >= 2 ? valueOrNull(cells?.[2]) : null;
      const recovered = prose.get(label);
      const diameter = diaExisting ?? recovered?.diameter ?? null;
      const reflux = refExisting ?? recovered?.reflux ?? null;
      // Preserve a stated-normal "—" the model wrote (don't overwrite with prose).
      const diaCell = cells && cells[1]?.trim() === '—' && diaExisting == null ? '—' : (diameter ?? NOT_DOCUMENTED);
      const refCell = t.dataCols >= 2
        ? (cells && cells[2]?.trim() === '—' && refExisting == null ? '—' : (reflux ?? NOT_DOCUMENTED))
        : null;
      return t.dataCols >= 2 ? `| ${label} | ${diaCell} | ${refCell} |` : `| ${label} | ${diaCell} |`;
    });

    rebuilt.splice(t.start + 2, t.end - (t.start + 2), ...newRows);
  }
  return rebuilt.join('\n');
}

/** Split the FINDINGS section into right/left prose + extract each leg's
 *  measurements. Uses explicit "Right Leg"/"Left Leg" markers when present,
 *  else paragraph order (1st = right, 2nd = left). */
function extractFindingsByLeg(note: string): Map<string, Map<string, Cell>> {
  const result = new Map<string, Map<string, Cell>>();
  const lines = note.split('\n');
  // Grab the FINDINGS section body (## FINDINGS … next ##).
  let start = -1;
  let end = lines.length;
  for (let i = 0; i < lines.length; i++) {
    if (/^##\s+findings\b/i.test(lines[i])) { start = i + 1; continue; }
    if (start >= 0 && /^##\s/.test(lines[i])) { end = i; break; }
  }
  if (start < 0) return result;
  const body = lines.slice(start, end).join('\n');

  // Prefer explicit leg markers.
  const rightMark = body.match(/right leg\s*:?\s*([\s\S]*?)(?=left leg\s*:|$)/i);
  const leftMark = body.match(/left leg\s*:?\s*([\s\S]*)$/i);
  if (rightMark || leftMark) {
    if (rightMark) result.set('right', extractLegMeasurements(rightMark[1]));
    if (leftMark) result.set('left', extractLegMeasurements(leftMark[1]));
    return result;
  }
  // Fall back to paragraph order.
  const paras = body.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  if (paras[0]) result.set('right', extractLegMeasurements(paras[0]));
  if (paras[1]) result.set('left', extractLegMeasurements(paras[1]));
  return result;
}
