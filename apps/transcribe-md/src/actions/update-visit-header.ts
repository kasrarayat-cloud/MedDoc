'use server';

// ============================================================================
// Correcting the header of a note the doctor is reviewing.
// ----------------------------------------------------------------------------
// The document has a header — patient name, chief complaint — and until now the
// only way to change any of it after the pipeline ran was PATCH /api/visits/[id],
// which refuses anything past QUEUED. So a misspelled name on a READY visit had
// no fix at all: not in the UI, not in the chat, not in the API. The doctor's
// options were sign it wrong or delete the visit and start over.
//
// TWO THINGS THIS DELIBERATELY DOES NOT DO:
//   • It does not touch a SIGNED visit. A signed record is corrected by
//     addendum, never by editing the name on it.
//   • It does not desynchronise the patient from the visit. Renaming writes the
//     PATIENT RECORD and the visit's denormalised copy together, because a
//     misspelled name is misspelled everywhere and fixing one of the two is how
//     you get a chart that disagrees with itself.
//
// That second one has a blast radius, and the caller is required to say so: the
// rename shows up on that patient's other visits too. The chat's reply names it.
// ============================================================================

import prisma from '@meddoc/db';

import { requireSession } from '@/lib/auth';
import { visitByIdScope, visitScope } from '@/lib/practice-scope';
import { logAudit } from '@/lib/audit';
import { invalidateVisitFills } from '@/lib/docx-preview/fill-cache';

export type VisitHeaderField = 'patient_name' | 'chief_complaint';

export interface UpdateVisitHeaderResult {
  ok: boolean;
  /** Doctor-facing, PHI-free on the failure path. */
  error?: string;
  /** What it was, so the reply can say what changed. Present only on success. */
  before?: string;
  after?: string;
  /** True when the change also lands on the patient's other visits. */
  affectsOtherVisits?: boolean;
}

const MAX_LEN = 200;

export async function updateVisitHeaderAction(
  visitId: string,
  field: VisitHeaderField,
  rawValue: string,
): Promise<UpdateVisitHeaderResult> {
  const session = await requireSession();

  const value = rawValue.trim();
  if (!value) return { ok: false, error: 'That would leave the field empty.' };
  if (value.length > MAX_LEN) {
    return { ok: false, error: 'That value is too long for a header field.' };
  }

  // Ownership is a WHERE clause, never a check after the fact.
  const visit = await prisma.transcribeVisit.findFirst({
    where: {
      ...visitByIdScope(visitId, session.user.practiceId),
      // ACTION, not a read: the author conjunct stays until T6's role
      // gate decides who else may edit. Widening SEE never widens DO.
      userId: session.user.id,
      deletedAt: null,
      archivedAt: null,
    },
    select: {
      id: true,
      signedAt: true,
      patientId: true,
      patientName: true,
      chiefComplaint: true,
    },
  });
  if (!visit) return { ok: false, error: 'That visit is not available.' };

  // SIGNED IS FINAL. Same rule the whole app runs on.
  if (visit.signedAt) {
    return {
      ok: false,
      error: 'This visit is signed, so its header cannot be edited. A signed note is corrected by addendum.',
    };
  }

  if (field === 'chief_complaint') {
    const before = visit.chiefComplaint ?? '';
    if (before === value) return { ok: false, error: 'That is already what it says.' };
    await prisma.transcribeVisit.update({
      where: { id: visit.id },
      data: { chiefComplaint: value },
    });
    void logAudit({
      action: 'EDITED_NOTE',
      targetType: 'TranscribeVisit',
      targetId: visit.id,
      // Field NAME only. The value is the patient's chief complaint.
      metadata: { via: 'visit_header', field },
    });
    // The header is printed into the exported document, and the preview of it
    // is cached on (visit, soapVersion) — which this does not move.
    await invalidateVisitFills(visit.id);
    return { ok: true, before, after: value };
  }

  // ── patient_name ────────────────────────────────────────────────────────
  const before = visit.patientName ?? '';
  if (before === value) return { ok: false, error: 'That is already the name on this visit.' };

  let affectsOtherVisits = false;

  if (visit.patientId) {
    // Scope the patient write by the SAME ownership the visit was found under —
    // a patientId taken off a row this doctor owns is theirs, but updateMany
    // with an explicit practice filter is what makes that a rule rather than an
    // inference.
    const me = await prisma.user.findUnique({
      where: { id: session.user.id },
      select: { practiceId: true },
    });
    if (!me?.practiceId) return { ok: false, error: 'That visit is not available.' };

    const changed = await prisma.transcribeMdPatient.updateMany({
      where: { id: visit.patientId, practiceId: me.practiceId, deletedAt: null },
      data: { name: value },
    });
    if (changed.count === 0) {
      return { ok: false, error: 'That patient record is not available.' };
    }

    // EXACTLY the rows the rename will touch — same filter, counted first.
    //
    // This used to count every visit for the patient, including SIGNED and
    // archived ones that the updateMany deliberately skips. So a doctor whose
    // patient had one old signed note was told the rename had spread to other
    // visits when it had not, and the audit row recorded the same untruth.
    const otherIds = await prisma.transcribeVisit.findMany({
      where: {
        patientId: visit.patientId,
        // Its own predicate, not the parent read's scope inherited by habit.
        ...visitScope(session.user.practiceId),
        id: { not: visit.id },
        signedAt: null,
        deletedAt: null,
        archivedAt: null,
      },
      select: { id: true },
    });
    affectsOtherVisits = otherIds.length > 0;

    // Every UNSIGNED visit for this patient carries the denormalised copy, and
    // leaving them stale is how the chart starts disagreeing with itself.
    // SIGNED ones are deliberately excluded: their header is part of what was
    // signed, and rewriting it here would edit a finished record.
    await prisma.transcribeVisit.updateMany({
      where: {
        patientId: visit.patientId,
        signedAt: null,
        deletedAt: null,
        archivedAt: null,
      },
      data: { patientName: value },
    });

    // EACH of those visits caches a RENDERING of the document, and the name is
    // printed in its header. Invalidating only the visit in front of the doctor
    // would leave every other one serving a preview of the old name for the
    // rest of its TTL — the same staleness class the E/M override had, one
    // table over.
    await Promise.all(otherIds.map((o: { id: string }) => invalidateVisitFills(o.id)));

    // A ROW ON EACH NOTE THAT CHANGED, not just on the one being looked at.
    //
    // In a shared practice these can be a COLLEAGUE'S unsigned notes: the
    // patient record is practice-level, so keeping their denormalised header in
    // step is right, but a doctor opening their own note tomorrow and finding a
    // different name on it must be able to see why. A count on the patient
    // record does not appear in the trail of the note it happened to.
    await Promise.all(
      otherIds.map((o: { id: string }) =>
        logAudit({
          action: 'EDITED_NOTE',
          targetType: 'TranscribeVisit',
          targetId: o.id,
          // Field name and cause only — never the name itself.
          metadata: { via: 'patient_rename', field: 'patient_name', fromVisit: visit.id },
        }),
      ),
    );

    void logAudit({
      action: 'TM_PATIENT_UPDATED',
      targetType: 'TranscribeMdPatient',
      targetId: visit.patientId,
      // COUNT, not ids — but a count, because a rename reaching notes the
      // doctor is not looking at should be visible in the trail of the patient
      // record it happened to.
      metadata: {
        via: 'visit_header',
        field: 'name',
        fromVisit: visit.id,
        otherUnsignedVisitsRenamed: otherIds.length,
      },
    });
  } else {
    // No linked patient record — the visit's own denormalised name is all there
    // is, so it is the whole of the correction.
    await prisma.transcribeVisit.update({
      where: { id: visit.id },
      data: { patientName: value },
    });
  }

  void logAudit({
    action: 'EDITED_NOTE',
    targetType: 'TranscribeVisit',
    targetId: visit.id,
    metadata: { via: 'visit_header', field, affectsOtherVisits },
  });

  await invalidateVisitFills(visit.id);
  return { ok: true, before, after: value, affectsOtherVisits };
}
