// ============================================================================
// Server-only visit-export loader (T-M7)
// ----------------------------------------------------------------------------
// Split from visit-export.ts because that module is imported (transitively)
// from client components via ehr-formatters.ts → visit-ready-view.tsx.
// Any `import prisma from '@meddoc/db'` reaches into @prisma/adapter-pg,
// which pulls Node built-ins (fs/net/tls/dns) and breaks the client bundle.
//
// Keeping the Prisma-touching function here means the pure helpers and
// types can stay in visit-export.ts and be safely client-imported.
// ============================================================================

import prisma from '@meddoc/db';
import { visitByIdScope, type PracticeId } from '@/lib/practice-scope';
import type { TranscribeVisitStatus } from '@prisma/client';
import { findSpecialty } from '@meddoc/shared/specialties';
import { emAppliesToVisit } from './note-shape';
import {
  projectEmForDisplay,
  sanitizeExportedSoap,
  resolveHeaderFields,
  coerceHeaderFields,
} from './visit-export';
import { renumberFormSections, coerceFormSignature } from './form-only';
import type {
  CptEm,
  CptModifier,
  CptProcedure,
  IcdCode,
  Prescription,
  Referral,
  RxWarning,
  VisitExportData,
} from './visit-export';

/**
 * Auth + load. Returns null for "not found / not yours" so the route
 * can return 404 without distinguishing the two (prevents ID
 * enumeration).
 */
export async function loadVisitExportData(
  visitId: string,
  // T5 §4.1b — a READ, so it is scoped by PRACTICE. Renamed from `userId`
  // deliberately: both are strings, and a caller passing the old one would
  // have compiled and silently returned nothing for a colleague's chart.
  practiceId: PracticeId
): Promise<VisitExportData | null> {
  const visit = await prisma.transcribeVisit.findFirst({
    where: visitByIdScope(visitId, practiceId),
    select: {
      id: true,
      userId: true,
      patientName: true,
      specialty: true,
      chiefComplaint: true,
      status: true,
      createdAt: true,
      signedAt: true,
      soapFinal: true,
      signedSoap: true,
      rawTextInput: true,
      icdCodes: true,
      cptCodes: true,
      rxDrafts: true,
      referrals: true,
      patientSummary: true,
      // feat/template-header-fields: the bound template's export-only config
      // (header fields + form-only pref) rides in its styleProfile JSONB. One
      // round-trip via the relation; only these two export fields are read,
      // note-gen never sees them.
      // F12 / ruling #123 adds `sections`: the note-SHAPE axis of E/M
      // applicability is read from the template's own section labels, because
      // `encounterType` is NULL on every production row and is really the
      // specialty slot. Still one round-trip; note-gen never sees these.
      noteTemplate: { select: { styleProfile: true, name: true, sections: true } },
      user: { select: { name: true, email: true } },
    },
  });
  if (!visit) return null;

  const styleProfile =
    (visit.noteTemplate?.styleProfile as {
      headerFields?: unknown;
      formOnlyExport?: unknown;
      formSignature?: unknown;
    } | null) ?? null;
  const parsedHeaderFields = coerceHeaderFields(styleProfile?.headerFields);
  const formOnly = styleProfile?.formOnlyExport === true;
  const formTitle = visit.noteTemplate?.name ?? null;
  const formSignature = coerceFormSignature(styleProfile?.formSignature);

  const rawSoap =
    visit.status === 'SIGNED'
      ? visit.signedSoap ?? visit.soapFinal ?? ''
      : visit.soapFinal ?? '';
  // DEDUPE (prod bug): the note body may carry a "## PATIENT SUMMARY" section
  // (from the template — often partial), and the visit ALSO has a dedicated,
  // complete `patientSummary` field the exporters render as their own "Patient
  // Summary" block. Rendering both yields a partial-above-complete duplicate.
  // When the complete field is present, strip the note's section so exactly one
  // (complete) summary is rendered; when it is absent, the note's section stays.
  // Presentation-only export cleanup (Stage 1): set-aside/empty prose sections
  // → "Not documented.", "[not documented]" table cells → "—", review-lane
  // placeholder dropped. Applied ONLY to the exported copy — stored columns and
  // the on-screen review lane are untouched. Runs after the patient-summary
  // strip so the dedupe still sees the note's own heading.
  const sanitizedSoap = sanitizeExportedSoap(
    visit.patientSummary && visit.patientSummary.trim()
      ? stripNotePatientSummarySection(rawSoap)
      : rawSoap
  );
  // Form-only: renumber enumerable findings/recommendations PROSE into numbered
  // lists (matching the practice's form style). Toggle-OFF path is untouched.
  const soapText = formOnly ? renumberFormSections(sanitizedSoap) : sanitizedSoap;

  // All four of these are Json? columns — treat each as its own shape
  // with a tolerant cast + safe-default. Downstream code can rely on
  // arrays being arrays.
  const icdBlob = (visit.icdCodes as { codes?: IcdCode[] } | null) ?? null;
  const cptBlob =
    (visit.cptCodes as {
      em?: CptEm | null;
      procedures?: CptProcedure[];
      modifiers?: CptModifier[];
    } | null) ?? null;
  const rxBlob =
    (visit.rxDrafts as {
      prescriptions?: Prescription[];
      warnings?: RxWarning[];
    } | null) ?? null;
  const refBlob =
    (visit.referrals as { referrals?: Referral[] } | null) ?? null;

  // E/M PARITY (#315 obs#2): project the AUTHORITATIVE displayed level onto
  // em.code so every artifact (PDF, DOCX, all EHR clipboard formats) prints
  // what the doctor reviewed — never the raw L7b suggestion. The SAME helper
  // the client Codes tab + "Copy codes" use, so all surfaces agree.
  // AN IMAGING REPORT EXPORTS NO OFFICE E/M LEVEL, whatever the row carries —
  // and since F12 / ruling #123, NEITHER DOES AN OPERATIVE OR PROCEDURE NOTE.
  //
  // ⚠️ THIS IS THE SINGLE SEAM FOR EVERY EXPORT SURFACE. DOCX, PDF, all the EHR
  // clipboard formats, email, patient export, settings export-data, the sign
  // route and the preview action all reach it through `loadVisitExportData`, so
  // the export half of #123 is ONE line at the root rather than a per-route
  // sweep — which is R3.4's recorded lesson: a per-caller list is kept complete
  // by hand, and hand-kept lists are wrong eventually.
  //
  // `visit.specialty` is the raw column, which IS an id — the label conversion
  // happens below at `specialty:`, and feeding a label to the predicate is the
  // exact mistake that caused this whole class (see emAppliesToSpecialty).
  const emForExport = projectEmForDisplay(
    cptBlob?.em ?? null,
    visit.status === 'SIGNED',
    emAppliesToVisit({
      specialtyId: visit.specialty,
      templateSections: visit.noteTemplate?.sections ?? null,
      // `rawSoap`, deliberately — the STORED record, before the export-only
      // cleanups. `stripNotePatientSummarySection` and `sanitizeExportedSoap`
      // both rewrite the body for presentation, and classifying a note by a
      // string that exists only inside one export path would make the verdict
      // depend on which surface asked.
      noteText: rawSoap,
    }),
  );

  // Deterministically fill the header fields for THIS visit (never AI): NAME +
  // DATE from the visit record, SURGEON from the dictated note, DOB/ID blank.
  const headerFields = resolveHeaderFields(parsedHeaderFields, {
    patientName: visit.patientName,
    // Ruling #115 — DATE OF SURGERY names when the encounter happened. Reading
    // `signedAt` here printed the SIGNING date onto a customer's operative form.
    visitDate: visit.createdAt,
    soapText,
    dictationText: visit.rawTextInput,
  });

  return {
    visitId: visit.id,
    patientName: visit.patientName,
    // PDF/DOCX/EHR formatters render `data.specialty` directly into
    // document headers — we want the human label ("Cardiology"), not
    // the canonical id ("cardiology"). findSpecialty also resolves
    // legacy display-name rows so old visits export with the right
    // label instead of "Unspecified".
    specialty: findSpecialty(visit.specialty).label,
    chiefComplaint: visit.chiefComplaint,
    status: visit.status as TranscribeVisitStatus,
    createdAt: visit.createdAt,
    signedAt: visit.signedAt,
    clinicianName: visit.user.name ?? null,
    clinicianEmail: visit.user.email,
    soapText,
    icdCodes: icdBlob?.codes ?? [],
    em: emForExport,
    procedures: cptBlob?.procedures ?? [],
    modifiers: cptBlob?.modifiers ?? [],
    prescriptions: rxBlob?.prescriptions ?? [],
    rxWarnings: rxBlob?.warnings ?? [],
    referrals: refBlob?.referrals ?? [],
    patientSummary: visit.patientSummary,
    headerFields,
    formOnly,
    formTitle,
    formSignature,
  };
}

/**
 * Remove a note body's "## PATIENT SUMMARY" section (heading + body up to the
 * next "## " heading or end of note) so it is not rendered alongside the visit's
 * dedicated complete `patientSummary` field. Pure; case-insensitive on the
 * heading text only. When the note carries no such section the SECTION is left
 * intact; trailing whitespace is still normalised (trimEnd + collapse blank-line
 * runs), which is inert for the export renderer.
 */
export function stripNotePatientSummarySection(soap: string): string {
  return soap
    .replace(/(^|\n)[ \t]*##[ \t]+patient summary\b[\s\S]*?(?=\n[ \t]*##[ \t]|$)/i, '$1')
    .replace(/\n{3,}/g, '\n\n')
    .trimEnd();
}
