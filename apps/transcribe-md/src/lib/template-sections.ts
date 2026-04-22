// ============================================================================
// Template section detector (T-M24.smart — Phase 1)
// ----------------------------------------------------------------------------
// Read a doctor's uploaded .docx template (no {{tokens}}) and return a
// classified, ordered list of sections. Input is the raw zip buffer;
// output is a report-style view: what's letterhead, what's a clinical
// section we can map to a SUPPORTED_TOKEN, what's a table we should
// leave verbatim, what's signature / disclaimer / boilerplate.
//
// Design constraints for Phase 2 auto-token injection:
//   1. We must produce a deterministic mapping heading→token so the
//      injection step is reproducible (no Claude call here).
//   2. Tables MUST be detectable — Range-of-Motion tables etc. can't be
//      rewritten as text, and mammoth-based text extraction loses the
//      structure. We look at `<w:tbl>` elements directly.
//   3. Letterhead / signature / disclaimer detection is conservative:
//      only obvious markers (credential tail, "Disclaimer" heading,
//      salutation phrases). Everything ambiguous stays classified as
//      `boilerplate` so the injector preserves it verbatim.
// ============================================================================

import PizZip from 'pizzip';

import { SUPPORTED_TOKENS, type SupportedToken } from './template-tokens';

// ---------------------------------------------------------------------------
// XML block types
// ---------------------------------------------------------------------------

interface BlockOffsets {
  /** Byte offset of this block's opening tag inside the body string
   *  (i.e., inside xml[bodyStart..bodyEnd]). The injector uses these
   *  to slice the original XML surgically while replacing ranges. */
  startOffset: number;
  /** Offset immediately AFTER this block's closing tag. */
  endOffset: number;
}

interface ParaBlock extends BlockOffsets {
  kind: 'para';
  text: string;
  isBold: boolean;
  isAllCaps: boolean;
  styleId: string | null;
}

interface TableBlock extends BlockOffsets {
  kind: 'table';
  rowCount: number;
  /** Flattened cell text for preview / matching. */
  text: string;
}

export type Block = ParaBlock | TableBlock;

// ---------------------------------------------------------------------------
// Detected-section type
// ---------------------------------------------------------------------------

export type SectionContentType =
  | 'letterhead'
  | 'metadata'
  | 'salutation'
  | 'clinical_narrative'
  | 'clinical_table'
  | 'sub_section'
  | 'signature'
  | 'disclaimer'
  | 'boilerplate';

export type HeadingType = 'all_caps' | 'title_case' | 'bold' | 'styled' | 'none';

export interface DetectedSection {
  heading: string | null;
  headingType: HeadingType;
  contentType: SectionContentType;
  mappedToken: SupportedToken | null;
  preview: string;
  blockCount: number;
  hasTable: boolean;
  /** Indices into the Block[] array returned by parseBlocks. `start`
   *  is the first block touched (the heading, when one exists);
   *  `end` is the last block (inclusive). `null` for synthesised
   *  sections (e.g., signature) that span a range but where the
   *  heading was not a real block. The injector uses this to slice
   *  the right body range. */
  blockRange: { start: number; end: number } | null;
  /** True when the heading paragraph also contains inline content on
   *  the same paragraph ("Medications This Visit:\tGabapentin…").
   *  The injector distinguishes: when this is true we must replace
   *  the entire heading paragraph (heading + inline tail → heading +
   *  {{token}}); when false we keep the heading paragraph verbatim
   *  and replace subsequent body paragraphs. */
  headingHasInlineContent: boolean;
}

// ---------------------------------------------------------------------------
// Heading → token mapping
// ---------------------------------------------------------------------------

const HEADING_TO_TOKEN: Array<{ patterns: RegExp[]; token: SupportedToken }> = [
  // --- primary SOAP ---
  {
    patterns: [/^chief\s*complaints?\b/i, /^cc\b/i, /^presenting\s+complaint/i],
    token: 'chief_complaint',
  },
  {
    patterns: [
      /^history\s+of\s+present\s+illness\b/i,
      /^hpi\b/i,
      /^present\s+illness\b/i,
    ],
    token: 'hpi',
  },
  {
    patterns: [/^review\s+of\s+systems?\b/i, /^ros\b/i],
    token: 'ros',
  },
  {
    patterns: [
      /^physical\s+examinations?\b/i,
      /^physical\s+exam\b/i,
      /^\bpe\b/i,
      /^exam\b/i,
      /^examinations?\b/i,
    ],
    token: 'exam',
  },
  {
    patterns: [
      /^assessments?\b/i,
      /^diagnostic\s+impressions?\b/i,
      /^impressions?\b/i,
      /^clinical\s+impression/i,
    ],
    token: 'assessment',
  },
  {
    patterns: [
      /^plan\b/i,
      /^treatment\s+plan\b/i,
      /^discussion\s+and\s+recommendations/i,
      /^recommendations?\b/i,
    ],
    token: 'plan',
  },
  {
    patterns: [
      /^medications?\b/i,
      /^current\s+medications?\b/i,
      /^meds?\b/i,
      /^active\s+medications?\b/i,
      // Gap 2: Dr M's template uses "Medications This Visit:\tGabapentin…"
      // — one paragraph with label + value tab-separated. Same intent
      // as "Medications" so mapped to the same token.
      /^medications\s+this\s+visit\b/i,
      /^visit\s+medications\b/i,
    ],
    token: 'medications',
  },
  {
    patterns: [/^allergies\b/i, /^drug\s+allergies\b/i, /^known\s+allergies\b/i],
    token: 'allergies',
  },
  {
    patterns: [
      /^past\s+medical\s+history\b/i,
      /^pmh\b/i,
      /^medical\s+history\b/i,
    ],
    token: 'pmh',
  },
  // --- clinical sub-sections (Lever 2) ---
  {
    patterns: [/^current\s+status\b/i, /^functional\s+status\b/i],
    token: 'current_status',
  },
  {
    patterns: [/^prior\s+injur(y|ies)\b/i, /^previous\s+injur(y|ies)\b/i],
    token: 'prior_injuries',
  },
  {
    patterns: [/^social\s+history\b/i, /^sh\b/i],
    token: 'social_history',
  },
  {
    patterns: [/^family\s+history\b/i, /^fh\b/i, /^family\s+medical\s+history\b/i],
    token: 'family_history',
  },
  {
    patterns: [/^past\s+surgical\s+history\b/i, /^psh\b/i, /^surgical\s+history\b/i],
    token: 'past_surgical_history',
  },
  {
    patterns: [
      /^imaging\b/i,
      /^mri\s+of/i,
      /^ct\s+(of|scan)/i,
      /^x-?ray(s)?\b/i,
      /^diagnostic\s+imaging\b/i,
      /^radiolog(y|ic\s+findings)/i,
    ],
    token: 'imaging',
  },
  {
    patterns: [/^general\b/i, /^general\s+(exam|appearance)\b/i, /^vitals?\b/i],
    token: 'general_exam',
  },
  {
    patterns: [/^heent\b/i, /^head\s+and\s+neck\b/i],
    token: 'heent',
  },
  {
    patterns: [
      /^lumbar\s+spine\b/i,
      /^lumbosacral\s+spine\b/i,
      /^low\s+back\s+exam\b/i,
    ],
    token: 'lumbar_spine',
  },
  {
    patterns: [/^right\s+lower\s+extremity\b/i, /^r\s+lower\s+extremity\b/i],
    token: 'right_lower_extremity',
  },
  {
    patterns: [/^left\s+lower\s+extremity\b/i, /^l\s+lower\s+extremity\b/i],
    token: 'left_lower_extremity',
  },
  {
    patterns: [/^reflexes\b/i, /^deep\s+tendon\s+reflexes\b/i, /^dtrs?\b/i],
    token: 'reflexes',
  },
  {
    patterns: [/^integument\b/i, /^skin(\s+exam)?\b/i, /^dermatolog/i],
    token: 'integument',
  },
];

// T-M24.smart Lever 1 — metadata labels in the header row. Tab/space
// delimiter between label and value is typical ("Patient:\tKasra Rayat");
// the reclassifier below promotes the block to clinical_narrative with
// the matching token so the injector's replace_inline step rewrites
// the whole row as "Patient:\t{{patient_name}}".
const METADATA_LABEL_TO_TOKEN: Array<{ patterns: RegExp[]; token: SupportedToken }> = [
  {
    patterns: [/^(patient|pt)\s*[:\t]/i],
    token: 'patient_name',
  },
  {
    patterns: [/^(d\.?o\.?b\.?|date\s+of\s+birth)\s*[:\t]/i],
    token: 'patient_dob',
  },
  {
    patterns: [/^(d\.?o\.?i\.?|date\s+of\s+injury)\s*[:\t]/i],
    token: 'date_of_injury',
  },
];

// Standalone date — March 3, 2026 / 03/03/2026 / 3-3-2026 — sitting
// by itself on a pre-clinical line. Promoted to visit_date when it's
// the ONLY content of the paragraph (we don't want to match dates
// embedded inside prose).
const STANDALONE_DATE_RE =
  /^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}$|^\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}$/i;

function mapMetadataToToken(text: string): SupportedToken | null {
  const trimmed = text.trim();
  for (const entry of METADATA_LABEL_TO_TOKEN) {
    for (const re of entry.patterns) {
      if (re.test(trimmed)) return entry.token;
    }
  }
  if (STANDALONE_DATE_RE.test(trimmed)) return 'visit_date';
  return null;
}

// Keywords that mark a section as boilerplate (disclaimer / legal / fee
// schedule / insurance advisory — stuff we never rewrite).
const BOILERPLATE_KEYWORDS =
  /\b(disclaimer|legal|liability|pursuant|insurance|license|warranty|advisory|notice|business\s+and\s+professions|california\s+law)\b/i;

const CREDENTIAL_TAIL =
  /\b(M\.?D\.?|D\.?O\.?|Ph\.?D\.?|N\.?P\.?|P\.?A\.?|D\.?C\.?|L\.?Ac\.?|D\.?P\.?T\.?)\b/;

const SALUTATION_RE =
  /^(to\s+whom\s+it\s+may\s+concern|dear\s+\S|hello\s+\S|greetings)/i;

// Gap 1 — signature detection. The anchor pattern is "Firstname Lastname,
// M.D." (with optional middle initial); the continuation pattern is the
// credential-adjacent tagline line that commonly follows ("Board Certified
// Anesthesiologist, Interventional Pain Management"); the closing pattern
// is the letter-style close ("Thank you for allowing me...") that
// immediately precedes the signature in consultation letters.
//
// Using these together lets us carve out a clean "signature region" the
// injector must never consume — even though none of these paragraphs are
// detected as headings by the standard Title-Case / ALL-CAPS rules.
const SIGNATURE_NAME_RE =
  /^[A-Z][a-zA-Z]+(?:\s+(?:[A-Z]\.?|[A-Z][a-zA-Z]+))*,?\s+(?:M\.?D\.?|D\.?O\.?|Ph\.?D\.?|N\.?P\.?|P\.?A\.?|D\.?C\.?|L\.?Ac\.?|D\.?P\.?T\.?)\b/;

const CREDENTIAL_CONTINUATION_RE =
  /\b(board\s+certified|licensed|interventional|pediatric|internal|family\s+medicine|emergency|cardiology|anesthesiology|anesthesiologist|physician|surgeon|psychiatrist|neurologist|orthopedic|orthopaedic|specialist|diplomate)\b/i;

const CLOSING_PHRASE_RE =
  /^(thank\s+you|please\s+(do\s+not|don'?t)\s+hesitate|sincerely|best\s+regards|respectfully|warm\s+regards|with\s+regards|warmly|yours\s+truly|kind\s+regards)\b/i;

// ---------------------------------------------------------------------------
// XML walk — body-level <w:p> and <w:tbl> only.
// ---------------------------------------------------------------------------

export function parseBlocks(xml: string): Block[] {
  const bodyStart = xml.indexOf('<w:body>');
  const bodyEnd = xml.indexOf('</w:body>');
  if (bodyStart < 0 || bodyEnd < 0) return [];
  const body = xml.slice(bodyStart + '<w:body>'.length, bodyEnd);

  const blocks: Block[] = [];
  let cursor = 0;

  while (cursor < body.length) {
    const pIdx = nextTagIndex(body, '<w:p', cursor);
    const tblIdx = nextTagIndex(body, '<w:tbl', cursor);

    if (pIdx < 0 && tblIdx < 0) break;

    let start: number;
    let tag: 'p' | 'tbl';
    if (pIdx < 0) {
      start = tblIdx;
      tag = 'tbl';
    } else if (tblIdx < 0) {
      start = pIdx;
      tag = 'p';
    } else if (pIdx < tblIdx) {
      start = pIdx;
      tag = 'p';
    } else {
      start = tblIdx;
      tag = 'tbl';
    }

    const openClose = body.indexOf('>', start);
    if (openClose < 0) break;
    const isSelfClose = body[openClose - 1] === '/';

    if (isSelfClose) {
      if (tag === 'p') {
        blocks.push({
          kind: 'para',
          text: '',
          isBold: false,
          isAllCaps: false,
          styleId: null,
          startOffset: start,
          endOffset: openClose + 1,
        });
      }
      cursor = openClose + 1;
      continue;
    }

    const closeTag = `</w:${tag}>`;
    let end: number;
    if (tag === 'p') {
      end = body.indexOf(closeTag, openClose + 1);
    } else {
      end = findMatchingClose(body, '<w:tbl', closeTag, openClose + 1);
    }
    if (end < 0) break;

    const inner = body.slice(openClose + 1, end);
    const blockEndOffset = end + closeTag.length;
    blocks.push(
      tag === 'p'
        ? parseParagraph(inner, start, blockEndOffset)
        : parseTable(inner, start, blockEndOffset)
    );
    cursor = blockEndOffset;
  }

  return blocks;
}

/** Return the absolute offset range of the body string inside xml.
 *  Callers need this to translate the relative offsets on Block into
 *  absolute positions in the XML for surgical slicing. */
export function bodyRange(xml: string): { start: number; end: number } {
  const openIdx = xml.indexOf('<w:body>');
  const closeIdx = xml.indexOf('</w:body>');
  if (openIdx < 0 || closeIdx < 0) throw new Error('word/document.xml has no <w:body>');
  return { start: openIdx + '<w:body>'.length, end: closeIdx };
}

/** Find the next `tag` occurrence that is a real element start (not a
 *  prefix of another element like `<w:pPr` or `<w:tblPr`). Returns -1
 *  when no more are present. */
function nextTagIndex(body: string, tag: string, from: number): number {
  let scan = from;
  while (scan < body.length) {
    const idx = body.indexOf(tag, scan);
    if (idx < 0) return -1;
    const next = body[idx + tag.length];
    if (next === ' ' || next === '>' || next === '/') return idx;
    scan = idx + tag.length;
  }
  return -1;
}

function findMatchingClose(
  body: string,
  openTag: string,
  closeTag: string,
  from: number
): number {
  let depth = 1;
  let scan = from;
  while (scan < body.length) {
    const no = nextTagIndex(body, openTag, scan);
    const nc = body.indexOf(closeTag, scan);
    if (nc < 0) return -1;
    if (no >= 0 && no < nc) {
      depth++;
      scan = no + openTag.length;
    } else {
      depth--;
      if (depth === 0) return nc;
      scan = nc + closeTag.length;
    }
  }
  return -1;
}

function parseParagraph(
  inner: string,
  startOffset: number,
  endOffset: number
): ParaBlock {
  const styleMatch = inner.match(/<w:pStyle\s+w:val="([^"]+)"/);
  const styleId = styleMatch?.[1] ?? null;

  // "Bold" = the paragraph's pPr has <w:b/>, OR the first run's rPr has <w:b/>.
  // Either indicates the default run is bold (inline unbold runs would
  // be rare for heading paragraphs).
  const pPr = inner.match(/<w:pPr\b[^>]*>([\s\S]*?)<\/w:pPr>/)?.[1] ?? '';
  const firstRPr =
    inner.match(/<w:r\b[^>]*>[\s\S]*?<w:rPr\b[^>]*>([\s\S]*?)<\/w:rPr>/)?.[1] ??
    '';
  const isBold = /<w:b\s*\/?>/.test(pPr) || /<w:b\s*\/?>/.test(firstRPr);

  // Text: join <w:t> runs in order, converting <w:tab/> → \t, <w:br/> → \n.
  let text = '';
  const TEXT_RE =
    /<w:t(?:\s+[^>]*)?>([^<]*)<\/w:t>|<w:tab\s*\/?>|<w:br\s*\/?>/g;
  for (const m of inner.matchAll(TEXT_RE)) {
    if (m[1] !== undefined) {
      text += m[1];
    } else if (m[0].startsWith('<w:tab')) {
      text += '\t';
    } else {
      text += '\n';
    }
  }
  text = decodeXmlEntities(text);

  const trimmed = text.trim();
  const isAllCaps =
    trimmed.length > 0 &&
    trimmed === trimmed.toUpperCase() &&
    /[A-Z]/.test(trimmed);

  return { kind: 'para', text, isBold, isAllCaps, styleId, startOffset, endOffset };
}

function parseTable(
  inner: string,
  startOffset: number,
  endOffset: number
): TableBlock {
  const rowCount = (inner.match(/<w:tr\b/g) ?? []).length;
  let text = '';
  const TEXT_RE = /<w:t(?:\s+[^>]*)?>([^<]*)<\/w:t>/g;
  for (const m of inner.matchAll(TEXT_RE)) {
    text += m[1] + ' ';
  }
  text = decodeXmlEntities(text).trim().replace(/\s+/g, ' ');
  return { kind: 'table', rowCount, text, startOffset, endOffset };
}

function decodeXmlEntities(s: string): string {
  return s
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'");
}

// ---------------------------------------------------------------------------
// Classification
// ---------------------------------------------------------------------------

/** Gap 2 helper — detect `Label:\t<value>` or `Label:  <value>` (colon
 *  followed by tab or 2+ spaces). Returns the label prefix (with colon)
 *  when the label looks heading-shaped: 1-4 Title-Case / ALL-CAPS
 *  words, no leading punctuation, ≥ 3 chars. Otherwise null. */
function labelPrefixIfTabDelimited(text: string): string | null {
  const m =
    text.match(/^((?:[A-Z][A-Za-z]*\s*){1,4}[A-Za-z]):[ \t]{2,}/) ||
    text.match(/^((?:[A-Z][A-Za-z]*\s*){1,4}[A-Za-z]):\t+/);
  if (!m) return null;
  const label = m[1].trim();
  if (label.length < 3) return null;
  return `${label}:`;
}

function isProbablyHeading(block: ParaBlock): boolean {
  const t = block.text.trim();
  if (!t) return false;
  // Gap 4 — minimum length + reject leading punctuation. "*Pain" was
  // the prior false positive; anything starting with *, -, •, ◦, :,
  // etc. is never a real section heading.
  if (t.length < 3) return false;
  if (/^[^A-Za-z0-9]/.test(t)) return false;
  if (t.length > 120) {
    // Gap 2 fallback — long paragraphs where the *prefix* is a tab-
    // delimited label still qualify as headings. Splits happen later
    // in splitHeadingInline.
    return labelPrefixIfTabDelimited(t) !== null;
  }
  if (block.styleId && /^Heading/i.test(block.styleId)) return true;
  // ALL CAPS short line — strongest heading signal in consult letters.
  if (block.isAllCaps && /[A-Z]/.test(t)) return true;
  // Bold + short — common in Title-Case heading style.
  if (block.isBold && t.length <= 80) return true;
  // "Label:" on short line — Title Case ending in colon. Skip obvious
  // salutations and sentence-shaped paragraphs.
  if (t.endsWith(':') && t.length <= 80 && !SALUTATION_RE.test(t)) {
    const words = t.slice(0, -1).split(/\s+/);
    const caps = words.filter((w) => /^[A-Z]/.test(w)).length;
    if (caps / words.length >= 0.5) return true;
  }
  // Gap 2 — "Label:<tab>value" inside a short paragraph.
  if (labelPrefixIfTabDelimited(t) !== null) return true;
  return false;
}

function mapHeadingToToken(heading: string): SupportedToken | null {
  const norm = heading.replace(/:\s*$/, '').trim();
  for (const entry of HEADING_TO_TOKEN) {
    for (const re of entry.patterns) {
      if (re.test(norm)) return entry.token;
    }
  }
  return null;
}

function headingTypeOf(b: ParaBlock): HeadingType {
  if (b.styleId && /^Heading/i.test(b.styleId)) return 'styled';
  if (b.isAllCaps) return 'all_caps';
  if (b.isBold) return 'bold';
  return 'title_case';
}

/** Split "HEADING: inline content here." → ["HEADING:", "inline content here."].
 *  Also handles the Gap-2 case "Label:\tvalue" / "Label:  value" where
 *  the separator between label and value is a tab or ≥2 spaces. */
function splitHeadingInline(text: string): { heading: string; tail: string } {
  const trimmed = text.trim();
  // Tab/wide-space delimited labels take priority: we only want the
  // label prefix as the heading even if the value has more colons in
  // it ("Medications This Visit:\tGabapentin 300 mg #90.").
  const labelPrefix = labelPrefixIfTabDelimited(trimmed);
  if (labelPrefix) {
    const tail = trimmed.slice(labelPrefix.length).trim();
    return { heading: labelPrefix, tail };
  }
  const colonIdx = trimmed.indexOf(':');
  if (colonIdx < 0 || colonIdx === trimmed.length - 1) {
    return { heading: trimmed, tail: '' };
  }
  const tail = trimmed.slice(colonIdx + 1).trim();
  if (!tail) return { heading: trimmed, tail: '' };
  return { heading: trimmed.slice(0, colonIdx + 1), tail };
}

/** Gap 1 — locate the contiguous signature region at the tail of the
 *  document (inclusive range in `blocks`). The region spans:
 *    - an anchor paragraph matching SIGNATURE_NAME_RE ("Bobby
 *      Moussazadeh, M.D.") in the last 40% of blocks;
 *    - forward: up to 3 credential-continuation lines ("Board Certified
 *      Anesthesiologist…");
 *    - backward: up to 2 letter-closing paragraphs ("Thank you for
 *      allowing me to participate…") that immediately precede the
 *      anchor — otherwise the {{medications}} or {{plan}} injection
 *      directly above would eat them.
 *
 *  Returns null when no signature-shaped paragraph is found. */
function findSignatureRange(
  blocks: Block[]
): { start: number; end: number } | null {
  const scanStart = Math.floor(blocks.length * 0.6);
  let anchor = -1;
  for (let i = scanStart; i < blocks.length; i++) {
    const b = blocks[i];
    if (b.kind !== 'para') continue;
    if (SIGNATURE_NAME_RE.test(b.text.trim())) {
      anchor = i;
      break;
    }
  }
  if (anchor < 0) return null;

  let end = anchor;
  for (let i = anchor + 1; i < blocks.length && i - anchor < 4; i++) {
    const b = blocks[i];
    if (b.kind !== 'para') break;
    const t = b.text.trim();
    if (!t) continue;
    if (CREDENTIAL_CONTINUATION_RE.test(t) || SIGNATURE_NAME_RE.test(t)) {
      end = i;
    } else {
      break;
    }
  }

  let start = anchor;
  let closingsConsumed = 0;
  for (let i = anchor - 1; i >= 0 && closingsConsumed < 2; i--) {
    const b = blocks[i];
    if (b.kind !== 'para') break;
    const t = b.text.trim();
    if (!t) continue;
    if (CLOSING_PHRASE_RE.test(t)) {
      start = i;
      closingsConsumed++;
    } else {
      break;
    }
  }

  return { start, end };
}

/** Classify the set of trailing non-clinical sections at the end of
 *  the document as signature + disclaimer when the heuristics match.
 *  Mutates `sections` in place. */
function reclassifyTail(sections: DetectedSection[]): void {
  // Walk backwards from the end; stop at the last section whose token
  // is non-null (the last mapped clinical section).
  let lastClinicalIdx = -1;
  for (let i = sections.length - 1; i >= 0; i--) {
    if (sections[i].mappedToken) {
      lastClinicalIdx = i;
      break;
    }
  }
  for (let i = lastClinicalIdx + 1; i < sections.length; i++) {
    const s = sections[i];
    const hay = `${s.heading ?? ''} ${s.preview}`;
    if (BOILERPLATE_KEYWORDS.test(hay)) {
      s.contentType = 'disclaimer';
      continue;
    }
    // Signature: a short paragraph with credential tail — "Bobby
    // Moussazadeh, M.D." / "Board Certified Anesthesiologist".
    if (
      CREDENTIAL_TAIL.test(hay) &&
      s.blockCount <= 4 &&
      s.preview.length <= 200
    ) {
      s.contentType = 'signature';
      continue;
    }
  }
}

/** Letterhead classifier for pre-clinical blocks. */
function classifyPreClinical(block: Block): SectionContentType {
  if (block.kind === 'table') return 'letterhead';
  const t = block.text.trim();
  if (SALUTATION_RE.test(t)) return 'salutation';
  // Metadata: "Patient: ...", "DOB: ...", "DOI: ...", dates, MRN — anything
  // that looks like a labeled key/value header line.
  if (
    /^(patient|pt|dob|date of birth|doi|date of injury|mrn|visit date|date|age|sex|gender)\b\s*[:\t]/i.test(
      t
    ) ||
    /^\d{1,2}\/\d{1,2}\/\d{2,4}\b/.test(t) ||
    /^(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d/i.test(
      t
    )
  ) {
    return 'metadata';
  }
  return 'letterhead';
}

// ---------------------------------------------------------------------------
// Public entry
// ---------------------------------------------------------------------------

export function detectSections(buffer: Buffer): DetectedSection[] {
  const zip = new PizZip(buffer);
  const xml = zip.file('word/document.xml')?.asText();
  if (!xml) throw new Error('word/document.xml missing');
  const blocks = parseBlocks(xml);
  return classify(blocks);
}

function classify(blocks: Block[]): DetectedSection[] {
  const headingFlags = blocks.map((b) =>
    b.kind === 'para' ? isProbablyHeading(b) : false
  );
  const signatureRange = findSignatureRange(blocks);

  // Find the first heading that maps to a clinical token. Everything
  // before it is letterhead/metadata/salutation.
  let firstClinicalIdx = -1;
  for (let i = 0; i < blocks.length; i++) {
    if (!headingFlags[i]) continue;
    const p = blocks[i] as ParaBlock;
    const { heading } = splitHeadingInline(p.text);
    if (mapHeadingToToken(heading)) {
      firstClinicalIdx = i;
      break;
    }
  }

  const sections: DetectedSection[] = [];

  // Pre-clinical: each non-empty block becomes its own "section" so
  // the report shows letterhead lines distinctly. Lever 1 — blocks
  // carrying a metadata label (Patient:, DOB:, DOI:) or a standalone
  // date get promoted to clinical_narrative so the injector rewrites
  // their value portion per-visit. Letterhead stays as-is.
  const preEnd = firstClinicalIdx < 0 ? blocks.length : firstClinicalIdx;
  for (let i = 0; i < preEnd; i++) {
    const b = blocks[i];
    if (b.kind === 'para' && !b.text.trim()) continue;
    const preview =
      b.kind === 'para' ? b.text.trim() : `[table, ${b.rowCount} rows] ${b.text}`;

    let contentType: SectionContentType = classifyPreClinical(b);
    let mappedToken: SupportedToken | null = null;
    let heading: string | null = null;
    let headingHasInlineContent = false;

    if (b.kind === 'para') {
      const token = mapMetadataToToken(b.text);
      if (token) {
        contentType = 'clinical_narrative';
        mappedToken = token;
        // Extract the label prefix for replace_inline: "Patient:",
        // "DOB:", "DOI:". Standalone dates have no label → empty
        // heading, and the injector emits `{{visit_date}}` alone.
        if (token === 'visit_date') {
          heading = '';
          headingHasInlineContent = true;
        } else {
          const { heading: h } = splitHeadingInline(b.text);
          heading = h;
          headingHasInlineContent = true;
        }
      }
    }

    sections.push({
      heading,
      headingType: mappedToken ? 'bold' : 'none',
      contentType,
      mappedToken,
      preview: preview.slice(0, 120),
      blockCount: 1,
      hasTable: b.kind === 'table',
      blockRange: { start: i, end: i },
      headingHasInlineContent,
    });
  }

  // Main body: walk from first clinical heading onward. Headings delimit
  // sections; tables attach to the current section.
  let cur: {
    heading: string;
    headingType: HeadingType;
    paragraphs: string[];
    tableCount: number;
    token: SupportedToken | null;
    blockStart: number;
    blockEnd: number;
    headingHasInlineContent: boolean;
  } | null = null;

  const flush = () => {
    if (!cur) return;
    let contentType: SectionContentType;
    if (cur.tableCount > 0) {
      contentType = 'clinical_table';
    } else if (cur.token) {
      contentType = 'clinical_narrative';
    } else if (BOILERPLATE_KEYWORDS.test(cur.heading)) {
      contentType = 'boilerplate';
    } else if (
      CREDENTIAL_TAIL.test(cur.heading) ||
      CREDENTIAL_TAIL.test(cur.paragraphs.join(' '))
    ) {
      contentType = 'signature';
    } else {
      contentType = 'sub_section';
    }
    const content = cur.paragraphs.join(' ').trim();
    sections.push({
      heading: cur.heading,
      headingType: cur.headingType,
      contentType,
      mappedToken: cur.token,
      preview: content.slice(0, 120),
      blockCount: cur.paragraphs.length + cur.tableCount,
      hasTable: cur.tableCount > 0,
      blockRange: { start: cur.blockStart, end: cur.blockEnd },
      headingHasInlineContent: cur.headingHasInlineContent,
    });
    cur = null;
  };

  for (let i = preEnd; i < blocks.length; i++) {
    // Gap 1 — the signature region is a hard boundary. When we reach
    // it, flush whatever clinical section is open and emit a single
    // `signature` section spanning the full range. Skip past `end`
    // so the inner paragraphs don't get reprocessed.
    if (signatureRange && i === signatureRange.start) {
      flush();
      const sigBlocks = blocks.slice(signatureRange.start, signatureRange.end + 1);
      const sigText = sigBlocks
        .map((b) => (b.kind === 'para' ? b.text.trim() : b.text))
        .filter(Boolean)
        .join(' ')
        .replace(/\s+/g, ' ');
      sections.push({
        heading: null,
        headingType: 'none',
        contentType: 'signature',
        mappedToken: null,
        preview: sigText.slice(0, 120),
        blockCount: sigBlocks.length,
        hasTable: false,
        blockRange: { start: signatureRange.start, end: signatureRange.end },
        headingHasInlineContent: false,
      });
      i = signatureRange.end;
      continue;
    }
    const b = blocks[i];
    if (b.kind === 'para' && headingFlags[i]) {
      flush();
      const p = b as ParaBlock;
      const { heading, tail } = splitHeadingInline(p.text);
      cur = {
        heading,
        headingType: headingTypeOf(p),
        paragraphs: tail ? [tail] : [],
        tableCount: 0,
        token: mapHeadingToToken(heading),
        blockStart: i,
        blockEnd: i,
        headingHasInlineContent: tail.length > 0,
      };
    } else if (b.kind === 'para') {
      if (cur) {
        const t = b.text.trim();
        if (t) cur.paragraphs.push(t);
        cur.blockEnd = i;
      } else if (b.text.trim()) {
        // Trailing paragraph with no containing heading — likely a
        // closing line or orphaned content. Keep as boilerplate.
        sections.push({
          heading: null,
          headingType: 'none',
          contentType: 'boilerplate',
          mappedToken: null,
          preview: b.text.trim().slice(0, 120),
          blockCount: 1,
          hasTable: false,
          blockRange: { start: i, end: i },
          headingHasInlineContent: false,
        });
      }
    } else {
      if (cur) {
        cur.tableCount++;
        cur.blockEnd = i;
      } else {
        sections.push({
          heading: null,
          headingType: 'none',
          contentType: 'clinical_table',
          mappedToken: null,
          preview: `[table, ${b.rowCount} rows] ${b.text.slice(0, 80)}`,
          blockCount: 1,
          hasTable: true,
          blockRange: { start: i, end: i },
          headingHasInlineContent: false,
        });
      }
    }
  }
  flush();

  // Post-pass: reclassify the trailing sections as signature / disclaimer
  // when their text matches credential or legal-boilerplate markers.
  reclassifyTail(sections);

  return sections;
}

// Export for ad-hoc tests.
export const _TOKEN_MAPPINGS = HEADING_TO_TOKEN;
export const _SUPPORTED_TOKENS = SUPPORTED_TOKENS;
