import { NextResponse } from 'next/server';

import { AuthError, requireDoctorSession } from '@/lib/auth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import {
  certifyAndActivateTemplateTwin,
  TemplateTwinLifecycleError,
} from '@/lib/template-twin/certification-lifecycle';
import { TemplateTwinCertifyRequestSchema } from '@/lib/template-twin/contracts';
import { isSameOriginTemplateTwinMutation } from '@/lib/template-twin/request-security';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

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
    return response({ ok: false, error: 'The certification request was not same-origin.' }, 403);
  }
  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, session.user.id);
    if (blocked) return blocked;
    const { id } = await context.params;
    const parsed = TemplateTwinCertifyRequestSchema.safeParse(await request.json());
    if (!parsed.success) {
      return response(
        { ok: false, error: 'Both physician certification acknowledgements are required.' },
        400,
      );
    }
    const workspace = await certifyAndActivateTemplateTwin({
      noteTemplateId: id,
      actor: {
        userId: session.user.id,
        userEmail: session.user.email,
        practiceId: session.user.practiceId,
      },
      expectedMappingsSha256: parsed.data.expectedMappingsSha256,
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
              : 'Sign in again before certifying.',
        },
        error.code === 'FORBIDDEN' ? 403 : 401,
      );
    }
    if (error instanceof TemplateTwinLifecycleError) {
      return response(
        { ok: false, error: error.message },
        error.code === 'NOT_FOUND' ? 404 : 409,
      );
    }
    return response({ ok: false, error: 'The template was not certified.' }, 500);
  }
}
