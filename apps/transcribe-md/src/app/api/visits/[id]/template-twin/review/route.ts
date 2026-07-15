import { NextResponse } from 'next/server';

import { AuthError, requireDoctorSession } from '@/lib/auth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { TemplateTwinReviewAcknowledgementRequestSchema } from '@/lib/template-twin/contracts';
import { isSameOriginTemplateTwinMutation } from '@/lib/template-twin/request-security';
import {
  acknowledgeTemplateTwinReview,
  TemplateTwinReviewAcknowledgementError,
} from '@/lib/template-twin/review-acknowledgement';
import { TemplateTwinRolloutError } from '@/lib/template-twin/rollout';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function response(body: unknown, status: number) {
  return NextResponse.json(body, {
    status,
    headers: {
      'Cache-Control': 'no-store, private',
      'X-Content-Type-Options': 'nosniff',
    },
  });
}

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  if (!isSameOriginTemplateTwinMutation(request)) {
    return response(
      { ok: false, error: 'The review request was not same-origin.' },
      403,
    );
  }
  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.VISIT_OPS, session.user.id);
    if (blocked) return blocked;
    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return response(
        { ok: false, error: 'The review confirmation body is not valid JSON.' },
        400,
      );
    }
    const parsed = TemplateTwinReviewAcknowledgementRequestSchema.safeParse(
      body,
    );
    if (!parsed.success) {
      return response(
        { ok: false, error: 'The review confirmation is stale or incomplete.' },
        400,
      );
    }
    const { id } = await context.params;
    const result = await acknowledgeTemplateTwinReview({
      visitId: id,
      expectedManifestVersion: parsed.data.expectedManifestVersion,
      expectedManifestSha256: parsed.data.expectedManifestSha256,
      actor: {
        userId: session.user.id,
        userEmail: session.user.email,
        practiceId: session.user.practiceId,
      },
    });
    return response({ ok: true, result }, 200);
  } catch (error) {
    if (error instanceof AuthError) {
      return response(
        {
          ok: false,
          error:
            error.code === 'FORBIDDEN'
              ? error.message
              : 'Sign in again before confirming review.',
        },
        error.code === 'FORBIDDEN' ? 403 : 401,
      );
    }
    if (error instanceof TemplateTwinRolloutError) {
      return response({ ok: false, error: error.message, code: error.code }, 403);
    }
    if (error instanceof TemplateTwinReviewAcknowledgementError) {
      const status =
        error.code === 'NOT_FOUND'
          ? 404
          : error.code === 'MANIFEST_INVALID' || error.code === 'NOT_READY'
            ? 422
            : 409;
      return response(
        { ok: false, error: error.message, code: error.code },
        status,
      );
    }
    return response(
      {
        ok: false,
        error: 'Review was not confirmed because its durable audit record could not be saved.',
      },
      503,
    );
  }
}
