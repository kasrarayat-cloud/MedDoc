"use server";

import { revalidatePath } from "next/cache";
import {
  emAppliesToSpecialty,
  isImagingReportSpecialty,
  ultrasoundSpecialtyEnabled,
} from "@meddoc/shared/specialties";
import { seedEmBaselineIfUnset } from "@/lib/em-coding/seed-baseline";
import { z } from "zod";

import prisma from "@meddoc/db";
import { visitByIdScope, ScopedWriteMissError } from "@/lib/practice-scope";
import { TranscribeVisitStatus } from "@prisma/client";
import { requireSession } from "@/lib/auth";

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
  expectedVersion?: number,
): Promise<SaveSoapResult> {
  const session = await requireSession();
  const parsed = SaveSoapSchema.safeParse({ visitId, text, expectedVersion });
  if (!parsed.success) {
    return { ok: false, error: "Invalid input." };
  }

  const visit = await prisma.transcribeVisit.findFirst({
    where: visitByIdScope(visitId, session.user.practiceId),
    select: {
      id: true,
      userId: true,
      status: true,
      deletedAt: true,
      archivedAt: true,
      // For the baseline seed: the note as it stands BEFORE this save, and
      // the signals the level is scored from.
      soapFinal: true,
      emScoredCode: true,
      specialty: true,
      icdCodes: true,
      rxDrafts: true,
      cptCodes: true,
      user: { select: { practiceId: true } },
    },
  });
  // T6 §4.1c — the author conjunct is GONE; practice membership is the gate.
  // The read above is practice-scoped (T5), so reaching this line means the
  // visit is in the caller's practice. SIGNING is the only role-gated action
  // (SPEC §1.2); tech-creates/doctor-signs requires every member to be able to
  // prepare work.
  if (!visit) {
    return { ok: false, error: "Visit not found." };
  }
  // T-M17.3: reject writes on trashed / archived visits. The UI
  // already hides these from the default dashboard but a stale tab
  // could still fire this action.
  if (visit.deletedAt !== null || visit.archivedAt !== null) {
    return { ok: false, error: "Visit is no longer active. Restore it first." };
  }
  if (visit.status === TranscribeVisitStatus.SIGNED) {
    return { ok: false, error: "Signed notes cannot be edited." };
  }
  if (visit.status !== TranscribeVisitStatus.READY) {
    return { ok: false, error: "Note is still processing." };
  }

  // Round 3 PR-E (A09-P0-003) — optimistic-concurrency path.
  // updateMany with a WHERE clause on soapVersion is atomic in
  // Postgres: only one of two concurrent saves with the same
  // expectedVersion succeeds; the other returns count=0.
  if (parsed.data.expectedVersion !== undefined) {
    const result = await prisma.transcribeVisit.updateMany({
      where: {
            ...visitByIdScope(visitId, session.user.practiceId),
            soapVersion: parsed.data.expectedVersion,
          },
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
      const current = await prisma.transcribeVisit.findFirst({
        where: visitByIdScope(visitId, session.user.practiceId),
        select: { soapVersion: true, soapFinal: true },
      });
      return {
        ok: false,
        error: "conflict",
        conflict: {
          currentVersion: current?.soapVersion ?? -1,
          currentText: current?.soapFinal ?? "",
        },
      };
    }
    // Seed the E/M baseline from the PRE-EDIT note — AFTER the write, as adopt
    // does. `visit.soapFinal` is still the pre-edit text here (it was read
    // above), and scoring can be an LLM round-trip: inside the read→write window
    // of the soapVersion check it widened the race on the AUTOSAVE path and
    // produced spurious "the note changed in another tab" conflicts.
    // Page view seeds it for most visits, but not for a doctor whose first
    // action is an edit — and for them the first re-score would find no
    // baseline, conclude nothing had moved, and clear the gate.
    await seedEmBaselineIfUnset({
      visitId,
      priorSoap: visit.soapFinal,
      currentScoredCode: visit.emScoredCode,
      signals: {
        icdCodes: visit.icdCodes,
        rxDrafts: visit.rxDrafts,
        cptCodes: visit.cptCodes,
      },
      ctx: { practiceId: visit.user?.practiceId, userId: session.user.id },
      applies: emAppliesToSpecialty(visit.specialty),
    });

    revalidatePath(`/visits/${visitId}`);
    return { ok: true, newVersion: parsed.data.expectedVersion + 1 };
  }

  // Legacy fallback (no expectedVersion supplied) — last-write-wins.
  // Still bumps soapVersion so a subsequent expectedVersion-aware
  // call sees the right value.
  // ⚠️ T5-W — TRANSACTIONAL updateMany + re-read, and the transaction is
  // LOAD-BEARING here rather than decorative.
  //
  // `soapVersion: { increment: 1 }` means the value the caller must be told is
  // not knowable from the input — it is whatever the increment produced. A
  // re-read OUTSIDE a transaction could observe a DIFFERENT writer's increment
  // and report a version this call never wrote, which is precisely the
  // read-after-write window the optimistic `expectedVersion` path above exists
  // to close. So the write and the read share one transaction.
  //
  // The alternative treatment — keep `update` and argue the preceding
  // practice-scoped read authorises it — was available and NOT taken here: this
  // is the last-write-wins fallback, which by definition has no version guard,
  // so it is the one path where borrowed authorisation has the least to lean on.
  const updated = await prisma.$transaction(async (tx: typeof prisma) => {
    const res = await tx.transcribeVisit.updateMany({
      where: visitByIdScope(visitId, session.user.practiceId),
      data: {
        soapFinal: parsed.data.text,
        emStale: true,
        soapVersion: { increment: 1 },
      },
    });
    if (res.count === 0)
      throw new ScopedWriteMissError("transcribeVisit", visitId);
    return tx.transcribeVisit.findFirstOrThrow({
      where: visitByIdScope(visitId, session.user.practiceId),
      select: { soapVersion: true },
    });
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

// SPEAKER REASSIGNMENT WAS REMOVED HERE — 2026-07-28.
//
// `reassignSpeakerAction` lost its only caller when the input-transcript panel
// came off the review page. Rather than leave a server action nothing could
// reach, it was deleted, and the reasoning is worth keeping because the obvious
// move — re-surface it through the chat editor — is the wrong one:
//
//   1. To reassign a speaker you must first SEE which speaker is wrong, which
//      means reading utterances attributed to speakers. Putting that in the
//      chat rebuilds the transcript panel inside the chat.
//   2. Decisive: it changed nothing about the artifact being signed. The action
//      mutated `speakerMap` and never re-ran the pipeline — its own success
//      toast said "Re-running the SOAP pipeline will pick up the new roles".
//      On a pre-sign review page the note is already written. A control that
//      appears to fix attribution while the document under it does not move is
//      the pretend-success class, and realising it needs a regenerate, which
//      would discard the doctor's edits.
//
// The 'SPEAKER_ROLE_REASSIGNED' audit action is KEPT in lib/audit.ts: rows
// written before today still reference it, and an audit enum that forgets its
// own history makes those rows unreadable.
//
// Logged in the Q1 fix-pack. If speaker attribution needs correcting again, the
// place for it is before the pipeline runs, not after the note exists.
