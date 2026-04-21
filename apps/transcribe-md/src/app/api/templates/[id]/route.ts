// ============================================================================
// GET /api/templates/[id] + DELETE /api/templates/[id] (T-M24)
// ----------------------------------------------------------------------------
// Single-template fetch + soft-delete. Delete sets `deletedAt` — the
// MinIO object is deliberately NOT removed so visits that referenced
// this template can still render their filled output. A future ops job
// can purge old soft-deleted templates + their objects once we have
// one.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { apiError, withApiHandler } from '@/lib/api-error';
import { auth } from '@/lib/nextauth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { log } from '@/lib/log';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// ---------------------------------------------------------------------------
// GET /api/templates/[id]
// Returns the template metadata (no binary, no extractedText). The
// visit-picker UI uses this to show which tokens will be filled.
// 404 on missing / not-yours / soft-deleted — collapsed so the caller
// can't distinguish "doesn't exist" from "belongs to someone else".
// ---------------------------------------------------------------------------

export const GET = withApiHandler<{ id: string }>(
  'api:templates:get',
  async (_req, { params }) => {
    const { id } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

    const template = await prisma.transcribeTemplate.findUnique({
      where: { id },
      select: {
        id: true,
        userId: true,
        name: true,
        originalFileName: true,
        tokens: true,
        createdAt: true,
        updatedAt: true,
        deletedAt: true,
      },
    });

    if (
      !template ||
      template.userId !== userId ||
      template.deletedAt !== null
    ) {
      return apiError('not found', 404);
    }

    // Strip userId + deletedAt from the response; callers only need
    // the user-facing fields.
    const { userId: _, deletedAt: __, ...rest } = template;
    return NextResponse.json(rest, { status: 200 });
  }
);

// ---------------------------------------------------------------------------
// DELETE /api/templates/[id]
// Soft-delete — sets `deletedAt`. Existing `transcribe_visits` rows
// that reference this template keep their templateId FK intact (the
// FK is `ON DELETE SET NULL` for the *hard* delete path, but soft
// delete leaves the row present so visits keep working). The
// filled-docx endpoint in commit 4 will check `deletedAt` before
// attempting to regenerate.
// ---------------------------------------------------------------------------

export const DELETE = withApiHandler<{ id: string }>(
  'api:templates:delete',
  async (_req, { params }) => {
    const { id } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

    const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, userId);
    if (blocked) return blocked;

    const template = await prisma.transcribeTemplate.findUnique({
      where: { id },
      select: { id: true, userId: true, deletedAt: true },
    });

    if (
      !template ||
      template.userId !== userId ||
      template.deletedAt !== null
    ) {
      return apiError('not found', 404);
    }

    await prisma.transcribeTemplate.update({
      where: { id },
      data: { deletedAt: new Date() },
    });

    log.info('api:templates:delete', 'template soft-deleted', {
      userId,
      templateId: id,
    });

    return NextResponse.json({ ok: true }, { status: 200 });
  }
);
