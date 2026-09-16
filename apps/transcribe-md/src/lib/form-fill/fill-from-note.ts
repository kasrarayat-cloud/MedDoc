// ============================================================================
// ONE-PIPELINE (ruling #326, Slice B) — the DETECTED-form value source. Given a
// visit note + the mapped detected fields, produce the { fieldId → text } map the
// fill engine draws into the detected boxes. Deterministic; NO AI, NO fabricated
// DOCX IR.
// ----------------------------------------------------------------------------
// ⚠️ WHY NOT `resolveTemplateFields`. The obvious plan was to synthesise a
// zod-valid `TemplateField` + `SemanticMapping` per detected box and reuse the
// twin resolver. `TemplateFieldSchema` REQUIRES a DOCX `rendererBinding` (bookmark
// / alias / tag into a Word part), `criticality`, and table structure — none of
// which a detected PDF box has. Synthesising them means fabricating meaningless
// Word bindings, and any resolver arm that touches one is undefined behaviour on a
// detected form. So the value source is the one the pdf-native NON-twin export
// ALREADY uses and that is precedented + deterministic:
//   • body sections  → `buildPdfFillTexts` splits the note by its `## <label>`
//                      headings and fills the box whose label matches (note-heading
//                      split — pdf-native/note-to-texts.ts).
//   • header fields  → `resolveHeaderFields` fills the record-derived metadata
//                      (patient_name / date_of_surgery / surgeon) deterministically
//                      by canonical key; everything else is blank-unless-dictated,
//                      exactly as the DOCX twin attests `visit_metadata`/`manual`
//                      fields blank (#247 / #319). A blank DOB box is NOT a fill
//                      failure — it is a policy blank.
//
// The certify proof (certify-detected-form) and the per-visit export
// (export-detected) BOTH call this one function, so a real export takes exactly
// the path certification proved binds — the synthetic-test.ts doctrine, applied to
// the detected form.
// ============================================================================
import { buildPdfFillTexts } from '@/lib/pdf-native/note-to-texts';
import { resolveHeaderFields } from '@/lib/visit-export';
import type { NoteTemplateHeaderField } from '@/worker/note-templates/system-default-template';

import type { StoredDetectedField } from './detected-form-store';

/** The canonical header key a record-derived metadata concept fills through, or
 *  null when the concept is a body section (routed to the note-heading split).
 *  Mirrors VISIT_METADATA_LABEL_CONCEPTS → resolveHeaderFields' switch. */
export function headerKeyForConcept(concept: string | null): string | null {
  switch (concept) {
    case 'visit_metadata.patient_name':
      return 'patient_name';
    case 'visit_metadata.date_of_service':
      return 'date_of_surgery';
    case 'procedure.surgeon':
      return 'surgeon';
    case 'visit_metadata.date_of_birth':
      return 'patient_dob';
    case 'visit_metadata.patient_id':
      return 'patient_id';
    case 'visit_metadata.patient_age':
      return 'patient_age';
    case 'visit_metadata.dictated_at':
      return 'dictated_at';
    case 'visit_metadata.transcribed_at':
      return 'transcribed_at';
    default:
      return null;
  }
}

/** The header keys `resolveHeaderFields` fills DETERMINISTICALLY today. A metadata
 *  field whose key is NOT here is a POLICY BLANK (blank-unless-dictated) — it must
 *  not be counted as a fill failure at certify. `resolveHeaderFields` is the single
 *  authority on this set; keep it in sync with its `switch`. */
export const DETERMINISTICALLY_FILLED_HEADER_KEYS: ReadonlySet<string> = new Set([
  'patient_name',
  'date_of_surgery',
  'surgeon',
]);

export interface NoteFillContext {
  patientName: string | null;
  visitDate: Date;
  /** The visit note (signedSoap ?? soapFinal), already export-sanitized. Also the
   *  surgeon source for `resolveHeaderFields`. */
  noteText: string;
  dictationText?: string | null;
}

export interface FillFromNoteResult {
  /** fieldId → the value text to draw (only non-empty values appear). */
  values: Map<string, string>;
  /** Note sections with real content that match NO detected field — carried by
   *  the caller so real clinical content is never silently dropped (the
   *  pdf-native addendum rule; a continuation page is a Slice-B follow-up). */
  addenda: Array<{ label: string; text: string }>;
}

/**
 * Build the fieldId → value map for a detected form over a note. PURE apart from
 * the two shared helpers it composes.
 *
 * Body fields fill from the note-heading split (matched on the box's own label);
 * header fields fill from `resolveHeaderFields` by canonical key. A field with no
 * value simply does not appear — its box stays blank.
 */
export function fillFromNote(
  fields: ReadonlyArray<StoredDetectedField>,
  ctx: NoteFillContext,
): FillFromNoteResult {
  const bodyFields = fields.filter((f) => f.headerKey === null);
  const headerFields = fields.filter((f) => f.headerKey !== null);

  const values = new Map<string, string>();

  // ── BODY SECTIONS — the note-heading split, keyed by the field id. Pass NO
  // header fields so header resolution never collides on a shared canonical key.
  const { texts, addenda } = buildPdfFillTexts({
    noteText: ctx.noteText,
    sections: bodyFields.map((f) => ({ key: f.id, label: f.label })),
    headerFields: [],
    headerCtx: {
      patientName: ctx.patientName,
      visitDate: ctx.visitDate,
      soapText: ctx.noteText,
      dictationText: ctx.dictationText,
    },
  });
  for (const [key, text] of Object.entries(texts)) {
    if (text && text.trim()) values.set(key, text);
  }

  // ── HEADER FIELDS — resolve each by its OWN canonical key and assign back to
  // the field id. One field per call so two boxes sharing a key (a form with two
  // date lines) never overwrite each other via the shared-key text map.
  for (const f of headerFields) {
    const asHeader: NoteTemplateHeaderField = {
      key: f.headerKey as string,
      label: f.label,
      order: 1,
    };
    const rendered = resolveHeaderFields([asHeader], {
      patientName: ctx.patientName,
      visitDate: ctx.visitDate,
      soapText: ctx.noteText,
      dictationText: ctx.dictationText,
    });
    const value = rendered[0]?.value?.trim();
    if (value) values.set(f.id, value);
  }

  return { values, addenda };
}
