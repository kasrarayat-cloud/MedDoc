// ============================================================================
// UPLOAD-AND-CERTIFIED · S1 — DOCX PROSE FORMS → DERIVED CONTROLS.
// ----------------------------------------------------------------------------
// A doctor uploads a Word form that is PROSE — labels ("PATIENT NAME:"), fill
// blanks ("Total time: ______"), section headings, body lines — with NO content
// controls. Today the twin compiler finds zero `w:sdt` and the upload quarantines
// `NO_FILLABLE_FIELDS` (create-draft.ts). This module is the missing step: it
// derives ONE content control per detected label / blank slot and writes them
// into `word/document.xml`, LAYOUT PRESERVED, so the SAME downstream twin path
// (compile → propose mappings → certify) can run — the regenerate-consult-form
// method (ruling #209) GENERALISED from one hand-coded form to any prose docx.
//
// ⚠️ THREE SAFETY INVARIANTS, because this transforms an UNTRUSTED upload and
// feeds the clinical pipeline:
//
//  1. INSERT-ONLY, BYTE-PRESERVING. Every original byte of `word/document.xml`
//     survives; the only change is `<w:sdt>…</w:sdt>` inserted before a matched
//     paragraph's closing `</w:p>`. No run is split, no paragraph rebuilt, no
//     property touched. This is what keeps Word able to open the result and what
//     preserves the doctor's layout — the same discipline as regenerate's
//     wrap-in-place, never a parse→serialize round-trip (fast-xml-parser is lossy
//     for OOXML and Word rejects the result).
//
//  2. SELF-VERIFY BY RE-COMPILE (the keystone). `deriveProseTwin` returns bytes
//     ONLY when the derived package re-compiles to EXACTLY the controls it
//     claims to have added — the caller passes a `verify` that runs the real
//     compiler and asserts (fieldCount === slots, 0 blocking, every field a
//     FILLABLE PLAIN-TEXT kind). `derivedTwinProbeIsValid` below is the ONE
//     reader of that rule; the caller and the gate both call it, never a private
//     copy. A `<w:text/>` control the compiler classifies as narrative_text OR
//     measurement OR number (a label "Weight:"/"Age:" is a legitimate
//     measurement/number, and demanding narrative_text alone would quarantine the
//     WHOLE form over one such label); it can never become a dropdown/date/
//     checkbox, so the plain-text set is exactly what an inserted control admits.
//     Any mismatch (a form shape this module handled wrong, a corrupted package)
//     returns null → the caller quarantines exactly as today.
//
//     ⚠️ WHAT THE KEYSTONE PROVES, AND WHAT IT DOES NOT. It proves the derived
//     package is well-formed and re-compiles to exactly the controls inserted —
//     no MALFORMED, mis-counted or corrupted twin is ever produced. It does NOT
//     prove the DETECTOR chose a real field: a control on a section heading or a
//     sentence would re-compile fine. That guarantee comes from detection
//     precision (invariant below): a slot must carry an explicit FILL AFFORDANCE.
//
//  3. NO-CONTROLS PRECONDITION. If the docx already has a `w:sdt`, this is not a
//     prose form — return null and let the normal path own it. We never add
//     controls to a form that already declares them.
//
// PRODUCE ONCE, PIN BY SHA (ruling #317): a derived twin's bytes are minted once
// per (source, algorithm) and its fieldIds are salted by the whole-package sha
// (compiler.ts `stableId`). JSZip is not a reproducible-archive writer, so a
// re-derivation is not byte-identical — callers persist the derived bytes, never
// re-derive "to get the same form".
// ============================================================================
import JSZip from 'jszip';

/** A slot the derivation decided to make fillable, in document order. */
export interface DerivedSlot {
  /** The control's `w:alias` — the doctor's own label (or a generic blank name).
   *  This becomes the field's `originalLabel` at compile time. */
  alias: string;
  /** The control's `w:tag`. Distinct per slot for a label; shared families are a
   *  later slice (numbered bullet groups, #313/#319 — deliberately NOT here). */
  tag: string;
  kind: 'label' | 'blank';
}

export interface DerivedProseTwin {
  /** The derived .docx bytes — produce once, pin, persist. */
  bytes: Uint8Array;
  /** The controls added, in document order. */
  slots: DerivedSlot[];
  /** The transformed `word/document.xml`, for proofs (byte-preservation, furniture-only). */
  documentXml: string;
  /** The original `word/document.xml`, for the byte-preservation proof. */
  sourceDocumentXml: string;
}

/**
 * The control's OOXML shape. ⚠️ IDENTICAL to `regenerate-consult-form.ts`'s
 * `sdt()` — that module self-executes `main()` on import so it cannot be imported,
 * and a gate (`gate-prose-twin`) asserts the two shapes stay identical so they
 * cannot drift. `<w:text/>` marks a plain-text control; `<w:alias>` is what the
 * compiler reads as the field label; the placeholder run is the visible prompt.
 */
export function proseControlSdt(alias: string, tag: string, id: number, inner: string): string {
  return (
    `<w:sdt><w:sdtPr><w:alias w:val="${xmlAttr(alias)}"/><w:tag w:val="${xmlAttr(tag)}"/>` +
    `<w:id w:val="${id}"/><w:text/></w:sdtPr><w:sdtContent>` +
    `<w:r><w:t xml:space="preserve">${xmlText(inner)}</w:t></w:r>` +
    `</w:sdtContent></w:sdt>`
  );
}

function xmlAttr(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function xmlText(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** The label detector: "LABEL: ____" or "LABEL ____". A fillable label is a short
 *  leading phrase FOLLOWED BY AN EXPLICIT FILL AFFORDANCE — a run of >=2
 *  underscores (a "blank line", the owner's reference-form marker), optionally
 *  after a colon.
 *
 *  ⚠️ THE AFFORDANCE IS REQUIRED, and that is a bug fix, not a policy change.
 *  This module's stated invariant is "leave anything not UNAMBIGUOUSLY a label or
 *  blank as static prose". A bare "LABEL:" (colon, nothing after) is NOT
 *  unambiguous: it is the exact shape of a section HEADING ("Assessment and
 *  Plan:", "Impression:", "Diagnosis:") and of a lead-in SENTENCE ("Findings were
 *  as follows:"), whose value is the prose BELOW, not an inline slot. Wrapping
 *  those planted a fillable control on a heading/sentence line (adversarial pass,
 *  2026-09-13). Requiring the affordance restores the invariant: a bare "LABEL:"
 *  falls through to static prose, and only a marked blank slot is derived. The
 *  same SHAPE as note-template-parse header-fields `LABEL_LINE_RE`, tightened to a
 *  WHOLE-paragraph match with a mandatory trailing blank.
 *
 *  ⚠️ THE COLON FORM (alt 1) DOES NOT ANCHOR THE LINE END; THE COLON-LESS FORM
 *  (alt 2) DOES. A `LABEL: ____` carries a strong fill signal (colon + affordance),
 *  so trailing furniture after the blank — a unit ("Total time: ____ minutes"), a
 *  format hint ("DOB: ____ (mm/dd/yyyy)"), or a second field — must NOT drop the
 *  line (adversarial pass, 2026-09-13); the lazy label capture still stops at the
 *  first colon, so the alias is the label. A COLON-LESS `LABEL ____` is far weaker
 *  (it is also the shape of a sentence with an embedded blank, "the patient was
 *  seen ____ for evaluation"), so it KEEPS the end anchor — the blank must end the
 *  line — or those sentences would be wrapped. */
const LABEL_PARAGRAPH_RE =
  /^[\s>*|•-]*([A-Za-z][A-Za-z0-9 .,/#()'’&-]{0,48}?)\s*:\s*_{2,}|^[\s>*|•-]*([A-Za-z][A-Za-z0-9 .,/#()'’&-]{0,48}?)\s+_{2,}[\s_.]*$/;

/** The paragraph's visible text (all `<w:t>` runs concatenated). ⚠️ Inter-run
 *  `<w:tab/>`, `<w:br/>` and `<w:cr/>` become a SPACE — a real Word form splits a
 *  wrapped/column-aligned label across runs with these ("Patient" `<w:tab/>`
 *  "Name"), and dropping them fused the derived alias to "PatientName" (adversarial
 *  pass, 2026-09-13). A space is the right separator for a LABEL (the compiler's
 *  own `visibleText` uses \t/\n; here a clean word gap is what the alias wants). */
function paragraphText(paragraphXml: string): string {
  let text = '';
  const re = /<w:t\b[^>]*>([\s\S]*?)<\/w:t>|<w:(?:tab|br|cr)\b[^>]*?\/?>/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(paragraphXml)) !== null) {
    text += m[1] !== undefined ? decodeXml(m[1]) : ' ';
  }
  return text;
}
function decodeXml(s: string): string {
  return s
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, '&');
}

/** A bare fill line: only underscores and whitespace, with a run of >=2
 *  underscores (the owner's "blank line" fill convention). Excludes decorative
 *  dividers of dashes/equals/bullets/asterisks/dots, which carry no fill
 *  affordance and are not slots. */
function isBlankFillLine(trimmed: string): boolean {
  return /^_{2,}$/.test(trimmed.replace(/\s+/g, ''));
}

/** A single leading LIST / ENUMERATION marker: a bullet, a numbered ordinal
 *  ("1." "1)" "1]" "(1)" "[1]"), or a checkbox glyph — each followed by
 *  whitespace. The `\s+` is load-bearing: it ensures the marker is a separate
 *  token, so a real label ("B12 level:") is never partly eaten.
 *
 *  ⚠️ SINGLE-LETTER MARKERS ("a." "a)" "(R)") ARE DELIBERATELY NOT STRIPPED.
 *  A single letter + punctuation is INDISTINGUISHABLE by shape from a clinical
 *  abbreviation or laterality — "T. Bili" (total bilirubin), "D. Bili" (direct),
 *  "T./N./M. Stage" (TNM), "(R) Knee" (right). Stripping them collapsed distinct
 *  labels to one alias and dropped laterality (adversarial pass, 2026-09-13). The
 *  cost of not stripping is only a lettered ordinal ("a) Allergies") keeping its
 *  ordinal in the alias — cosmetic, visible at the confirmation step — which is
 *  far preferable to a corrupted/collapsed clinical label. Only digit-led and
 *  checkbox markers, which do not collide with clinical shorthand, are stripped. */
const LEADING_MARKER_RE =
  /^\s*(?:[-*•▪◦·‣⁃>|]+|[([]?\d{1,3}[.)\]]|[☐☑☒□■▢◻◼✓✔])\s+/;

/** Strip ONE leading numbered/checkbox/bullet marker so a numbered FILL line
 *  ("1. Primary Dx: ___", "☐ Other: ___") is detected as one control whose alias
 *  is the LABEL, not the ordinal — the owner's S1 scope ("one control per label /
 *  blank / numbered slot"). Each numbered slot becomes its OWN control; numbered
 *  GROUPS as a shared field family are a later slice (#313/#319). The marker text
 *  is left VISIBLE in the paragraph (insert-only); only the derived alias drops
 *  it. (adversarial pass, 2026-09-13) */
function stripLeadingMarker(s: string): string {
  return s.replace(LEADING_MARKER_RE, '');
}

/** Classify one paragraph. Returns the alias to use, or null to leave it alone.
 *  Fail-safe: anything that is not unambiguously a label or a blank is left as
 *  static prose (headings, sentences, letterhead) — a form we only partly
 *  understand still yields a partly-filled twin, never a corrupted one. */
// ⚠️ EXPORTED so the S2-4 pdf-native export identifies the SAME fields this
// derivation created — ONE reader of "what is a field". The export re-detecting
// slots with its own marker/underscore regex drifted repeatedly (a "1. ______"
// numbered blank missed, a no-affordance "3." over-counted), transposing clinical
// values (adversarial pass, 2026-09-15). It now runs THIS over the same
// annotated line boxes. `text` is the affordance-ANNOTATED line (post
// annotateAffordances), exactly as the derivation classifies it.
export function classifyParagraph(text: string): { alias: string; kind: 'label' | 'blank' } | null {
  const trimmed = text.trim();
  if (trimmed.length === 0) return null; // truly empty paragraph — spacing, not a slot
  // Drop a leading list/enumeration marker ("1.", "a)", "☐", …) so a numbered or
  // checkbox fill line is detected with the LABEL as its alias, not the ordinal
  // (owner S1 scope: "numbered slot"). The marker stays visible in the paragraph.
  const marked = stripLeadingMarker(trimmed);
  // A bare fill BLANK: a run of underscores (the owner's "blank line" marker),
  // possibly segmented by spaces. ⚠️ It must be UNDERSCORES, not "any furniture":
  // a decorative divider ("======", "------", "• • •", "******") is NOT a fill
  // line and must stay static prose (adversarial pass, 2026-09-13). This is the
  // SAME affordance the label branch requires (>=2 underscores), applied to the
  // label-less case — a fill line is a fill line whether or not it has a label.
  if (isBlankFillLine(marked)) {
    return { alias: 'Fill-in', kind: 'blank' };
  }
  const m = LABEL_PARAGRAPH_RE.exec(marked);
  if (m) {
    const label = (m[1] ?? m[2] ?? '').trim();
    // A label must be more than punctuation and not absurdly long.
    if (label.length >= 2 && /[A-Za-z]/.test(label)) {
      return { alias: label, kind: 'label' };
    }
  }
  return null;
}

/**
 * Walk the DIRECT children of `<w:body>` and transform each body-level `<w:p>`.
 * Depth-aware: paragraphs inside `<w:tbl>`, an existing `<w:sdt>`, or a TEXT BOX
 * (`<w:txbxContent>`) are NOT touched (tables and text boxes are a different
 * slice; a form with pre-existing controls was excluded upstream). Returns the
 * transformed xml + the slots added in order.
 *
 * ⚠️ A TOKENIZER, NOT A REGEX SOUP. OOXML `<w:p>` can appear inside `<w:tbl>` and
 * `<w:sdt>`; a naive `<w:p>.*?</w:p>` would wrap the wrong thing. This scans the
 * body child by child, tracking element nesting, and only classifies a paragraph
 * that is a DIRECT body child.
 */
function injectControls(documentXml: string): { out: string; slots: DerivedSlot[] } {
  const bodyOpen = documentXml.match(/<w:body\b[^>]*>/);
  const bodyCloseIdx = documentXml.lastIndexOf('</w:body>');
  if (!bodyOpen || bodyCloseIdx < 0) return { out: documentXml, slots: [] };
  const bodyStart = bodyOpen.index! + bodyOpen[0].length;
  const head = documentXml.slice(0, bodyStart);
  const body = documentXml.slice(bodyStart, bodyCloseIdx);
  const tail = documentXml.slice(bodyCloseIdx);

  const slots: DerivedSlot[] = [];
  let out = '';
  let nextId = 990001; // high, fixed base — never collides with a form's own ids
  let seq = 0;

  // Split the body into top-level element blocks (paragraphs and everything else)
  // using a nesting-aware scan. We only transform blocks that are a single
  // top-level `<w:p …>…</w:p>`.
  for (const block of topLevelBlocks(body)) {
    if (!/^<w:p[\s>]/.test(block) || /^<w:p\b[^>]*\/>/.test(block)) {
      out += block;
      continue;
    }
    // ⚠️ A body paragraph that EMBEDS nested block content — a text box
    // (`<v:textbox>`/`<wps:txbx>` → `<w:txbxContent>`, VML or DrawingML) or any
    // other nested `<w:p>` — is NOT a simple prose line. Its visible fill label
    // lives in the INNER paragraph, so `paragraphText` would scrape the nested
    // text and the control would be inserted at the OUTER `</w:p>`, divorced from
    // its label (and two inner fields would collapse to one). A well-formed prose
    // paragraph opens exactly ONE `<w:p …>`; more than one means embedded content.
    // Leave it untouched — the same fail-safe as a table (a later slice). Found by
    // the adversarial pass, 2026-09-13.
    if ((block.match(/<w:p[\s>]/g) ?? []).length > 1) {
      out += block;
      continue;
    }
    const text = paragraphText(block);
    const decided = classifyParagraph(text);
    if (!decided) {
      out += block;
      continue;
    }
    seq += 1;
    const tag = `prose_${decided.kind}_${seq}`;
    const prompt = decided.kind === 'label' ? `Enter ${decided.alias}` : 'Enter value';
    const control = proseControlSdt(decided.alias, tag, nextId, prompt);
    nextId += 1;
    // Insert the control before the paragraph's closing tag — layout preserved,
    // the label/blank runs untouched, the control holds the value.
    const closeIdx = block.lastIndexOf('</w:p>');
    out += block.slice(0, closeIdx) + control + block.slice(closeIdx);
    slots.push({ alias: decided.alias, tag, kind: decided.kind });
  }

  return { out: head + out + tail, slots };
}

/** Yield the top-level element blocks of an OOXML fragment, nesting-aware. Text
 *  between elements (rare in document.xml) is yielded as its own block so nothing
 *  is dropped. */
function topLevelBlocks(fragment: string): string[] {
  const blocks: string[] = [];
  // ⚠️ MATCH ANY ELEMENT, NOT JUST `w:`. A depth counter that only tracks
  // `w:`-prefixed tags treats a `<w:p>` nested inside a NON-w: container
  // (`mc:AlternateContent`, `mc:Choice`, `mc:Fallback`, drawing `a:…`/`wp:…`
  // blocks) as a direct body child and double-wraps it (adversarial pass,
  // 2026-09-13). Tracking every qualified element keeps such a paragraph at
  // depth > 0, so the whole container passes through as one untouched top-level
  // block.
  //
  // ⚠️ TWO XML REALITIES THIS SCANNER MUST HONOUR, OR DEPTH DESYNCS AND A REAL
  // BODY-LEVEL `<w:p>` IS DROPPED (both found by the adversarial pass, 2026-09-13):
  //   1. A raw `>` is legal INSIDE a quoted attribute value — e.g. an inline
  //      image's `descr="a > b"`. A `[^>]*` attribute scan stops at that `>` and
  //      mis-reads a self-closing tag as an OPEN one. So the attribute run skips
  //      over quoted strings: `(?:"[^"]*"|'[^']*'|[^>"'])*?`.
  //   2. `<!-- … -->`, `<![CDATA[ … ]]>` and `<? … ?>` are OPAQUE: tag-like text
  //      inside them (`</w:p>` in a comment) must not drive depth. They are
  //      matched as whole spans and skipped (they never change depth; a top-level
  //      one is carried verbatim as stray text).
  const tokenRe =
    /<!--[\s\S]*?-->|<!\[CDATA\[[\s\S]*?\]\]>|<\?[\s\S]*?\?>|<(\/?)([A-Za-z_][\w.-]*(?::[A-Za-z_][\w.-]*)?)\b(?:"[^"]*"|'[^']*'|[^>"'])*?(\/?)>/g;
  let depth = 0;
  let blockStart = 0;
  let m: RegExpExecArray | null;
  let cursor = 0;
  while ((m = tokenRe.exec(fragment)) !== null) {
    if (depth === 0 && m.index > cursor) {
      // stray text between top-level elements
      blocks.push(fragment.slice(cursor, m.index));
      cursor = m.index;
    }
    // An opaque comment / CDATA / PI (no captured tag name) never changes depth;
    // its bytes fold into the surrounding stray text or enclosing block.
    if (m[2] === undefined) continue;
    const isClose = m[1] === '/';
    const isSelfClose = m[3] === '/';
    if (isSelfClose) {
      if (depth === 0) {
        blocks.push(fragment.slice(m.index, tokenRe.lastIndex));
        cursor = tokenRe.lastIndex;
      }
      continue;
    }
    if (!isClose) {
      if (depth === 0) blockStart = m.index;
      depth += 1;
    } else {
      depth -= 1;
      if (depth === 0) {
        blocks.push(fragment.slice(blockStart, tokenRe.lastIndex));
        cursor = tokenRe.lastIndex;
      }
    }
  }
  if (cursor < fragment.length) blocks.push(fragment.slice(cursor));
  return blocks;
}

/** The fillable plain-text kinds an inserted `<w:text/>` control can compile to.
 *  A label the compiler reads as a measurement ("Weight:") or a number
 *  ("Age:"/"…Score:") is still a fillable plain-text field — never a blocking
 *  control — so the keystone accepts all three. See invariant #2. */
const DERIVED_PLAIN_TEXT_KINDS: ReadonlySet<string> = new Set([
  'narrative_text',
  'measurement',
  'number',
]);

/**
 * THE KEYSTONE ACCEPTANCE PREDICATE — the ONE reader of "the derived package
 * re-compiled to exactly the controls we added". Both `create-draft.ts` (the real
 * path) and the S1 gate call this over a compiled probe, so they cannot drift.
 * Structural param (no compiler import) keeps this module a leaf.
 */
export function derivedTwinProbeIsValid(
  probe: { fields: ReadonlyArray<{ kind: string }>; stats: { blockingUnsupported: number } },
  expected: number,
): boolean {
  return (
    probe.fields.length === expected &&
    probe.stats.blockingUnsupported === 0 &&
    probe.fields.every((f) => DERIVED_PLAIN_TEXT_KINDS.has(f.kind))
  );
}

/**
 * Derive a fillable twin from a PROSE .docx. Returns null (→ caller quarantines
 * exactly as today) when: the package has no document.xml; it already has content
 * controls; no label/blank slot was detected; or — via the caller's `verify` —
 * the derived package does not re-compile to exactly the controls added.
 *
 * @param verify runs the REAL compiler on candidate bytes and returns whether it
 *   discovered exactly `expected` narrative_text fields with zero blocking. This
 *   is injected (not imported) so this module stays a leaf and the compiler's
 *   heavy graph is only pulled in by the caller.
 */
export async function deriveProseTwin(
  source: Uint8Array,
  verify: (bytes: Uint8Array, expected: number) => Promise<boolean>,
): Promise<DerivedProseTwin | null> {
  let zip: JSZip;
  try {
    zip = await JSZip.loadAsync(source);
  } catch {
    return null;
  }
  const entry = zip.file('word/document.xml');
  if (!entry) return null;
  const sourceDocumentXml = await entry.async('string');
  // No-controls precondition: a form that already declares controls is not ours.
  if (/<w:sdt[\s>]/.test(sourceDocumentXml)) return null;

  const { out, slots } = injectControls(sourceDocumentXml);
  if (slots.length === 0) return null;

  zip.file('word/document.xml', out);
  const bytes = await zip.generateAsync({ type: 'uint8array' });

  // ⚠️ THE KEYSTONE: ship these bytes ONLY if the real compiler agrees they carry
  // exactly the controls we added. Otherwise return null — the caller quarantines,
  // and no wrong twin is ever produced.
  const ok = await verify(bytes, slots.length);
  if (!ok) return null;

  return { bytes, slots, documentXml: out, sourceDocumentXml };
}
