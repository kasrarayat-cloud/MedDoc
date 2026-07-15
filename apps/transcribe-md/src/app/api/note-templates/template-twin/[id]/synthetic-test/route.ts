import { NextResponse } from 'next/server';

import { AuthError, requireDoctorSession } from '@/lib/auth';
import { TemplateTwinSyntheticTestRequestSchema } from '@/lib/template-twin/contracts';
import { isSameOriginTemplateTwinMutation } from '@/lib/template-twin/request-security';
import {
  runTemplateTwinSyntheticTest,
  TemplateTwinSyntheticTestError,
} from '@/lib/template-twin/synthetic-test';
import {
  TemplateTwinStorageUnavailableError,
  TemplateTwinArtifactIntegrityError,
} from '@/lib/template-twin/storage';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 120;

function response(body: unknown, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { 'Cache-Control': 'no-store, private' },
  });
}

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  if (!isSameOriginTemplateTwinMutation(request)) {
    return response({ ok: false, error: 'The test request was not same-origin.' }, 403);
  }
  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, session.user.id);
    if (blocked) return blocked;
    const { id } = await context.params;
    const parsed = TemplateTwinSyntheticTestRequestSchema.safeParse(
      await request.json(),
    );
    if (!parsed.success) {
      return response(
        { ok: false, error: 'Enter synthetic encounter evidence between 10 and 12,000 characters.' },
        400,
      );
    }
    const workspace = await runTemplateTwinSyntheticTest({
      noteTemplateId: id,
      actor: {
        userId: session.user.id,
        userEmail: session.user.email,
        practiceId: session.user.practiceId,
      },
      ...parsed.data,
    });
    return response({ ok: true, workspace }, 200);
  } catch (error) {
    if (error instanceof AuthError) {
      return response(
        {
          ok: false,
          error:
            error.code === 'FORBIDDEN'
              ? error.message
              : 'Sign in again before testing.',
        },
        error.code === 'FORBIDDEN' ? 403 : 401,
      );
    }
    if (error instanceof TemplateTwinSyntheticTestError) {
      const status =
        error.code === 'NOT_FOUND'
          ? 404
          : error.code === 'VALIDATION_FAILED' ||
              error.code === 'MAPPINGS_NOT_READY' ||
              error.code === 'SYNTHETIC_EVIDENCE_REJECTED'
            ? 422
            : 409;
      return response({ ok: false, error: error.message }, status);
    }
    if (
      error instanceof TemplateTwinStorageUnavailableError ||
      error instanceof TemplateTwinArtifactIntegrityError
    ) {
      return response(
        { ok: false, error: 'Private Template Twin storage could not verify the source or output.' },
        503,
      );
    }
    return response(
      { ok: false, error: 'The synthetic DOCX did not pass independent verification.' },
      500,
    );
  }
}
