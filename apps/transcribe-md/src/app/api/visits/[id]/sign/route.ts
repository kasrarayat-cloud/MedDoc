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
//     | 'pdf' | 'docx' | 'docx_original_template' | 'email'
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
//   originalTemplateDocxDownloadUrl?: string,
//   emailQueued?: boolean
// }
// ============================================================================

import { NextResponse } from 'next/server';
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
import { AuthError, requireFreshDoctorIdentity } from '@/lib/auth';
import { redactPhi } from '@meddoc/ai';
import { log } from '@/lib/log';
import { logAudit } from '@/lib/audit';
import { criticalWarningRefs } from '@/lib/rx-warnings';
import { unacknowledgedEmChange } from '@/lib/em-pending-change';
import {
  assessTemplateTwinSigning,
  TEMPLATE_TWIN_SIGNING_VISIT_SELECT,
} from '@/lib/template-twin/signing-gate';
import {
  createTemplateTwinArtifactStore,
  TemplateTwinStorageUnavailableError,
} from '@/lib/template-twin/storage';

export const runtime = 'nodejs';
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
  'docx_original_template',
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

class TemplateTwinSignClaimConflict extends Error {
  constructor() {
    super('Template Twin signing claim changed concurrently.');
    this.name = 'TemplateTwinSignClaimConflict';
  }
}

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
        ...TEMPLATE_TWIN_SIGNING_VISIT_SELECT,
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

    let templateTwinPracticeId = session.user.practiceId ?? '';
    if (visit.noteTemplate?.templateKind === 'template_twin_docx') {
      try {
        templateTwinPracticeId = (
          await requireFreshDoctorIdentity(userId)
        ).practiceId;
      } catch (error) {
        if (error instanceof AuthError) {
          return apiError('physician role required', 403, {
            code: 'DOCTOR_ROLE_REQUIRED',
            retry: false,
          });
        }
        throw error;
      }
    }

    // Template Twin is a server-enforced clinical gate. The persisted
    // manifest, validation result, immutable version pins, output digest, and
    // renderer round-trip proof are independently cross-checked here. UI
    // readiness state is never sufficient to authorize READY -> SIGNED.
    const twinGate = assessTemplateTwinSigning({
      visitId: visit.id,
      practiceId: templateTwinPracticeId,
      visitStatus: visit.status,
      noteTemplateId: visit.noteTemplateId,
      noteTemplateVersion: visit.noteTemplateVersion,
      noteTemplate: visit.noteTemplate,
      templateTwinFill: visit.templateTwinFill,
    });
    const wantsOriginalTemplate = parsed.data.destinations.includes(
      'docx_original_template',
    );
    const twinBlockerCodes =
      twinGate.applies && twinGate.ready && !twinGate.claim
        ? [...twinGate.blockerCodes, 'FILL_MANIFEST_MISSING' as const]
        : twinGate.blockerCodes;

    if (wantsOriginalTemplate && !twinGate.applies) {
      return NextResponse.json(
        {
          ok: false,
          error: 'This visit does not have an Original Template DOCX.',
          code: 'TEMPLATE_TWIN_OUTPUT_UNAVAILABLE',
        },
        { status: 400 },
      );
    }

    if (
      twinGate.applies &&
      (!twinGate.ready || !twinGate.claim) &&
      (visit.status === TranscribeVisitStatus.READY || wantsOriginalTemplate)
    ) {
      log.warn('api:visits:sign', 'Template Twin sign blocked', {
        userId,
        visitId,
        blockerCodes: twinBlockerCodes,
        blockerCount: twinBlockerCodes.length,
      });
      void logAudit({
        action: 'TEMPLATE_TWIN_SIGN_BLOCKED',
        targetType: 'TranscribeVisit',
        targetId: visitId,
        success: false,
        errorCode: 'TEMPLATE_TWIN_SIGN_BLOCKED',
        practiceId: session.user.practiceId,
        metadata: {
          blockerCodes: twinBlockerCodes,
          blockerCount: twinBlockerCodes.length,
          compiledVersionId: twinGate.compiledVersionId,
          fillManifestId: twinGate.fillManifestId,
          noteTemplateVersion: visit.noteTemplateVersion,
        },
      });
      return NextResponse.json(
        {
          ok: false,
          error:
            'Review the unresolved Template Twin fields and regenerate the verified document before signing.',
          code: 'TEMPLATE_TWIN_SIGN_BLOCKED',
          blockerCodes: twinBlockerCodes,
        },
        { status: 422 },
      );
    }

    // Selecting the exact-source delivery is a sign-and-deliver operation,
    // not merely permission to reveal a future URL. Verify the immutable
    // object through tenant/key/metadata/size/SHA checks before attestation;
    // the download route repeats the same verification as defense in depth.
    if (wantsOriginalTemplate && twinGate.ready && twinGate.claim) {
      const fill = visit.templateTwinFill;
      if (
        !fill?.outputObjectKey ||
        !fill.outputSha256 ||
        !fill.outputSizeBytes
      ) {
        return apiError('verified Original Template DOCX unavailable', 409, {
          code: 'TEMPLATE_TWIN_OUTPUT_UNAVAILABLE',
          retry: false,
        });
      }
      try {
        await createTemplateTwinArtifactStore().readOutputArtifact({
          practiceId: templateTwinPracticeId,
          objectKey: fill.outputObjectKey,
          expectedSha256: fill.outputSha256,
          expectedSizeBytes: fill.outputSizeBytes,
        });
      } catch (error) {
        const unavailable = error instanceof TemplateTwinStorageUnavailableError;
        log.warn('api:visits:sign', 'Template Twin delivery preflight failed', {
          userId,
          visitId,
          errorCode: unavailable
            ? 'TEMPLATE_TWIN_STORAGE_UNAVAILABLE'
            : 'TEMPLATE_TWIN_OUTPUT_INTEGRITY_FAILED',
        });
        void logAudit({
          action: 'TEMPLATE_TWIN_SIGN_BLOCKED',
          targetType: 'TranscribeVisit',
          targetId: visitId,
          practiceId: templateTwinPracticeId,
          success: false,
          errorCode: unavailable
            ? 'TEMPLATE_TWIN_STORAGE_UNAVAILABLE'
            : 'TEMPLATE_TWIN_OUTPUT_INTEGRITY_FAILED',
          metadata: {
            compiledVersionId: twinGate.compiledVersionId,
            fillManifestId: twinGate.fillManifestId,
          },
        });
        return apiError(
          unavailable
            ? 'Original Template DOCX storage is temporarily unavailable.'
            : 'Original Template DOCX failed integrity verification.',
          unavailable ? 503 : 409,
          {
            code: unavailable
              ? 'TEMPLATE_TWIN_STORAGE_UNAVAILABLE'
              : 'TEMPLATE_TWIN_OUTPUT_INTEGRITY_FAILED',
            retry: unavailable,
          },
        );
      }
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
            error: `Documentation level changed (${pendingEm.from} → ${pendingEm.to}) by an AI-suggestion action — confirm the new level before signing.`,
            code: 'EM_CHANGE_UNACKNOWLEDGED',
            pendingEmChange: { from: pendingEm.from, to: pendingEm.to },
          },
          { status: 400 }
        );
      }
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
      const signDecisionAt = new Date();
      const visitUpdate = {
        where: {
          id: visitId,
          status: TranscribeVisitStatus.READY,
        },
        data: {
          status: TranscribeVisitStatus.SIGNED,
          signedSoap: visit.soapFinal,
          signedAt: signDecisionAt,
          ...(cptWrite !== undefined ? { cptCodes: cptWrite } : {}),
          // E/M visible-confirm: the gate above verified the explicit
          // acknowledgement — MARK (not clear) the record so the row
          // keeps the forensic trail alongside the audit rows.
          ...(pendingEm
            ? {
                emPendingChange: {
                  ...pendingEm,
                  acknowledgedAt: signDecisionAt.toISOString(),
                } as unknown as Prisma.InputJsonValue,
              }
            : {}),
        },
      };

      let updated: { count: number };
      const twinClaim =
        twinGate.applies && twinGate.ready ? twinGate.claim : null;
      if (twinClaim) {
        try {
          updated = await prisma.$transaction(
            async (tx: typeof prisma): Promise<{ count: number }> => {
              // Optimistically claim the exact manifest assessed above. Any
              // concurrent correction/regeneration changes status, version,
              // digest, output, or updatedAt and rolls back this transaction.
              const claimed = await tx.templateTwinFillManifest.updateMany({
                where: {
                  id: twinClaim.id,
                  status: 'VERIFIED',
                  manifestVersion: twinClaim.manifestVersion,
                  manifestSha256: twinClaim.manifestSha256,
                  outputSha256: twinClaim.outputSha256,
                  roundTripVerified: true,
                  criticalUnresolvedCount: 0,
                  signedDecisionAt: null,
                  updatedAt: twinClaim.updatedAt,
                },
                data: {
                  status: 'SIGNED',
                  signedDecisionAt: signDecisionAt,
                },
              });
              if (claimed.count !== 1) {
                throw new TemplateTwinSignClaimConflict();
              }
              const visitUpdated = await tx.transcribeVisit.updateMany(
                visitUpdate,
              );
              if (visitUpdated.count !== 1) {
                throw new TemplateTwinSignClaimConflict();
              }
              return visitUpdated;
            },
          );
        } catch (error) {
          if (!(error instanceof TemplateTwinSignClaimConflict)) throw error;
          updated = { count: 0 };
        }
      } else {
        updated = await prisma.transcribeVisit.updateMany(visitUpdate);
      }
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
            ...(twinGate.applies
              ? {
                  templateTwin: {
                    compiledVersionId: twinGate.compiledVersionId,
                    fillManifestId: twinGate.fillManifestId,
                    manifestVersion: twinClaim?.manifestVersion ?? null,
                  },
                }
              : {}),
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
    let originalTemplateDocxDownloadUrl: string | undefined;
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
        } else if (dest === 'docx_original_template') {
          originalTemplateDocxDownloadUrl =
            `/api/visits/${visitId}/export/original-template-docx`;
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
          const pdf = await generateVisitPdf(data);
          await sendVisitPdfEmail({
            toEmail: to,
            visitId,
            pdfBuffer: pdf,
            doctorName: data.clinicianName,
            patientName: data.patientName,
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
        originalTemplateDocxDownloadUrl,
        emailQueued,
        deliveryErrors: Object.keys(deliveryErrors).length
          ? deliveryErrors
          : undefined,
      },
      { status: 200 }
    );
  }
);
