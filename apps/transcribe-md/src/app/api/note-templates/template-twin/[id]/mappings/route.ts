import { NextResponse } from 'next/server';

import { AuthError, requireSession } from '@/lib/auth';
import {
  TemplateTwinLifecycleError,
  updateTemplateTwinMappings,
} from '@/lib/template-twin/certification-lifecycle';
import { TemplateTwinUpdateMappingsRequestSchema } from '@/lib/template-twin/contracts';
import { isSameOriginTemplateTwinMutation } from '@/lib/template-twin/request-security';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function response(body: unknown, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { 'Cache-Control': 'no-store, private' },
  });
}

export async function PATCH(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  if (!isSameOriginTemplateTwinMutation(request)) {
    return response({ ok: false, error: 'The update request was not same-origin.' }, 403);
  }
  try {
    const session = await requireSession();
    const { id } = await context.params;
    const parsed = TemplateTwinUpdateMappingsRequestSchema.safeParse(
      await request.json(),
    );
    if (!parsed.success) {
      return response({ ok: false, error: 'The mapping draft is invalid.' }, 400);
    }
    const workspace = await updateTemplateTwinMappings({
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
      return response({ ok: false, error: 'Sign in again before saving.' }, 401);
    }
    if (error instanceof TemplateTwinLifecycleError) {
      const status = error.code === 'NOT_FOUND' ? 404 : error.code === 'MAPPING_INVALID' || error.code === 'FIELD_SET_MISMATCH' ? 422 : 409;
      return response({ ok: false, error: error.message }, status);
    }
    return response({ ok: false, error: 'Mappings were not saved.' }, 500);
  }
}
