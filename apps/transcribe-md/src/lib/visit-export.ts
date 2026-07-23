// ============================================================================
// Pure visit-export types + helpers (T-M7)
// ----------------------------------------------------------------------------
// This module is safe to import from client components. The Prisma-
// touching loader lives in visit-export-server.ts — keeping it there
// prevents @prisma/adapter-pg from reaching fs/net/tls/dns in the
// client bundle via the ehr-formatters → visit-ready-view import chain.
// ============================================================================

import type { TranscribeVisitStatus } from '@prisma/client';
import { EMPTY_SECTION_PLACEHOLDER } from './soap-format';
import type { NoteTemplateHeaderField } from '@/worker/note-templates/system-default-template';

// ----------------------------------------------------------------------------
// Wire types — duplicated from worker/layers/* so this module can be
// imported from both the web app AND test files without pulling in the
// worker-only modules.
// ----------------------------------------------------------------------------

export interface IcdCode {
  code: string;
  description: string;
  evidence_quote: string;
  confidence: number;
}

export interface CptEm {
  /** The E/M code to PRINT. The export loader projects the authoritative
   *  displayed level onto this field (signed → frozen signedCode; otherwise
   *  override ?? raw) so every artifact prints what the doctor reviewed —
   *  NOT the raw L7b suggestion. See visit-export-server.loadVisitExportData. */
  code: string;
  description: string;
  reasoning: {
    problems: { description: string; status: string }[];
    data: string;
    risk: string;
  };
  evidence_quote: string;
  /** Doctor override set via the override route (cptCodes.em.override). */
  override?: { code: string; reason?: string; overriddenAt?: string };
  /** The displayed E/M level FROZEN at sign time (#315 obs#2 parity fix).
   *  Present on visits signed after 2026-06-13; the authoritative billing
   *  code for a signed visit. */
  signedCode?: string;
}

/** The AUTHORITATIVE E/M code to show/print — the level the doctor reviewed,
 *  never the raw L7b suggestion. Pure + client-safe, so EVERY surface (the
 *  server export loader, the on-screen Codes tab, the "Copy codes" clipboard)
 *  projects identically: signed → frozen signedCode, else the doctor override,
 *  else the raw code. (#315 obs#2 — the divergence is impossible by
 *  construction only if all surfaces call THIS.) */
export function projectDisplayedEmCode(
  em: CptEm | null | undefined,
  isSigned: boolean
): string | null {
  if (!em) return null;
  return isSigned
    ? em.signedCode ?? em.override?.code ?? em.code
    : em.override?.code ?? em.code;
}

/** `em` with its `code` projected to the authoritative displayed level. */
export function projectEmForDisplay(
  em: CptEm | null | undefined,
  isSigned: boolean
): CptEm | null {
  if (!em) return null;
  const code = projectDisplayedEmCode(em, isSigned);
  return code ? { ...em, code } : em;
}

export interface CptProcedure {
  code: string;
  description: string;
  evidence_quote: string;
}

export interface CptModifier {
  code: string;
  rationale: string;
}

export interface Prescription {
  drug: string;
  strength?: string | null;
  form?: string | null;
  sig?: string | null;
  quantity?: string | null;
  refills?: string | null;
  action:
    | 'new'
    | 'continue'
    | 'increase'
    | 'decrease'
    | 'discontinue'
    | 'unclear';
  evidence_quote: string;
}

export interface RxWarning {
  severity: 'critical' | 'major' | 'minor';
  rx_drug: string;
  message: string;
  evidence_quote?: string | null;
}

export interface Referral {
  to: string;
  reason: string;
  relevant_history: string;
  urgency: 'routine' | 'urgent' | 'stat';
  evidence_quote: string;
}

/**
 * The complete bundle every downstream generator consumes. Nulls are
 * allowed and expected — each generator decides how to handle missing
 * sections (skip vs "not documented").
 */
export interface VisitExportData {
  visitId: string;
  patientName: string | null;
  specialty: string;
  chiefComplaint: string | null;
  status: TranscribeVisitStatus;
  createdAt: Date;
  signedAt: Date | null;

  clinicianName: string | null;
  clinicianEmail: string;

  /** The displayable SOAP: signedSoap when frozen, soapFinal otherwise. */
  soapText: string;

  icdCodes: IcdCode[];
  em: CptEm | null;
  procedures: CptProcedure[];
  modifiers: CptModifier[];
  prescriptions: Prescription[];
  rxWarnings: RxWarning[];
  referrals: Referral[];
  patientSummary: string | null;

  /** The doctor's parsed form header fields (feat/template-header-fields),
   *  deterministically filled for THIS visit (label + value; value '' = blank).
   *  Empty for templates without a header block. Rendered at the top of the
   *  styled export, in order. */
  headerFields: RenderedHeaderField[];
  /** "Form-only export": when true, suppress the appended Diagnoses /
   *  Procedures / Medications / Referrals / Patient Summary blocks. */
  formOnly: boolean;
}

/** A header field resolved for one visit: the doctor's label + the filled value
 *  ('' when blank / not dictated). Presentation-only. */
export interface RenderedHeaderField {
  label: string;
  value: string;
}

// A surgeon must be EXPLICITLY attributed with an OPERATING role — an operating
// surgeon / performed by / proceduralist attribution, or a labeled "SURGEON:"
// field. A BARE mid-sentence "surgeon" is intentionally NOT matched: it grabs a
// referring/consulting surgeon or even the PATIENT's own occupation ("the
// patient is a surgeon, Dr. Jane Patient") — wrong-physician / patient-name
// contamination of a signed export. The negative lookbehind additionally rejects
// "referring/consulting/… surgeon:". Case-INSENSITIVE for the attribution…
const SURGEON_CONTEXT_RE =
  /(?<!\b(?:referring|consulting|usual|prior|previous)\s{1,3})(?:\b(?:operating\s+surgeon|proceduralist|performing\s+(?:surgeon|physician|provider))\b(?:\s+(?:was|is))?\s*[:,]?|\bperformed(?:\s+\w+){0,2}\s+by\b|\bsurgeon\s*:)\s*/i;
// …but the NAME is matched CASE-SENSITIVELY (real uppercase first letters) so a
// following lowercase word ("performed") is never swallowed. The surname char
// class excludes '.' (kept only in the "Dr." title) so a sentence period is a
// hard stop — "Dr. Shabatian. The scope…" yields "Dr. Shabatian", not
// "Dr. Shabatian. The". Hyphenated/compound surnames (Reyes-Lopez) still match.
const SURGEON_NAME_RE = /^(Dr\.?\s+[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+){0,2})/;

/** Extract an explicitly-attributed surgeon name ("Dr. X") from the dictated
 *  note. Returns null when not clearly stated (→ blank field). Conservative +
 *  deterministic; NEVER AI, never the account holder. */
export function extractSurgeonFromNote(soapText: string): string | null {
  const ctx = soapText.match(SURGEON_CONTEXT_RE);
  if (!ctx || ctx.index === undefined) return null;
  const name = soapText.slice(ctx.index + ctx[0].length).match(SURGEON_NAME_RE);
  if (!name) return null;
  // Strip a trailing sentence period/comma; internal "Dr." period is preserved.
  return name[1].replace(/[.,;]+$/, '').replace(/\s+/g, ' ').trim();
}

/** A header field LABEL is a short generic form label ("PATIENT NAME", "DATE OF
 *  SURGERY"). It must NOT look like it carries data. This is the render-seam
 *  DEFENSE-IN-DEPTH backstop: the primary guard is the ^…$-anchored canonical-key
 *  match at every WRITE seam, but the structured-PHI detector is blind to a bare
 *  name (no digits), so if a write-seam guard were ever loosened a name could sit
 *  in a stored label. Re-validating here means a malformed/tampered stored row
 *  can never render a patient value. Rejects digits, over-long, or many-word
 *  labels. Pure. */
export function isSafeHeaderLabel(label: string): boolean {
  const t = label.trim();
  return t.length > 0 && t.length <= 40 && !/\d/.test(t) && t.split(/\s+/).length <= 5;
}

/** Shape-guard header fields read from a template's styleProfile JSONB into the
 *  typed array (drops malformed entries + labels that fail the safety backstop).
 *  Pure. */
export function coerceHeaderFields(raw: unknown): NoteTemplateHeaderField[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((f) => {
    if (!f || typeof f !== 'object') return [];
    const o = f as Record<string, unknown>;
    if (typeof o.key !== 'string' || typeof o.label !== 'string' || typeof o.order !== 'number') {
      return [];
    }
    if (!isSafeHeaderLabel(o.label)) return [];
    return [{ key: o.key, label: o.label, order: o.order }];
  });
}

/**
 * Deterministically fill a template's header fields for the styled export.
 * Same rule class as context defaults + the native DATE OF PROCEDURE fill:
 *   - patient_name    → the visit's patient name (visit record)
 *   - date_of_surgery → the visit date (signed/created — visit record)
 *   - surgeon         → an explicit surgeon attribution in the note, else blank
 *   - patient_dob / patient_id / anything else → blank unless dictated (never
 *     inferred — DOB/ID are never guessed)
 * NEVER AI. Preserves template order. A blank value ('') is rendered as an
 * honest blank by the generators.
 */
export function resolveHeaderFields(
  headerFields: NoteTemplateHeaderField[] | null | undefined,
  ctx: { patientName: string | null; visitDate: Date; soapText: string }
): RenderedHeaderField[] {
  if (!headerFields || headerFields.length === 0) return [];
  const surgeon = extractSurgeonFromNote(ctx.soapText);
  return [...headerFields]
    .sort((a, b) => a.order - b.order)
    .map((f) => {
      let value = '';
      switch (f.key) {
        case 'patient_name':
          value = (ctx.patientName ?? '').trim();
          break;
        case 'date_of_surgery':
          value = formatVisitDate(ctx.visitDate);
          break;
        case 'surgeon':
          value = surgeon ?? '';
          break;
        // patient_dob, patient_id, and any unmapped field: blank unless dictated.
        default:
          value = '';
      }
      return { label: f.label, value };
    });
}

/** Human-readable short date used in filenames + PDF headers. */
export function formatVisitDate(d: Date): string {
  // ISO-like YYYY-MM-DD is filename-safe + sortable. The PDF header
  // uses a prettier variant; see pdf-generator.ts.
  return d.toISOString().slice(0, 10);
}

/** Filename-safe version of the patient name (or "anonymous"). */
export function filenameSlug(name: string | null | undefined): string {
  const base = (name ?? 'anonymous').trim().toLowerCase();
  return base.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40) ||
    'visit';
}

/** Known administration ROUTES (not form descriptors like "extended release").
 *  A form whose leading word is one of these AND which the drug name already
 *  carries is de-duplicated; restricting to routes keeps multi-word form
 *  descriptors intact. */
const ROUTE_WORDS = new Set([
  'sublingual', 'oral', 'buccal', 'rectal', 'topical', 'transdermal',
  'ophthalmic', 'otic', 'nasal', 'intranasal', 'inhaled', 'inhalation',
  'vaginal', 'subcutaneous', 'intramuscular', 'intravenous', 'oromucosal',
]);

/** If `form` begins with a route word that already appears (as a whole word) in
 *  `drug`, strip that leading word (and its separator). Returns the trimmed
 *  form otherwise. Pure; presentation-only. */
export function dedupeLeadingRoute(drug: string, form: string): string {
  const trimmed = form.trim();
  const m = trimmed.match(/^(\S+?)([\s,;:]+)(.*)$/);
  const firstRaw = m ? m[1] : trimmed;
  const first = firstRaw.replace(/[.,;:]+$/, '').toLowerCase();
  if (
    ROUTE_WORDS.has(first) &&
    new RegExp(`\\b${first.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i').test(drug)
  ) {
    return m ? m[3].trim() : '';
  }
  return trimmed;
}

/** Format a prescription into a single Epic-compatible line. Shared
 *  between clipboard formatters + the PDF/DOCX generators so their Rx
 *  sections stay aligned if one of us changes format conventions later. */
export function prescriptionOneLine(rx: Prescription): string {
  const parts: string[] = [rx.drug];
  if (rx.strength) parts.push(rx.strength);
  if (rx.form) {
    // Route-word de-dup (2026-07-23): the drafter sometimes appends a route to
    // the drug name AND repeats it as the form's leading word — e.g. drug
    // "Cyanocobalamin (Vitamin B12) sublingual" + form "sublingual tablet"
    // renders "…sublingual sublingual tablet". Drop the form's leading word only
    // when it is a known ROUTE word (not a form descriptor like "extended
    // release") that already appears in the drug name — provably redundant, and
    // the whitelist avoids garbling multi-word form descriptors. Trims leading
    // whitespace and ignores trailing punctuation on the leading word.
    const form = dedupeLeadingRoute(rx.drug, rx.form);
    if (form) parts.push(form);
  }
  if (rx.sig) parts.push(`– ${rx.sig}`);
  const tail: string[] = [];
  if (rx.quantity) tail.push(`#${rx.quantity}`);
  if (rx.refills) tail.push(`Refills ${rx.refills}`);
  if (tail.length) parts.push(`(${tail.join(', ')})`);
  // Append an uppercase action tag only when it carries information
  // beyond "new Rx" — NEW is implied by context on a fresh note.
  if (rx.action !== 'new') {
    parts.push(`[${rx.action.toUpperCase()}]`);
  }
  return parts.join(' ');
}

// ----------------------------------------------------------------------------
// Export cleanliness (Stage 1) — one presentation-only convention for "nothing
// documented", applied to the note markdown BEFORE any renderer (docx / PDF /
// clipboard / email) walks it, so a signed export reads as a physician-authored
// clinical document: no review-screen machinery, no bracketed markers, no
// stray markdown. It is PURELY presentational — it never changes stored data
// and NEVER generates clinical content the doctor didn't dictate or adopt.
// ----------------------------------------------------------------------------

/** The word used in a prose section that has no documented content. */
export const EXPORT_EMPTY_SECTION_TEXT = 'Not documented.';
/** The cell token used in an export table for an undocumented measurement. */
export const EXPORT_EMPTY_CELL = '—';

/**
 * Clean a note's markdown for export. Two transforms, both presentation-only:
 *   1. every set-aside/empty PROSE section renders as its header + "Not
 *      documented." — the "_[All AI-drafted…adopt before signing.]_" review
 *      placeholder is dropped, and any section left with no content gets the
 *      one consistent "Not documented." line (never a bare header);
 *   2. every "[not documented]" table cell becomes an em dash "—".
 *
 * It NEVER touches a section the doctor adopted (its text renders exactly as
 * today), NEVER invents content, and NEVER edits stored columns — the loader
 * runs it only on the copy handed to the exporters. A section that carries a
 * table (its body has pipe rows) keeps its structure; only its empty cells
 * become "—". Idempotent.
 */
export function sanitizeExportedSoap(soap: string): string {
  if (!soap || !soap.trim()) return soap;
  const SECTION_RE = /^\s*#{1,6}\s/;
  // Pass 1: drop the set-aside placeholder line; normalise empty table cells.
  const lines = soap
    .split('\n')
    .filter((l) => l.trim() !== EMPTY_SECTION_PLACEHOLDER)
    .map((l) => l.replace(/\[not documented\]/gi, EXPORT_EMPTY_CELL));
  // Pass 2: any section whose body has no remaining content → "Not documented."
  const out: string[] = [];
  for (let i = 0; i < lines.length; i++) {
    out.push(lines[i]);
    if (!SECTION_RE.test(lines[i])) continue;
    let j = i + 1;
    let hasContent = false;
    while (j < lines.length && !SECTION_RE.test(lines[j])) {
      if (lines[j].trim()) hasContent = true;
      j++;
    }
    if (!hasContent) out.push(EXPORT_EMPTY_SECTION_TEXT);
  }
  return out.join('\n');
}
