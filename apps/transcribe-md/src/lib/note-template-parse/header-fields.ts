// ============================================================================
// Header/short-field capture (feat/template-header-fields, 2026-07-23).
// ----------------------------------------------------------------------------
// A doctor's operative-note form carries a labeled header block —
//   PATIENT NAME:  ___    PATIENT DOB:  ___    PATIENT ID #: ___
//   DATE OF SURGERY: ___  SURGEON: ___
// which dropAdministrativeChrome (phi-gate) removes from the note BODY because
// it is not clinical prose. But those labels ARE the doctor's form shape and
// must survive to the styled export. This module captures the field LABELS
// (never any patient value) DETERMINISTICALLY from the header region above the
// first clinical heading, maps each to a canonical fill key, and PHI-scans the
// label. Values are filled later, at export, from the visit record / dictation.
//
// Deterministic (no LLM): we fully control what is captured — labels only, from
// a curated set of patient/procedure header fields — so no patient value can
// leak in through model variance.
// ============================================================================
import type { NoteTemplateHeaderField } from '@/worker/note-templates/system-default-template';
import { firstClinicalHeadingIndex } from './reconcile-markers';
import { detectStructuredPhi } from './phi-gate';

/** Curated canonical field patterns. Each tests a label with its trailing
 *  colon/whitespace already stripped. Only patient/procedure header fields are
 *  captured — clinic letterhead / phone / address lines never match, so they
 *  are not pulled into the form header. */
const HEADER_FIELD_PATTERNS: ReadonlyArray<{ key: string; re: RegExp }> = [
  { key: 'patient_name', re: /^(?:patient(?:['’]s)?\s*name|name\s*of\s*patient|patient|name)$/i },
  {
    key: 'patient_dob',
    re: /^(?:patient(?:['’]s)?\s*)?(?:d\.?\s*o\.?\s*b\.?|date\s+of\s+birth|birth\s*date)$/i,
  },
  {
    key: 'patient_id',
    re: /^(?:patient(?:['’]s)?\s*)?(?:id\s*#?|i\.?\s*d\.?\s*(?:no\.?|number|#)?|mrn|medical\s+record\s*(?:no\.?|number|#)?|record\s*(?:no\.?|number|#))$/i,
  },
  {
    key: 'date_of_surgery',
    re: /^date\s+of\s+(?:surgery|procedure|operation|service)$|^(?:surgery|procedure|operation)\s+date$/i,
  },
  { key: 'surgeon', re: /^(?:operating\s+)?surgeon$|^proceduralist$|^operating\s+physician$/i },
];

/** Map a raw field label (with any trailing colon/whitespace) to a canonical
 *  fill key, or null when it is not a recognized patient/procedure header
 *  field. */
export function canonicalHeaderKey(label: string): string | null {
  const norm = label
    .replace(/[:#*_\s]+$/g, '')
    .replace(/^[\s*_>#-]+/, '')
    .trim();
  for (const { key, re } of HEADER_FIELD_PATTERNS) {
    if (re.test(norm)) return key;
  }
  return null;
}

// A labeled header line: LABEL followed by a colon (optionally a value we
// discard) OR LABEL followed by a run of underscores (a fill blank). The label
// is short (<= ~48 chars), starts with a letter, and avoids sentence prose.
const LABEL_LINE_RE =
  /^\s*[>*|\s-]*([A-Za-z][A-Za-z0-9 .,/#()'’&-]{0,48}?)\s*(?::|_{2,})/;

/**
 * Extract labeled header/short fields from the header region above the first
 * clinical heading. Returns ONLY recognized patient/procedure fields (by
 * canonical key), de-duplicated by key, in source order, with PHI-tainted
 * labels dropped. LABELS ONLY — never a value.
 */
export function extractHeaderFields(
  noteText: string,
  clinicalSections: { label: string }[]
): NoteTemplateHeaderField[] {
  const lines = noteText.split('\n');
  const boundary = firstClinicalHeadingIndex(noteText, clinicalSections);
  // firstClinicalHeadingIndex returns `lines.length` when NO section heading
  // matches — do NOT scan the whole note as header (a body "SURGEON:" line is
  // not a form field). Only a real in-note boundary (0 < b < length) delimits a
  // header region; anything else → no header fields.
  const headerEnd = boundary > 0 && boundary < lines.length ? boundary : 0;

  const out: NoteTemplateHeaderField[] = [];
  const seenKeys = new Set<string>();
  for (let i = 0; i < headerEnd; i++) {
    const m = lines[i].match(LABEL_LINE_RE);
    if (!m) continue;
    const rawLabel = m[1].trim();
    const key = canonicalHeaderKey(rawLabel);
    if (!key || seenKeys.has(key)) continue;
    // The label is generic form text — but guard anyway: a label that trips the
    // structured-PHI detector (e.g. a value glued into the label) is dropped.
    if (detectStructuredPhi(rawLabel).length > 0) continue;
    seenKeys.add(key);
    out.push({ key, label: rawLabel.replace(/\s*:\s*$/, ''), order: out.length + 1 });
  }
  return out;
}
