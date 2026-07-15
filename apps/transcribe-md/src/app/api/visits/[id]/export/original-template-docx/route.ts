import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { apiError, withApiHandler } from '@/lib/api-error';
import { AuthError, requireFreshDoctorIdentity } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import { logDelivery } from '@/lib/deliveries';
import { log } from '@/lib/log';
import { auth } from '@/lib/nextauth';
import {
  assessTemplateTwinSigning,
  TEMPLATE_TWIN_SIGNING_VISIT_SELECT,
} from '@/lib/template-twin/signing-gate';
import {
  createTemplateTwinArtifactStore,
  TemplateTwinArtifactIntegrityError,
  TemplateTwinStorageUnavailableError,
} from '@/lib/template-twin/storage/artifact-store';
import { DOCX_MIME_TYPE } from '@/lib/template-twin/storage/keys';
import { TemplateTwinArtifactNotFoundError } from '@/lib/template-twin/storage/ownership';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 60;

/**
 * Delivers the already-rendered clone of the physician's immutable source
 * template. This route never regenerates a document. It authorizes visit
 * ownership, re-runs the signing-readiness proof, then verifies object key,
 * tenant, size, metadata, and SHA-256 while reading the immutable bytes.
 */
export const GET = withApiHandler<{ id: string }>(
  'api:visits:export:original-template-docx',
  async (_request, { params }) => {
    const { id: visitId } = await params;
    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);
    let practiceId: string;
    try {
      practiceId = (await requireFreshDoctorIdentity(userId)).practiceId;
    } catch (error) {
      if (error instanceof AuthError) {
        return apiError('physician role required', 403, {
          code: 'DOCTOR_ROLE_REQUIRED',
          retry: false,
        });
      }
      throw error;
    }

    const visit = await prisma.transcribeVisit.findFirst({
      where: {
        id: visitId,
        userId,
        status: TranscribeVisitStatus.SIGNED,
        deletedAt: null,
      },
      select: {
        id: true,
        status: true,
        ...TEMPLATE_TWIN_SIGNING_VISIT_SELECT,
      },
    });
    if (!visit) return apiError('not found', 404);

    const assessment = assessTemplateTwinSigning({
      visitId: visit.id,
      practiceId,
      visitStatus: visit.status,
      noteTemplateId: visit.noteTemplateId,
      noteTemplateVersion: visit.noteTemplateVersion,
      noteTemplate: visit.noteTemplate,
      templateTwinFill: visit.templateTwinFill,
    });
    if (!assessment.applies) return apiError('not found', 404);
    if (!assessment.ready || !assessment.claim || !visit.templateTwinFill) {
      log.warn(
        'api:visits:export:original-template-docx',
        'verified output unavailable',
        {
          userId,
          visitId,
          blockerCodes: assessment.blockerCodes,
          blockerCount: assessment.blockerCodes.length,
        },
      );
      void logAudit({
        action: 'EXPORT_TEMPLATE_TWIN_DOCX_DOWNLOADED',
        targetType: 'TranscribeVisit',
        targetId: visitId,
        practiceId,
        success: false,
        errorCode: 'TEMPLATE_TWIN_OUTPUT_UNVERIFIED',
        metadata: {
          blockerCodes: assessment.blockerCodes,
          blockerCount: assessment.blockerCodes.length,
          compiledVersionId: assessment.compiledVersionId,
          fillManifestId: assessment.fillManifestId,
        },
      });
      return NextResponse.json(
        {
          ok: false,
          error: 'The verified Original Template DOCX is not available.',
          code: 'TEMPLATE_TWIN_OUTPUT_UNVERIFIED',
        },
        { status: 409 },
      );
    }

    const fill = visit.templateTwinFill;
    // These columns are proven non-null by assessTemplateTwinSigning. Keep the
    // guard explicit so a future refactor cannot weaken that invariant.
    if (
      !fill.outputObjectKey ||
      !fill.outputSha256 ||
      !fill.outputSizeBytes
    ) {
      return apiError('verified output unavailable', 409);
    }

    let document: Buffer;
    try {
      document = await createTemplateTwinArtifactStore().readOutputArtifact({
        practiceId,
        objectKey: fill.outputObjectKey,
        expectedSha256: fill.outputSha256,
        expectedSizeBytes: fill.outputSizeBytes,
      });
    } catch (error) {
      const unavailable = error instanceof TemplateTwinStorageUnavailableError;
      const integrityFailure =
        error instanceof TemplateTwinArtifactIntegrityError ||
        error instanceof TemplateTwinArtifactNotFoundError;
      log.warn(
        'api:visits:export:original-template-docx',
        'artifact read failed',
        {
          userId,
          visitId,
          errorCode: unavailable
            ? 'TEMPLATE_TWIN_STORAGE_UNAVAILABLE'
            : integrityFailure
              ? 'TEMPLATE_TWIN_OUTPUT_INTEGRITY_FAILED'
              : 'TEMPLATE_TWIN_OUTPUT_READ_FAILED',
        },
      );
      void logAudit({
        action: 'EXPORT_TEMPLATE_TWIN_DOCX_DOWNLOADED',
        targetType: 'TranscribeVisit',
        targetId: visitId,
        practiceId,
        success: false,
        errorCode: unavailable
          ? 'TEMPLATE_TWIN_STORAGE_UNAVAILABLE'
          : 'TEMPLATE_TWIN_OUTPUT_INTEGRITY_FAILED',
        metadata: {
          compiledVersionId: assessment.compiledVersionId,
          fillManifestId: assessment.fillManifestId,
        },
      });
      return NextResponse.json(
        {
          ok: false,
          error: unavailable
            ? 'Original Template DOCX storage is temporarily unavailable.'
            : 'The Original Template DOCX failed integrity verification.',
          code: unavailable
            ? 'TEMPLATE_TWIN_STORAGE_UNAVAILABLE'
            : 'TEMPLATE_TWIN_OUTPUT_INTEGRITY_FAILED',
        },
        { status: unavailable ? 503 : 409 },
      );
    }

    logDelivery({
      visitId,
      channel: 'docx_original_template',
      sizeBytes: document.byteLength,
    });
    void logAudit({
      action: 'EXPORT_TEMPLATE_TWIN_DOCX_DOWNLOADED',
      targetType: 'TranscribeVisit',
      targetId: visitId,
      practiceId,
      metadata: {
        sizeBytes: document.byteLength,
        compiledVersionId: assessment.compiledVersionId,
        fillManifestId: assessment.fillManifestId,
        noteTemplateVersion: visit.noteTemplateVersion,
      },
    });

    return new NextResponse(document as unknown as BodyInit, {
      status: 200,
      headers: {
        'Content-Type': DOCX_MIME_TYPE,
        'Content-Length': String(document.byteLength),
        'Content-Disposition':
          `attachment; filename="quillmd-original-template-${visitId}.docx"`,
        'Cache-Control': 'no-store, private',
        'X-Content-Type-Options': 'nosniff',
      },
    });
  },
);
