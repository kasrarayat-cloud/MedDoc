'use server';

import { revalidatePath } from 'next/cache';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { requireSession } from '@/lib/auth';
import { logAudit } from '@/lib/audit';

const SaveSoapSchema = z.object({
  visitId: z.string().min(1),
  text: z.string().max(50_000),
  expectedVersion: z.number().int().nonnegative().optional(),
});

export interface SaveSoapResult {
  ok: boolean;
  error?: string;
  /**
   * Round 3 PR-E (A09-P0-003) — populated when error === 'conflict'.
   * Lets the client surface a "another edit happened — reload to see"
   * UX without a second round trip.
   */
  conflict?: {
    currentVersion: number;
    currentText: string;
  };
  /** New version after a successful write. Client stores it for the
   *  next save's expectedVersion. */
  newVersion?: number;
}

/** Persists the user's edits to soapFinal. Signed visits are locked —
 *  the action rejects rather than silently dropping the write.
 *
 *  Round 3 PR-E (A09-P0-003) — optimistic concurrency. If
 *  `expectedVersion` is provided (preferred), the write is gated by
 *  `WHERE soapVersion = expectedVersion`; mismatch returns
 *  `error: 'conflict'` with current state. If omitted (legacy
 *  callers during deploy window), falls back to last-write-wins.
 *
 *  FIND-P1-002 (comprehensive-audit 2026-05-14, RESOLVED-WITH-DOCS):
 *  this action intentionally does NOT write an `audit_logs` row per
 *  save. The audit doc's options were (A) emit `EDITED_NOTE` on
 *  every save — 5-20 rows per editing session — or (B) introduce
 *  a debounced `SOAP_DRAFT_SAVED` enum value. Both inflate
 *  `audit_logs` with intermediate draft churn for coverage we
 *  already get elsewhere:
 *
 *    - **Legal audit event**: `VISIT_SIGNED` fires from the sign
 *      route at `app/api/visits/[id]/sign/route.ts` — the sole
 *      READY→SIGNED path. Closed by PR #251 / FIND-P1-001.
 *
 *    - **Per-save evidence**: `soapVersion` increments here on
 *      every successful update (counter only — `soapFinal` itself
 *      holds the current text; prior textual states are not
 *      preserved). Operators can see "this visit had N draft
 *      saves before signing" but not the intermediate content.
 *
 *    - **Cumulative edit forensics**: `DoctorEditPattern` (table
 *      `doctor_edit_patterns`) captures one row per signed visit
 *      via `captureEditPattern(...)` in the sign route — the
 *      cumulative `originalSoap` (L6's AI output) → `editedSoap`
 *      (what the doctor signed) diff plus a char-level Levenshtein
 *      distance. This is the ML/quality surface, not a per-save
 *      capture.
 *
 *  The `audit_logs` table contract targets discrete legal events
 *  (sign, export, delete, view). Intermediate draft saves are
 *  operational state — the legal event is the sign transition,
 *  fully wired by PR #251.
 *
 *  If future regulatory guidance (or a multi-doctor scale need)
 *  requires per-save evidence with full content, options A or B
 *  remain viable. */
export async function saveSoapDraftAction(
  visitId: string,
  text: string,
  expectedVersion?: number
): Promise<SaveSoapResult> {
  const session = await requireSession();
  const parsed = SaveSoapSchema.safeParse({ visitId, text, expectedVersion });
  if (!parsed.success) {
    return { ok: false, error: 'Invalid input.' };
  }

  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      id: true,
      userId: true,
      status: true,
      deletedAt: true,
      archivedAt: true,
    },
  });
  if (!visit || visit.userId !== session.user.id) {
    return { ok: false, error: 'Visit not found.' };
  }
  // T-M17.3: reject writes on trashed / archived visits. The UI
  // already hides these from the default dashboard but a stale tab
  // could still fire this action.
  if (visit.deletedAt !== null || visit.archivedAt !== null) {
    return { ok: false, error: 'Visit is no longer active. Restore it first.' };
  }
  if (visit.status === TranscribeVisitStatus.SIGNED) {
    return { ok: false, error: 'Signed notes cannot be edited.' };
  }
  if (visit.status !== TranscribeVisitStatus.READY) {
    return { ok: false, error: 'Note is still processing.' };
  }

  // Round 3 PR-E (A09-P0-003) — optimistic-concurrency path.
  // updateMany with a WHERE clause on soapVersion is atomic in
  // Postgres: only one of two concurrent saves with the same
  // expectedVersion succeeds; the other returns count=0.
  if (parsed.data.expectedVersion !== undefined) {
    const result = await prisma.transcribeVisit.updateMany({
      where: { id: visitId, soapVersion: parsed.data.expectedVersion },
      data: {
        soapFinal: parsed.data.text,
        // THE NOTE CHANGED. Every editing surface funnels here — the inline
        // editor, tap-to-edit on the document, and the chat's section edit —
        // so this one line closes the gap for all of them at once: an edit
        // used to change the note without the E/M level ever being revisited.
        emStale: true,
        soapVersion: { increment: 1 },
      },
    });
    if (result.count === 0) {
      // Conflict: another save landed first. Surface current version
      // + text so the client can show a "reload to see latest" prompt.
      const current = await prisma.transcribeVisit.findUnique({
        where: { id: visitId },
        select: { soapVersion: true, soapFinal: true },
      });
      return {
        ok: false,
        error: 'conflict',
        conflict: {
          currentVersion: current?.soapVersion ?? -1,
          currentText: current?.soapFinal ?? '',
        },
      };
    }
    revalidatePath(`/visits/${visitId}`);
    return { ok: true, newVersion: parsed.data.expectedVersion + 1 };
  }

  // Legacy fallback (no expectedVersion supplied) — last-write-wins.
  // Still bumps soapVersion so a subsequent expectedVersion-aware
  // call sees the right value.
  const updated = await prisma.transcribeVisit.update({
    where: { id: visitId },
    data: {
      soapFinal: parsed.data.text,
      emStale: true,
      soapVersion: { increment: 1 },
    },
    select: { soapVersion: true },
  });

  revalidatePath(`/visits/${visitId}`);
  return { ok: true, newVersion: updated.soapVersion };
}

// NOTE: the legacy `signVisitAction` server action was removed in
// fix/rx-override-gate-correlation. It was the pre-T-M7 sign path, orphaned
// (no client/route/job referenced it) yet still registered as a server action
// — and, critically, it flipped READY→SIGNED with NO critical-Rx-warning
// override gate. The unified POST /api/visits/[id]/sign route is now the SOLE
// path that transitions a visit to SIGNED, and it enforces the gate.

const SpeakerRoleKeys = z.enum(['doctor', 'patient', 'family', 'other', 'unknown']);

const ReassignSpeakerSchema = z.object({
  visitId: z.string().min(1),
  speakerId: z.string().min(1),
  role: SpeakerRoleKeys,
});

/** Manual override for Layer 2 — doctor can correct a mis-assigned
 *  speaker role from the Transcript tab. Updates speakerMap in place,
 *  keeps reasoning + confidence intact (just flips role).
 *  Does NOT re-run the downstream layers; surfaces a toast to the
 *  client asking them to regenerate if they want the SOAP updated. */
export async function reassignSpeakerAction(
  visitId: string,
  speakerId: string,
  role: string
): Promise<SaveSoapResult> {
  const session = await requireSession();
  const parsed = ReassignSpeakerSchema.safeParse({ visitId, speakerId, role });
  if (!parsed.success) {
    return { ok: false, error: 'Invalid speaker role.' };
  }

  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      id: true,
      userId: true,
      status: true,
      speakerMap: true,
      deletedAt: true,
      archivedAt: true,
    },
  });
  if (!visit || visit.userId !== session.user.id) {
    return { ok: false, error: 'Visit not found.' };
  }
  if (visit.deletedAt !== null || visit.archivedAt !== null) {
    return { ok: false, error: 'Visit is no longer active. Restore it first.' };
  }
  if (visit.status === TranscribeVisitStatus.SIGNED) {
    return { ok: false, error: 'Signed notes cannot be edited.' };
  }

  // Prisma Json typing is loose; treat as record + write back.
  const map = (visit.speakerMap as Record<string, {
    role: string;
    confidence: number;
    reasoning: string;
  }> | null) ?? {};
  // Capture the previous role BEFORE mutating the map — feeds the
  // audit metadata below so forensics can see what changed without
  // reading DB row history.
  const previousRole = map[parsed.data.speakerId]?.role ?? null;
  map[parsed.data.speakerId] = {
    ...(map[parsed.data.speakerId] ?? { confidence: 1, reasoning: '' }),
    role: parsed.data.role,
    // Manual override → high confidence, marker reasoning so the
    // Pipeline tab can show "(manually reassigned)" later.
    confidence: 1,
    reasoning: `Manually reassigned by ${session.user.email}.`,
  };

  await prisma.transcribeVisit.update({
    where: { id: visitId },
    data: { speakerMap: map as unknown as object },
  });

  // FIND-P1-003 (2026-05-14) — HIPAA §164.312(b) audit row. The
  // speakerMap mutation affects the SOAP note's history-vs-plan
  // segmentation downstream; this row gives "who reassigned what,
  // when" a single grep target rather than requiring DB row-history
  // reconstruction. Fire-and-forget: logAudit never throws.
  // Metadata has NO PHI: speakerId is an internal numeric label,
  // role is the SpeakerRoleKeys enum (doctor/patient/family/other/
  // unknown), source disambiguates against any future route-path
  // emit. The user identity is captured by logAudit's own session
  // resolution (audit_logs.userId + userEmailSnapshot columns).
  void logAudit({
    action: 'SPEAKER_ROLE_REASSIGNED',
    targetType: 'TranscribeVisit',
    targetId: visitId,
    metadata: {
      source: 'server_action',
      speakerId: parsed.data.speakerId,
      previousRole,
      newRole: parsed.data.role,
    },
  });

  revalidatePath(`/visits/${visitId}`);
  return { ok: true };
}
