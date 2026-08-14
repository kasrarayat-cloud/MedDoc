// ============================================================================
// SECTION ASSEMBLY — statics are stitched by code, never written by the model.
// ----------------------------------------------------------------------------
// WHY THIS EXISTS (ruling #106(a), SPEC §4.3a)
//
// A doctor uploaded a real blank form, activated it, and got back a note whose
// fixed TECHNIQUE paragraph had been PARAPHRASED: his "500 milliseconds" came
// out as "0.5 seconds". The bytes were never lost — they are preserved verbatim
// in `note_templates.sections` — but `build-soap-prompt` handed the paragraph to
// the model as text to REPRODUCE, and a model asked to reproduce prose will
// normalise it.
//
// ⚠️ THE FIX IS NOT A STRICTER PROMPT. The model never receives the static text
// as writable at all: it returns SLOT VALUES, and this module stitches the
// doctor's own bytes around them.
//
//     A model cannot paraphrase text it never receives as writable.
//
// That is "deterministic fills are never AI", pointed at statics.
//
// ⚠️ THE MARKER REGEX IS CANONICAL HERE. `picks-bridge.ts` and
// `reconcile-markers.ts` each carried their own identical copy; a third would
// drift from the first two the day any of them is fixed.
// ============================================================================

/** `{{one of: A | B | C}}` — the inline choice slot produced by Word dropdown
 *  content controls (see `docx-content-controls.ts`). */
export const CHOICE_MARKER_SOURCE = '\\{\\{one of:\\s*([^}]*)\\}\\}';

/**
 * What an unfilled slot renders as — the form's own visible empty convention
 * (SPEC §4.3a(b), ruling #106(f)).
 *
 * ⚠️ VISIBLE, DELIBERATELY. A bare gap reads as a typo or a rendering bug and
 * invites nobody to look; an em dash is the mark a paper form already uses for
 * "nothing recorded here", so a clinician reviewing the note can SEE that the
 * transcript did not answer this and decide, rather than skim past whitespace.
 */
export const EMPTY_SLOT_MARKER = '—';

export type Segment =
  /** The doctor's own bytes. Emitted EXACTLY, always. */
  | { kind: 'literal'; text: string }
  /** A hole the model may fill from `options`, and nothing else. */
  | { kind: 'slot'; id: string; options: string[]; raw: string };

/** Split one span of text into literals and slots, numbering slots from
 *  `startIndex` so ids stay stable across a multi-line section. */
function splitSpan(text: string, startIndex: number): Segment[] {
  const out: Segment[] = [];
  // A fresh regex per call: /g carries lastIndex, and a shared instance would
  // make this function's result depend on who called it last.
  const re = new RegExp(CHOICE_MARKER_SOURCE, 'g');
  let cursor = 0;
  let n = startIndex;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > cursor) {
      out.push({ kind: 'literal', text: text.slice(cursor, m.index) });
    }
    out.push({
      kind: 'slot',
      id: `s${n}`,
      // Options are trimmed for MATCHING; the literal spans around them are
      // untouched. Trimming an option changes what the model may pick, never
      // what the doctor wrote.
      options: (m[1] ?? '')
        .split('|')
        .map((o) => o.trim())
        .filter((o) => o.length > 0),
      raw: m[0],
    });
    n += 1;
    cursor = m.index + m[0].length;
  }
  if (cursor < text.length) {
    out.push({ kind: 'literal', text: text.slice(cursor) });
  }
  return out;
}

/** Count the slots in a segment list. */
function slotCount(segs: readonly Segment[]): number {
  return segs.reduce((k, s) => k + (s.kind === 'slot' ? 1 : 0), 0);
}

/**
 * Split a section's `defaultText` into literal spans and choice slots.
 *
 * ⚠️ THE LOAD-BEARING PROPERTY IS ROUND-TRIP IDENTITY: re-joining every literal
 * with each slot's own `raw` reproduces the input BYTE-FOR-BYTE. If that ever
 * fails, the doctor's text is being altered by the parser itself — which is the
 * defect this module exists to make impossible. Asserted by the gate.
 */
export function splitSegments(defaultText: string): Segment[] {
  return splitSpan(defaultText, 0);
}

/** Re-join segments with each slot restored to its own marker. MUST equal the
 *  input to `splitSegments`. This is the verbatim proof. */
export function rejoinVerbatim(segs: readonly Segment[]): string {
  return segs.map((s) => (s.kind === 'literal' ? s.text : s.raw)).join('');
}

/** One line of a section, segmented, with its slot ids already assigned. */
export interface AssemblyLine {
  segments: Segment[];
  slots: number;
}

/** Segment a whole section LINE BY LINE. Slot ids are global to the section so
 *  the model can be asked for them by name, but the drop rule below is
 *  per-line — a carrier sentence is a line, and that is the unit a form omits. */
export function segmentSection(defaultText: string): AssemblyLine[] {
  const lines = defaultText.split('\n');
  const out: AssemblyLine[] = [];
  let n = 0;
  for (const line of lines) {
    const segments = splitSpan(line, n);
    n += slotCount(segments);
    out.push({ segments, slots: slotCount(segments) });
  }
  return out;
}

/** Every slot in a section, for building the model's fill request. */
export function sectionSlots(
  lines: readonly AssemblyLine[]
): { id: string; options: string[] }[] {
  return lines
    .flatMap((l) => l.segments)
    .filter((s): s is Extract<Segment, { kind: 'slot' }> => s.kind === 'slot')
    .map((s) => ({ id: s.id, options: s.options }));
}

export interface AssembleResult {
  text: string;
  /** Carrier lines dropped because NO slot on them was filled — reported so a
   *  disappearance is observable rather than silent. */
  droppedLines: number;
  /** Slots the model declined to fill, or filled illegally. */
  unfilled: number;
  /** Slots whose proposed value was not one of that slot's own options. */
  rejected: number;
}

export interface AssembleOptions {
  /**
   * Drop a line whose every slot went unfilled.
   *
   * ⚠️ DEFAULT `false`, AND THE DEFAULT IS THE LOAD-BEARING PART. A line can be
   * BOTH fixed prose AND a carrier — the real form's TECHNIQUE paragraph is one
   * sentence of protocol text containing a single dropdown. Dropping that line
   * because its dropdown was undictated DELETES THE DOCTOR'S FIXED PARAGRAPH,
   * which is the exact defect this module exists to prevent.
   *
   * ⚠️ CAUGHT BY THIS MODULE'S OWN GATE, NOT BY REVIEW: the first version
   * dropped unconditionally, and the `500 milliseconds` tripwire went red on a
   * fail-closed slot. Two contract clauses genuinely collide on such a line —
   * §4.3a(a) "statics are sacred" and §4.3a(b) "slots fail closed".
   *
   * ⚠️ RULING #106(f) BREAKS THE TIE TOWARD (a), in the owner's words: *"the
   * worst case of keeping is a visible, reviewable hole; the worst case of
   * dropping is the doctor's prose silently vanishing, which is the original
   * defect's own shape."* So the line is KEPT, its fixed bytes verbatim, and
   * each unfilled slot renders `EMPTY_SLOT_MARKER` — never a bare gap, never a
   * dropped line.
   *
   * Set `true` only for sections whose lines are pure per-item carriers
   * (per-leg FINDINGS, per-side IMPRESSION), where an undictated line should
   * vanish rather than print half a sentence.
   */
  dropUndictatedCarriers?: boolean;
}

/**
 * Stitch the doctor's literals around the model's slot values.
 *
 * ⚠️ FAIL-CLOSED, per SPEC §4.3a(b). A slot whose value is absent — or is not
 * one of ITS OWN listed options — is UNFILLED. A value the model invented is
 * never emitted, and taking an option from a different slot's menu is refused
 * STRUCTURALLY rather than merely asked against in the prompt.
 *
 * ⚠️ A LINE WITH NO SLOTS IS ALWAYS KEPT — it is the doctor's fixed prose and is
 * emitted whatever the transcript said. For lines that DO carry slots, see
 * `dropUndictatedCarriers`.
 */
export function assembleSection(
  lines: readonly AssemblyLine[],
  fills: Readonly<Record<string, string | null | undefined>>,
  opts: AssembleOptions = {}
): AssembleResult {
  const dropUndictated = opts.dropUndictatedCarriers === true;
  const kept: string[] = [];
  let droppedLines = 0;
  let unfilled = 0;
  let rejected = 0;

  for (const line of lines) {
    // A line with no slots is pure static: emit the doctor's bytes, always.
    if (line.slots === 0) {
      kept.push(line.segments.map((s) => (s.kind === 'literal' ? s.text : '')).join(''));
      continue;
    }

    let filledHere = 0;
    const pieces = line.segments.map((s) => {
      if (s.kind === 'literal') return s.text;
      const v = fills[s.id];
      if (typeof v !== 'string' || v.length === 0) {
        unfilled += 1;
        return EMPTY_SLOT_MARKER;
      }
      if (!s.options.includes(v)) {
        rejected += 1;
        unfilled += 1;
        return EMPTY_SLOT_MARKER;
      }
      filledHere += 1;
      return v;
    });

    if (filledHere === 0 && dropUndictated) {
      droppedLines += 1;
      continue;
    }
    kept.push(pieces.join(''));
  }

  return { text: kept.join('\n'), droppedLines, unfilled, rejected };
}

export interface Block {
  /** The heading text without the leading `## `, or null for a preamble block
   *  that precedes the first heading. */
  heading: string | null;
  /** The block's full text INCLUDING its heading line. */
  text: string;
}

/** Split markdown into `##`-headed blocks. A leading block with no heading (the
 *  model's preamble, if any) is preserved as `heading: null` — this module
 *  never decides that content is worthless. */
export function splitBlocks(markdown: string): Block[] {
  // An empty draft has no blocks at all — not one empty preamble block. The
  // difference shows up as a stray leading newline in the composed note, which
  // is the kind of drift a byte-identity gate is supposed to catch and a reader
  // never would.
  if (markdown.length === 0) return [];
  const lines = markdown.split('\n');
  const out: Block[] = [];
  let current: Block | null = null;
  for (const line of lines) {
    const m = /^##\s+(\S.*)$/.exec(line);
    if (m) {
      if (current) out.push(current);
      current = { heading: m[1]!.trim(), text: line };
    } else if (current) {
      current.text += `\n${line}`;
    } else {
      current = { heading: null, text: line };
    }
  }
  if (current) out.push(current);
  return out;
}

/**
 * Is this block THIS section's? EXACT, after collapsing whitespace and case.
 *
 * ⚠️ DELIBERATELY NOT the validator's `headingMatcher`. That one is a PRESENCE
 * check and is lenient by design — `## TECHNIQUE` matches `## TECHNIQUE NOTES
 * FOR THIS STUDY`. Presence and identity are different questions, and using the
 * presence matcher for identity overwrote a section carrying a dictated
 * limitation with the doctor's boilerplate.
 */
export function headingIs(heading: string | null, label: string): boolean {
  if (heading === null) return false;
  const norm = (x: string) => x.trim().replace(/\s+/g, ' ').toLowerCase();
  return norm(heading) === norm(label);
}

/** The body of the block headed `label`, trimmed, or null when absent. */
export function sectionBody(text: string, label: string): string | null {
  const block = splitBlocks(text).find((b) => headingIs(b.heading, label));
  if (block === undefined) return null;
  const nl = block.text.indexOf('\n');
  return (nl === -1 ? '' : block.text.slice(nl + 1)).trim();
}

// ---------------------------------------------------------------------------
// STATIC-REGION DIVERGENCE — the L6b arm (ruling #106(g)).
// ---------------------------------------------------------------------------

/** An `always_include` section as CODE ASSEMBLED IT. `text` is the exact byte
 *  sequence that must survive every later hand on the note. */
export interface StaticRegion {
  sectionKey: string;
  label: string;
  text: string;
}

/**
 * Which assembled static regions are no longer present, byte-for-byte, in the
 * text under test.
 *
 * ⚠️ THIS IS A CONTAINMENT ASSERTION AGAINST BYTES CODE PRODUCED — NOT A DIFF,
 * and deliberately so. A heuristic diff has to DECIDE whether a change is
 * meaningful, and "0.5 seconds" for "500 milliseconds" is exactly the change a
 * similarity measure calls harmless. We know the precise bytes we assembled, so
 * the only honest question is whether they are still there.
 *
 * ⚠️ IT GUARDS THE OUTPUT, NOT THE WIRING (#106(g)(2)). It runs on the final
 * text whatever produced it — L6's polish today, L5's applied fixes, and any
 * future path that touches the note after assembly. A check that watched only
 * the polisher would go quiet the moment somebody added a seventh layer.
 *
 * ⚠️ WHY IT EXISTS AT ALL: `04-generate-soap` is not the only place the note
 * meets a model. `06-polish.ts` calls `completeText` and rewrites the WHOLE
 * note, so statics protected at L4 were still re-writable at L6. Protecting
 * them once and calling it done would have shipped a fix that LOOKS right and
 * still paraphrases the doctor's paragraph.
 */
export function findStaticDivergence(
  finalText: string,
  regions: readonly StaticRegion[]
): { sectionKey: string; label: string }[] {
  return regions
    .filter((r) => {
      if (r.text.trim().length === 0) return false;
      // ⚠️ POSITIONAL, NOT CONTAINMENT — AND THE CHANGE IS A BUG FIX. A plain
      // `finalText.includes(r.text)` is position-blind, so a polisher that
      // EMPTIED the doctor's section and appended its paragraph to the bottom
      // of another one produced a clean verdict: the bytes were still in the
      // document. `validateSoapStructure` also passes, because every heading is
      // present. The doctor gets a form whose protocol section is blank and
      // whose text sits under Findings, with no banner and no audit row.
      //
      // Not exotic: L6's own immutable preamble licenses "reword, REORGANIZE,
      // and reformat". The region must therefore still be under ITS OWN
      // heading, byte-for-byte.
      const body = sectionBody(finalText, r.label);
      return body === null || !body.includes(r.text);
    })
    .map((r) => ({ sectionKey: r.sectionKey, label: r.label }));
}
