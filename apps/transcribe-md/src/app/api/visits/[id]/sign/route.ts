// ============================================================================
// POST /api/visits/[id]/sign (T-M7)
// ----------------------------------------------------------------------------
// The unified sign + deliver path (T-M7) — the SOLE path that transitions a
// visit READY→SIGNED. Accepts a multi-destination body so the doctor can, in
// one click, freeze the note AND paste-to-Epic AND email themselves AND
// download the PDF.
//
// Body: {
//   destinations: Array<
//     | 'clipboard_epic' | 'clipboard_athena' | 'clipboard_cerner'
//     | 'clipboard_eclinicalworks' | 'clipboard_generic'
//     | 'pdf' | 'docx' | 'email'
//   >,
//   emailTo?: string,
//   // E/M visible-confirm (prod smoke #311): REQUIRED (echoing the
//   // recorded {from, to} exactly) when an unacknowledged suggestion-
//   // caused E/M level change exists on the visit — otherwise the
//   // READY→SIGNED transition is refused with 400
//   // { ok:false, error, code:'EM_CHANGE_UNACKNOWLEDGED' }.
//   acknowledgedEmChange?: { from: string, to: string }
// }
//
// Response: {
//   signedAt: ISO,
//   clipboardTexts?: Record<clipboard_format, string>,
//   pdfDownloadUrl?: string,   // "/api/visits/:id/export/pdf"
//   docxDownloadUrl?: string,
//   emailQueued?: boolean
// }
// ============================================================================

import { NextResponse } from 'next/server';
import { rescoreEmAction } from '@/actions/rescore-em';
import {
  emAppliesToSpecialty,
  isImagingReportSpecialty,
  ultrasoundSpecialtyEnabled,
} from '@meddoc/shared/specialties';
import { invalidateVisitFills } from '@/lib/docx-preview/fill-cache';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { Prisma, TranscribeVisitStatus } from '@prisma/client';
import { auth } from '@/lib/nextauth';
import { formatVisitDate } from '@/lib/visit-export';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { computeDisplayedEmCode } from '@/lib/em-coding/displayed-level';
import { formatForEhr, type EhrFormat } from '@/lib/ehr-formatters';
import { generateVisitPdf } from '@/lib/pdf-generator';
import { sendVisitPdfEmail } from '@/lib/email';
import {
  logDelivery,
  type DeliveryChannel,
} from '@/lib/deliveries';
import { captureEditPattern } from '@/lib/edit-tracking';

import { apiError, withApiHandler } from '@/lib/api-error';
import { redactPhi } from '@meddoc/ai';
import { log } from '@/lib/log';
import { logAudit } from '@/lib/audit';
import { criticalWarningRefs } from '@/lib/rx-warnings';
import { unacknowledgedEmChange, type EmChangeCause } from '@/lib/em-pending-change';

export const runtime = 'nodejs';

/** How the refusal message names WHY the level moved. Exhaustive over
 *  `EmChangeCause` on purpose: a new cause must not be able to inherit some
 *  other cause's wording, which is how a doctor's own override came to be
 *  described to them as "an AI-suggestion action". Adding a cause without
 *  adding a phrase here is a type error. */
const EM_CAUSE_PHRASE: Record<EmChangeCause, string> = {
  suggestion_adopted: 'by an AI-suggestion action',
  suggestion_dismissed: 'by an AI-suggestion action',
  note_edited: 'by an edit to the note',
  doctor_override: 'because you set it',
};
export const dynamic = 'force-dynamic';
export const maxDuration = 120;

const Destination = z.enum([
  'clipboard_epic',
  'clipboard_athena',
  'clipboard_cerner',
  'clipboard_eclinicalworks',
  'clipboard_generic',
  'pdf',
  'docx',
  'email',
]);

const BodySchema = z.object({
  destinations: z.array(Destination).max(10).default([]),
  emailTo: z.string().email().max(254).optional(),
  /** E/M visible-confirm (prod smoke #311): the doctor's explicit
   *  acknowledgement of a suggestion-caused E/M level change. Must echo
   *  the recorded {from, to} EXACTLY (content-identity check, same
   *  philosophy as the suggestions lane's expectedText) — a stale tab
   *  can never acknowledge a change the doctor didn't see. */
  acknowledgedEmChange: z
    .object({
      from: z.string().min(1).max(16),
      to: z.string().min(1).max(16),
    })
    .optional(),
  /** THE DOCTOR'S ATTESTATION — required, 2026-08-02.
   *
   *  Until this field existed the attestation was a UI-only gate
   *  (`sign-gates.ts` marked it `serverEnforced: false`). A second sign control
   *  shipped to production that did not count it, and because nothing here
   *  counted it either, the gate could be passed with no refusal and no audit
   *  row. Optional in the SCHEMA so a request without it produces the typed
   *  refusal below rather than a generic 400 the caller cannot act on. */
  attestation: z
    .object({
      acknowledged: z.literal(true),
    })
    .optional(),
});

const FORMAT_FOR_CHANNEL: Partial<
  Record<z.infer<typeof Destination>, EhrFormat>
> = {
  clipboard_epic: 'epic',
  clipboard_athena: 'athena',
  clipboard_cerner: 'cerner',
  clipboard_eclinicalworks: 'eclinicalworks',
  clipboard_generic: 'generic',
};

export const POST = withApiHandler<{ id: string }>(
  'api:visits:sign',
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    const sessionEmail = session?.user?.email;
    if (!userId || !sessionEmail) return apiError('unauthorized', 401);

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) return apiError('invalid destinations payload', 400);

    // ── PHI exfiltration guard ─────────────────────────────────────
    // If an 'email' destination is requested, `emailTo` MUST match
    // the caller's own account email (case-insensitive). Same guard
    // as /api/visits/[id]/export/email — prevents a session holder
    // from co-delivering every signed SOAP to any external inbox in
    // the same click that signs the visit.
    if (parsed.data.destinations.includes('email')) {
      const requestedTo = (parsed.data.emailTo ?? sessionEmail)
        .toLowerCase()
        .trim();
      if (requestedTo !== sessionEmail.toLowerCase().trim()) {
        log.warn('api:visits:sign', 'email destination blocked', {
          userId,
          visitId,
          requestedDomain: requestedTo.split('@')[1] ?? 'unknown',
          sessionDomain: sessionEmail.split('@')[1] ?? 'unknown',
        });
        void logAudit({
          action: 'EXPORT_EMAIL_BLOCKED_DESTINATION',
          targetType: 'TranscribeVisit',
          targetId: visitId,
          success: false,
          errorCode: 'INVALID_DESTINATION',
          metadata: {
            via: 'sign',
            requestedDomain: requestedTo.split('@')[1] ?? 'unknown',
            sessionDomain: sessionEmail.split('@')[1] ?? 'unknown',
          },
        });
        return apiError(
          'Email destination must match your account email.',
          403,
          { code: 'INVALID_DESTINATION', retry: false }
        );
      }
    }

    // ── Sign ────────────────────────────────────────────────────────
    // Use an atomic updateMany with a status guard so two concurrent
    // submissions can't both "win" and double-sign.
    const visit = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: {
        id: true,
        userId: true,
        status: true,
        soapFinal: true,
        icdCodes: true,
        rxDrafts: true,
        cptCodes: true,
        signedAt: true,
        deletedAt: true,
        archivedAt: true,
        emPendingChange: true,
        emStale: true,
        specialty: true,
      },
    });
    if (!visit || visit.userId !== userId) return apiError('not found', 404);
    // T-M17.3: never silently sign a trashed / archived visit. Archived
    // SIGNED visits cannot be re-signed via this route — the operator
    // must unarchive first (dedicated flow, not in T-M17.3 scope).
    if (visit.deletedAt !== null || visit.archivedAt !== null) {
      return NextResponse.json(
        {
          error: 'Visit is no longer active. Restore it first.',
          code: 'VISIT_NOT_ACTIVE',
        },
        { status: 400 }
      );
    }
    if (
      visit.status !== TranscribeVisitStatus.READY &&
      visit.status !== TranscribeVisitStatus.SIGNED
    ) {
      return apiError('visit is still processing', 409);
    }
    if (!visit.soapFinal?.trim()) {
      return apiError('visit has no SOAP to sign', 409);
    }

    // F5-1 + fix/rx-override-gate-correlation: Critical Rx warnings require a
    // PER-WARNING override before sign. Pre-F5-1 the endpoint accepted the
    // transition without checking (the override modal was UI-only, so direct/
    // scripted callers bypassed it). F5-1 added a server gate but compared a
    // BARE COUNT of severity='critical' override rows against the critical-
    // warning count — which a caller could satisfy by minting fabricated/
    // duplicate 'critical' rows. The gate now clears the READY→SIGNED
    // transition ONLY when EVERY persisted critical warning has a matching
    // override keyed by its REAL id (rx-warning-<index>). recordOverride
    // validates the id+severity against rxDrafts on write; this coverage check
    // is the second line of defence at sign time. Already-SIGNED visits skip
    // the gate; it fires on the READY → SIGNED transition only.
    if (visit.status === TranscribeVisitStatus.READY) {
      const criticalRefs = criticalWarningRefs(visit.rxDrafts);
      if (criticalRefs.length > 0) {
        const overrideRows = await prisma.rxWarningOverride.findMany({
          where: { visitId, severity: 'critical' },
          select: { warningId: true },
        });
        const overriddenIds = new Set(
          overrideRows.map((o: { warningId: string }) => o.warningId)
        );
        const unmet = criticalRefs.filter((ref) => !overriddenIds.has(ref.id));
        if (unmet.length > 0) {
          log.warn('api:visits:sign', 'override required', {
            userId,
            visitId,
            criticalCount: criticalRefs.length,
            overriddenCount: overriddenIds.size,
            unmetCount: unmet.length,
          });
          void logAudit({
            action: 'RX_SIGN_BLOCKED_NO_OVERRIDE',
            targetType: 'TranscribeVisit',
            targetId: visitId,
            success: false,
            errorCode: 'OVERRIDE_REQUIRED',
            metadata: {
              criticalCount: criticalRefs.length,
              overriddenCount: overriddenIds.size,
              unmetCount: unmet.length,
            },
          });
          return NextResponse.json(
            {
              error: 'Critical Rx warnings require an override before signing.',
              code: 'OVERRIDE_REQUIRED',
              warnings: unmet.map((ref) => ({
                severity: 'critical',
                drug: ref.warning.rx_drug ?? '',
                message: ref.warning.message ?? '',
                warningId: ref.id,
              })),
            },
            { status: 422 }
          );
        }
      }
    }

    // ── E/M visible-confirm gate (prod smoke #311) ─────────────────────
    // Adopting/dismissing an AI suggestion that changed the computed E/M
    // level records {from, to, cause, at} on the visit (suggestion-
    // actions.ts). The READY→SIGNED transition is REFUSED until the
    // request explicitly echoes that exact {from, to} back — fail-closed
    // server-side, so a UI that forgot to render the confirm control (or
    // a direct/scripted caller) can never sign through a silent level
    // change. Already-SIGNED visits skip the gate (this route only
    // re-delivers them; the change was acknowledged when they signed).
    // ── E/M STALE gate ────────────────────────────────────────────────
    // The note changed since the level was last validated. Until something
    // re-scores it we do not know whether the level moved, and "we do not
    // know" is not a state a note may be signed in.
    //
    // This closes a gap that predates the chat editor: a doctor could edit
    // the note in the inline editor and sign, and nothing ever revisited the
    // E/M level — only ADOPTING a suggestion computed a delta. There is one
    // semantics now, whether a human or a model made the change.
    //
    // It only ADDS a condition; every existing check below is untouched.
    // Imaging reports have no office-visit E/M level at all — the pipeline
    // skips scoring them and the Billing surface says "not applicable". A
    // staleness gate over a level that does not exist would make an ultrasound
    // report permanently unsignable after any edit, and "resolving" it would
    // mean inventing a clinic code. The flag may be set; here it is inert.
    const emApplies = !(
      !emAppliesToSpecialty(visit.specialty)
    );
    if (visit.status === TranscribeVisitStatus.READY && visit.emStale && emApplies) {
      // RE-SCORE HERE, don't just refuse.
      //
      // The first version returned 409 and told the doctor to open the codes
      // row. That made a server-side gate depend on a client control that only
      // exists behind NEXT_PUBLIC_REVIEW_DOC_VIEW — so with that flag off (its
      // own documented rollback), every edited visit became PERMANENTLY
      // unsignable, and in a second tab the named remedy did nothing.
      //
      // Doing the work here costs one scoring call on a path that is already
      // slow, only when the note actually changed, and it means the gate is
      // enforced by the route that owns the transition rather than by whichever
      // surface happens to be rendered. The lazy row-open re-score stays as an
      // optimisation, so most doctors meet the confirm card long before this.
      const rescored = await rescoreEmAction(visitId);
      if (!rescored.ok) {
        void logAudit({
          action: 'EM_SIGN_BLOCKED_STALE',
          targetType: 'TranscribeVisit',
          targetId: visitId,
          metadata: { reason: 'rescore_failed' },
        });
        return apiError(
          "We couldn't re-check the billing level for this note. Try again in a moment.",
          409,
        );
      }
      // Take the re-score's answer WHOLESALE, not just when it armed
      // something. Patching only on `pending` left a cleared record in place:
      // the level came back to the reviewed one, the DB record was dropped,
      // and this still demanded acknowledgement of a change that no longer
      // existed — while the refreshed UI showed no control to give it.
      visit.emPendingChange = rescored.pending
        ? ({
            from: rescored.pending.from,
            to: rescored.pending.to,
            // CARRY THE CAUSE, don't assume it. Hardcoding 'note_edited' here
            // relabelled a doctor's own override as an edit — the record the
            // re-score preserves already knows which it was, and the refusal
            // message below is built from this field.
            cause: rescored.cause ?? 'note_edited',
            at: new Date().toISOString(),
          } as unknown as typeof visit.emPendingChange)
        : null;
    }

    const pendingEm =
      visit.status === TranscribeVisitStatus.READY
        ? unacknowledgedEmChange(visit.emPendingChange)
        : null;
    if (pendingEm) {
      const ack = parsed.data.acknowledgedEmChange;
      if (!ack || ack.from !== pendingEm.from || ack.to !== pendingEm.to) {
        log.warn('api:visits:sign', 'em change unacknowledged', {
          userId,
          visitId,
          from: pendingEm.from,
          to: pendingEm.to,
          cause: pendingEm.cause,
          ackProvided: !!ack,
        });
        void logAudit({
          action: 'EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE',
          targetType: 'TranscribeVisit',
          targetId: visitId,
          success: false,
          errorCode: 'EM_CHANGE_UNACKNOWLEDGED',
          metadata: {
            from: pendingEm.from,
            to: pendingEm.to,
            cause: pendingEm.cause,
          },
        });
        return NextResponse.json(
          {
            ok: false,
            // Name the RIGHT cause. Every level change used to come from a
            // suggestion; an edit can move it now too, and telling a doctor
            // their own edit was "an AI-suggestion action" is a small lie in a
            // message whose whole job is to be believed.
            //
            // EXHAUSTIVE, not a ternary. The two-arm version put every cause it
            // did not name into "by an AI-suggestion action", so the moment a
            // doctor could set the level themselves it told them their own
            // choice was the model's. A Record over EmChangeCause means a new
            // cause fails to TYPECHECK instead of silently misattributing.
            error: `Documentation level changed (${pendingEm.from} → ${pendingEm.to}) ${
              EM_CAUSE_PHRASE[pendingEm.cause]
            } — confirm the new level before signing.`,
            code: 'EM_CHANGE_UNACKNOWLEDGED',
            pendingEmChange: { from: pendingEm.from, to: pendingEm.to },
          },
          { status: 400 }
        );
      }
    }

    // ── GATE 3 — THE ATTESTATION, NOW A SERVER TERM ─────────────────────
    // Same shape as the E/M refusal above: typed code, audit row, 400. It runs
    // for every visit that is actually being signed, on every path, because the
    // lesson that produced it is that a gate only the UI holds is one alternate
    // control away from not existing.
    //
    // ⚠️ LAST, AND THE ORDER IS THE POINT. This block sat FIRST and jumped the
    // queue: a visit with a moved E/M level answered ATTESTATION_REQUIRED
    // instead of naming the level that moved, and two tests that drive the
    // route directly to prove the E/M refusal got the wrong one. `sign-gates`
    // orders the gates rx → em → attestation, which is the order the doctor
    // walks them and the order Gate 3 sits last in. The route refuses in that
    // same order, so the FIRST thing a caller is told is the most clinically
    // specific thing that is wrong — not the formality they were going to do
    // last anyway.
    if (visit.status === TranscribeVisitStatus.READY && !parsed.data.attestation) {
      log.warn('api:visits:sign', 'attestation missing', { userId, visitId });
      void logAudit({
        action: 'SIGN_BLOCKED_NO_ATTESTATION',
        targetType: 'TranscribeVisit',
        targetId: visitId,
        success: false,
        errorCode: 'ATTESTATION_REQUIRED',
        metadata: { status: visit.status },
      });
      return NextResponse.json(
        {
          ok: false,
          error:
            'This note has not been attested. Confirm the attestation before signing.',
          code: 'ATTESTATION_REQUIRED',
        },
        { status: 400 }
      );
    }

    let signedAt = visit.signedAt;
    if (visit.status === TranscribeVisitStatus.READY) {
      // E/M PARITY (2026-06-13, #315 obs#2): FREEZE the authoritative billing
      // code at sign time. The signed note's DISPLAYED level (override ??
      // engine, via computeDisplayedEmCode — the SAME projection the rail
      // shows and the confirm gate guards) becomes cptCodes.em.signedCode, so
      // every downstream artifact (PDF, DOCX, EHR exports) prints the level
      // the doctor reviewed and attested — NOT the raw L7b model suggestion in
      // em.code. Frozen here (not recomputed at export) so it can't drift.
      // Fail-SAFE: a scoring error must never block a sign — the export loader
      // falls back to override ?? code when signedCode is absent.
      let cptWrite: Prisma.InputJsonValue | undefined;
      const cptBlob =
        visit.cptCodes && typeof visit.cptCodes === 'object' && !Array.isArray(visit.cptCodes)
          ? (visit.cptCodes as Record<string, unknown>)
          : null;
      const emBlob =
        cptBlob && cptBlob.em && typeof cptBlob.em === 'object'
          ? (cptBlob.em as Record<string, unknown>)
          : null;
      if (emBlob) {
        try {
          const signedCode = await computeDisplayedEmCode(
            visit.soapFinal ?? '',
            { icdCodes: visit.icdCodes, rxDrafts: visit.rxDrafts, cptCodes: visit.cptCodes },
            { practiceId: session?.user?.practiceId, visitId, userId }
          );
          cptWrite = {
            ...cptBlob,
            em: { ...emBlob, signedCode },
          } as Prisma.InputJsonValue;
        } catch (err) {
          log.warn('api:visits:sign', 'em signedCode freeze failed — export falls back to override ?? code', {
            visitId,
            error: err instanceof Error ? err.message : String(err),
          });
        }
      }
      const updated = await prisma.transcribeVisit.updateMany({
        where: {
          id: visitId,
          status: TranscribeVisitStatus.READY,
        },
        data: {
          status: TranscribeVisitStatus.SIGNED,
          signedSoap: visit.soapFinal,
          signedAt: new Date(),
          // ⚠️ T4 — THE SIGNER, STAMPED SERVER-SIDE, IN THE SAME STATEMENT AS
          // THE SIGNATURE. `userId` is `session.user.id` (line ~137), resolved
          // from the session cookie — it is NEVER read from the request body,
          // because a client-supplied signer is a client-supplied claim about
          // who attested to a clinical record.
          //
          // Set HERE rather than in a follow-up update, deliberately: this
          // `updateMany` is one atomic statement, so a row cannot exist in the
          // window between "signed" and "attributed". The DB CHECK
          // (`signedAt IS NULL OR signedBy IS NOT NULL`) makes that window
          // unrepresentable anyway — this is the code side of the same rule, so
          // the constraint never has to fire in normal operation.
          signedBy: userId,
          ...(cptWrite !== undefined ? { cptCodes: cptWrite } : {}),
          // E/M visible-confirm: the gate above verified the explicit
          // acknowledgement — MARK (not clear) the record so the row
          // keeps the forensic trail alongside the audit rows.
          ...(pendingEm
            ? {
                emPendingChange: {
                  ...pendingEm,
                  acknowledgedAt: new Date().toISOString(),
                } as unknown as Prisma.InputJsonValue,
              }
            : {}),
        },
      });
      // The pre-sign preview cache is keyed on soapVersion, which SIGNING DOES
      // NOT BUMP — so without this a signed visit could be served the pre-sign
      // render for the rest of the TTL, defeating the rule that a signed
      // document is never re-derived. Preview-side only; nothing here is read
      // by this route's own gates.
      void invalidateVisitFills(visitId);

      if (updated.count === 0) {
        // Another concurrent request got there first. Re-read.
        const refreshed = await prisma.transcribeVisit.findUnique({
          where: { id: visitId },
          select: { signedAt: true, status: true },
        });
        if (refreshed?.status !== TranscribeVisitStatus.SIGNED) {
          return apiError('sign race lost — please refresh and retry', 409);
        }
        signedAt = refreshed.signedAt;
      } else {
        const refreshed = await prisma.transcribeVisit.findUnique({
          where: { id: visitId },
          select: { signedAt: true },
        });
        signedAt = refreshed?.signedAt ?? new Date();
        // T-M14.1: fire-and-forget edit-pattern capture. Only on the
        // winning transition — race losers already have a capture in
        // flight from the winner's handler, and the @unique visitId
        // constraint would reject a second insert anyway.
        void captureEditPattern({ visitId, doctorId: userId });
        // HIPAA audit — one row per successful READY→SIGNED transition.
        // Race losers (updated.count===0) don't re-write; the winner
        // already covered them.
        void logAudit({
          action: 'VISIT_SIGNED',
          targetType: 'TranscribeVisit',
          targetId: visitId,
          metadata: {
            destinations: parsed.data.destinations,
            // E/M visible-confirm: record on the SIGN audit row that the
            // doctor explicitly acknowledged the suggestion-caused level
            // change ({from, to} codes only — never note text).
            ...(pendingEm
              ? {
                  emChangeAcknowledged: {
                    from: pendingEm.from,
                    to: pendingEm.to,
                  },
                }
              : {}),
          },
        });
      }
    }

    // ── Deliver ─────────────────────────────────────────────────────
    // loadVisitExportData reads the freshly-signed row so downstream
    // generators see signedSoap / signedAt set correctly.
    const data = await loadVisitExportData(visitId, userId);
    if (!data) return apiError('visit disappeared after signing', 500);

    const clipboardTexts: Record<string, string> = {};
    let pdfDownloadUrl: string | undefined;
    let docxDownloadUrl: string | undefined;
    let emailQueued = false;
    // Track which destinations actually succeeded vs which soft-failed so
    // the client can tell the user specifically what didn't go through.
    const deliveryErrors: Record<string, string> = {};

    for (const dest of parsed.data.destinations) {
      const channel: DeliveryChannel = dest;
      try {
        if (dest === 'pdf') {
          // The browser does the actual download; we return a URL so the
          // JSON response stays small. We still log here — the user
          // explicitly requested a PDF delivery, and the dedicated route
          // will log again when they fetch. Two rows is fine; it
          // reflects intent + completion.
          pdfDownloadUrl = `/api/visits/${visitId}/export/pdf`;
          logDelivery({ visitId, channel });
        } else if (dest === 'docx') {
          docxDownloadUrl = `/api/visits/${visitId}/export/docx`;
          logDelivery({ visitId, channel });
        } else if (dest === 'email') {
          if (!process.env.RESEND_API_KEY) {
            deliveryErrors[dest] =
              'email delivery is not configured on this environment';
            continue;
          }
          // Guard above already enforced emailTo === sessionEmail
          // when present. Resolve to sessionEmail explicitly to
          // close the loop for any future refactor of the guard.
          const to = sessionEmail;
          // Still generated (the delivery row records its size); no longer
          // attached. See sendVisitPdfEmail.
          const pdf = await generateVisitPdf(data);
          await sendVisitPdfEmail({
            toEmail: to,
            visitId,
            doctorName: data.clinicianName,
            visitDate: formatVisitDate(data.signedAt ?? data.createdAt),
          });
          emailQueued = true;
          logDelivery({
            visitId,
            channel,
            destination: to,
            sizeBytes: pdf.byteLength,
          });
        } else {
          const format = FORMAT_FOR_CHANNEL[dest];
          if (!format) continue;
          const text = formatForEhr(format, data);
          clipboardTexts[dest] = text;
          logDelivery({
            visitId,
            channel,
            sizeBytes: Buffer.byteLength(text, 'utf8'),
          });
        }
      } catch (err) {
        // T-M16.3: Resend/MinIO/PDF errors occasionally echo recipient
        // email or filename — scrub before logging.
        console.error(
          `[api:visits:sign] destination ${dest} failed:`,
          redactPhi(err instanceof Error ? err.message : err)
        );
        deliveryErrors[dest] =
          err instanceof Error ? err.message : 'delivery failed';
      }
    }

    return NextResponse.json(
      {
        signedAt: signedAt?.toISOString() ?? null,
        clipboardTexts,
        pdfDownloadUrl,
        docxDownloadUrl,
        emailQueued,
        deliveryErrors: Object.keys(deliveryErrors).length
          ? deliveryErrors
          : undefined,
      },
      { status: 200 }
    );
  }
);
