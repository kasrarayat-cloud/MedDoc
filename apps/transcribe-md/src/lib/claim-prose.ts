// ============================================================================
// A suggestion should read like something a person said.
// ----------------------------------------------------------------------------
// Verifier-demoted claims are quoted verbatim from the note, and when the note
// carries a measurements table that means a card can read:
//
//     | GSV at the Knee | 3.4 | 1.8 |
//
// which is a fragment of markup, not a clinical statement. A doctor is being
// asked to decide whether that belongs in a patient's record; they should be
// shown a sentence.
//
// The column names come from the note's OWN header row, so the phrasing is the
// doctor's vocabulary rather than ours, and a cell we cannot pair with a column
// is left out rather than guessed at. Anything that is not a table row is
// returned untouched — this only ever reformats markup, never content.
// ============================================================================

/** `| a | b | c |` with at least two cells. */
const ROW_RE = /^\s*\|(.+)\|\s*$/;
/** `| --- | :--- | ---: |` — a table's alignment rule, never content. */
const RULE_RE = /^\s*\|[\s:|-]+\|\s*$/;

function cells(line: string): string[] | null {
  if (RULE_RE.test(line)) return null;
  const m = ROW_RE.exec(line);
  if (!m) return null;
  const parts = m[1].split('|').map((c) => c.trim());
  return parts.length >= 2 ? parts : null;
}

/** "DIAMETER (mm)" -> { label: 'diameter', unit: 'mm' } */
function readHeading(raw: string): { label: string; unit: string | null } {
  const paren = /^(.*?)\s*\(([^)]+)\)\s*$/.exec(raw.trim());
  const label = (paren ? paren[1] : raw).trim().toLowerCase();
  return { label, unit: paren ? paren[2].trim() : null };
}

/** A cell that says nothing. */
function isBlank(cell: string): boolean {
  const t = cell.trim();
  return t === '' || t === '—' || t === '-' || /^\[not documented\]$/i.test(t);
}

/**
 * Find the header row of the table this row belongs to.
 *
 * Scans upward from the matching row in the note: the first pipe row above the
 * alignment rule is the header. Returns null when the row is not in a table we
 * can read, in which case the caller leaves the claim alone.
 */
function headerFor(note: string, rowText: string): { header: string[]; caption: string | null } | null {
  const lines = note.split('\n');
  const target = rowText.trim();
  const hits = lines.reduce<number[]>((acc, l, i) => (l.trim() === target ? [...acc, i] : acc), []);
  // AMBIGUOUS. A bilateral study renders one table per leg with identical
  // segment labels; pairing against whichever table came first would label a
  // left-leg measurement with the right leg's columns, in the doctor's own
  // vocabulary, which reads as authoritative. One match or nothing.
  if (hits.length !== 1) return null;
  const at = hits[0];
  for (let i = at - 1; i >= 0; i -= 1) {
    const line = lines[i];
    if (RULE_RE.test(line)) {
      const head = cells(lines[i - 1] ?? '');
      if (!head || head.length < 2) return null;
      // The line above the header is usually the table's own caption, and on a
      // bilateral study it is what carries the laterality. A card that says
      // "GSV at the Knee" without saying WHICH LEG is not enough to decide on.
      const above = (lines[i - 2] ?? '').trim();
      // Keep only the qualifying tail — "DIAMETER AND REFLUX TIME — Right Leg"
      // is worth reading as "Right Leg". The table's title repeats what the
      // column names already say; the LEG is the part a decision turns on.
      const raw = above && !cells(above) && !/^\s*#{1,6}\s/.test(above) ? above : null;
      const caption = raw ? (raw.split(/\s+[—–-]\s+/).pop() ?? raw).trim() : null;
      return { header: head, caption };
    }
    // A blank line or a heading means we left the table without finding a rule.
    if (!line.trim() || /^\s*#{1,6}\s/.test(line)) return null;
  }
  return null;
}

/**
 * Render a claim for display.
 *
 * A markdown table row becomes prose when its table's header can be found;
 * everything else is returned exactly as it is.
 */
export function claimProse(claimText: string, note: string): string {
  const row = cells(claimText);
  if (!row) return claimText;

  const found = headerFor(note, claimText);
  if (!found || found.header.length !== row.length) return claimText;
  const { header, caption } = found;

  const [rowLabel, ...values] = row;
  const parts: string[] = [];
  values.forEach((value, i) => {
    if (isBlank(value)) return; // not documented — say nothing rather than "—"
    const { label, unit } = readHeading(header[i + 1] ?? '');
    // Do not append a unit the cell already carries: "6.2 mm" must not become
    // "6.2 mm mm".
    const needsUnit = unit && !new RegExp(`${unit}\\s*$`, 'i').test(value);
    parts.push(label ? `${label} ${value}${needsUnit ? ` ${unit}` : ''}` : value);
  });

  const subject = caption ? `${caption} — ${rowLabel}` : rowLabel;
  if (parts.length === 0) {
    // Every measurement was blank: the row asserts nothing.
    return `${subject}: nothing documented`;
  }
  return `${subject}: ${parts.join(', ')}`;
}
