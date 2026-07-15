import { NextResponse } from 'next/server';

import { AuthError, requireDoctorSession } from '@/lib/auth';
import {
  createTemplateTwinDraft,
  TemplateTwinDraftError,
} from '@/lib/template-twin/create-draft';
import { isSameOriginTemplateTwinMutation } from '@/lib/template-twin/request-security';
import {
  TemplateTwinPhiRejectedError,
  TemplateTwinPhiScanUnavailableError,
} from '@/lib/template-twin/source-phi';
import {
  TemplateTwinArtifactTooLargeError,
  TemplateTwinStorageUnavailableError,
} from '@/lib/template-twin/storage';
import { TemplateDocxError } from '@/lib/note-template-docx';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 120;

const MAX_SOURCE_BYTES = 10 * 1024 * 1024;
const MAX_MULTIPART_BYTES = MAX_SOURCE_BYTES + 256 * 1024;
const DOCX_MIME =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

function json(
  body: { ok: true; certificationUrl: string } | { ok: false; error: string },
  status: number,
) {
  return NextResponse.json(body, {
    status,
    headers: {
      'Cache-Control': 'no-store, private',
      'X-Content-Type-Options': 'nosniff',
    },
  });
}

function safeError(error: unknown): { status: number; message: string } {
  if (error instanceof AuthError) {
    return {
      status: error.code === 'FORBIDDEN' ? 403 : 401,
      message:
        error.code === 'FORBIDDEN'
          ? error.message
          : 'Sign in again before uploading a template.',
    };
  }
  if (error instanceof TemplateTwinPhiRejectedError) {
    return { status: 422, message: error.message };
  }
  if (error instanceof TemplateTwinPhiScanUnavailableError) {
    return { status: 503, message: error.message };
  }
  if (
    error instanceof TemplateTwinStorageUnavailableError ||
    error instanceof TemplateTwinArtifactTooLargeError
  ) {
    return {
      status: error instanceof TemplateTwinArtifactTooLargeError ? 413 : 503,
      message:
        error instanceof TemplateTwinArtifactTooLargeError
          ? 'The compiled Word artifact exceeds the supported size.'
          : 'Private Template Twin storage is not available. The template was not activated.',
    };
  }
  if (error instanceof TemplateDocxError) {
    if (error.code === 'DOCM_REJECTED') {
      return { status: 422, message: 'Macro-enabled Word files are not accepted. Save a clean .docx copy.' };
    }
    if (
      error.code === 'EXTERNAL_RELATIONSHIP_REJECTED' ||
      error.code === 'EMBEDDED_OBJECT_REJECTED' ||
      error.code === 'ACTIVE_CONTENT_REJECTED'
    ) {
      return {
        status: 422,
        message: 'The Word file contains external, embedded, or active content that cannot be certified.',
      };
    }
    return {
      status: 422,
      message: 'The Word package failed structural safety checks. Open it in Word, save a clean DOCX copy, and try again.',
    };
  }
  if (error instanceof TemplateTwinDraftError) {
    return {
      status: error.code === 'NO_FILLABLE_FIELDS' ? 422 : 500,
      message: error.message,
    };
  }
  return {
    status: 500,
    message: 'The template could not be compiled. Nothing was activated.',
  };
}

export async function POST(request: Request) {
  if (!isSameOriginTemplateTwinMutation(request)) {
    return json({ ok: false, error: 'The upload request was not same-origin.' }, 403);
  }

  const contentLength = Number(request.headers.get('content-length') ?? '0');
  if (Number.isFinite(contentLength) && contentLength > MAX_MULTIPART_BYTES) {
    return json({ ok: false, error: 'Template Twin accepts DOCX files up to 10 MB.' }, 413);
  }

  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, session.user.id);
    if (blocked) return blocked;
    const formData = await request.formData();
    const file = formData.get('file');
    if (!(file instanceof File)) {
      return json({ ok: false, error: 'Choose one original DOCX file.' }, 400);
    }
    const lowerName = file.name.toLowerCase();
    if (!lowerName.endsWith('.docx') || lowerName.endsWith('.docm')) {
      return json({ ok: false, error: 'Choose a macro-free .docx file.' }, 415);
    }
    if (
      file.type &&
      file.type !== DOCX_MIME &&
      file.type !== 'application/octet-stream'
    ) {
      return json({ ok: false, error: 'The selected file is not a DOCX package.' }, 415);
    }
    if (file.size < 1 || file.size > MAX_SOURCE_BYTES) {
      return json({ ok: false, error: 'Template Twin accepts non-empty DOCX files up to 10 MB.' }, 413);
    }

    const source = new Uint8Array(await file.arrayBuffer());
    if (source.byteLength !== file.size) {
      return json({ ok: false, error: 'The uploaded file was incomplete. Try again.' }, 400);
    }

    const result = await createTemplateTwinDraft({
      source,
      actor: {
        userId: session.user.id,
        userEmail: session.user.email,
        practiceId: session.user.practiceId,
      },
    });
    return json(
      {
        ok: true,
        certificationUrl: `/settings/note-format/${encodeURIComponent(result.noteTemplateId)}/certify`,
      },
      201,
    );
  } catch (error) {
    const safe = safeError(error);
    return json({ ok: false, error: safe.message }, safe.status);
  }
}
