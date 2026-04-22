// ============================================================================
// POST /api/templates + GET /api/templates (T-M24)
// ----------------------------------------------------------------------------
// Template upload + list. Parallel to the audio upload pattern but with
// multipart `file` + `name` fields, no visit FK, and mammoth-extracted
// text cached at upload time so the L7f worker layer doesn't re-parse
// the binary per visit.
// ============================================================================

import { randomUUID } from 'node:crypto';

import { NextResponse } from 'next/server';
import mammoth from 'mammoth';

import prisma from '@meddoc/db';
import { redactPhi } from '@meddoc/ai';

import { apiError, withApiHandler } from '@/lib/api-error';
import { auth } from '@/lib/nextauth';
import {
  buildTemplateObjectKey,
  putTemplate,
} from '@/lib/minio';
import { extractTokens, partitionTokens } from '@/lib/template-tokens';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { log } from '@/lib/log';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const MAX_TEMPLATE_BYTES = 5 * 1024 * 1024; // 5 MB
const DOCX_MIME =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

// ---------------------------------------------------------------------------
// POST /api/templates — upload
// Body: multipart/form-data with `file` (.docx) + `name` (string, 1-80 chars)
// Response: 201 { id, name, originalFileName, tokens, unsupportedTokens,
//                 createdAt }
// ---------------------------------------------------------------------------

export const POST = withApiHandler('api:templates:upload', async (req) => {
  const session = await auth();
  const userId = session?.user?.id;
  if (!userId) return apiError('unauthorized', 401);

  const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, userId);
  if (blocked) return blocked;

  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return apiError('expected multipart/form-data body', 400);
  }

  const file = form.get('file');
  const nameField = form.get('name');
  if (!(file instanceof File)) {
    return apiError('file is required (multipart field "file")', 400);
  }
  if (typeof nameField !== 'string') {
    return apiError('name is required (multipart field "name")', 400);
  }

  const name = nameField.trim();
  if (!name || name.length > 80) {
    return apiError('name must be 1–80 characters', 400);
  }

  if (file.size === 0) {
    return apiError('uploaded file is empty', 400);
  }
  if (file.size > MAX_TEMPLATE_BYTES) {
    return apiError(
      `file too large (${Math.round(file.size / 1024)} KB; max 5 MB)`,
      413
    );
  }

  // Belt-and-suspenders behind the client's filename nudge. Require
  // BOTH the .docx extension AND either the canonical docx mime OR a
  // generic octet-stream (Safari / File Manager paste sometimes strip
  // the mime entirely — tightening to DOCX_MIME only would block
  // legit uploads). Mammoth downstream is the real source of truth
  // on actual parseability.
  const mime = file.type || 'application/octet-stream';
  const filenameIsDocx = file.name.toLowerCase().endsWith('.docx');
  const mimeIsCompatible = mime === DOCX_MIME || mime === 'application/octet-stream';
  if (!filenameIsDocx || !mimeIsCompatible) {
    return apiError('Only .docx files are supported.', 400);
  }

  const arrayBuf = await file.arrayBuffer();
  const buffer = Buffer.from(arrayBuf);

  let extractedText: string;
  try {
    const result = await mammoth.extractRawText({ buffer });
    extractedText = result.value.trim();
  } catch (err) {
    // Mammoth throws on zip corruption or non-docx input. Treat as
    // client validation failure, not 500. redactPhi just in case the
    // error message echoes filename bytes.
    return NextResponse.json(
      {
        error:
          'Could not read the uploaded file as a .docx. Make sure you saved from Word/Pages/Google Docs as .docx (not .doc or .odt).',
        detail: redactPhi(err instanceof Error ? err.message : String(err)),
      },
      { status: 415 }
    );
  }

  if (!extractedText) {
    return apiError(
      'Template appears to be empty after parsing. Save from Word with content and try again.',
      400
    );
  }

  const tokensFound = extractTokens(extractedText);
  const { supported: _supported, unsupported } = partitionTokens(tokensFound);

  // MinIO object key is decoupled from the DB row ID — we generate a
  // random UUID segment here so the PUT can run BEFORE the Prisma
  // create. Orphan objects (MinIO put succeeded, Prisma create failed)
  // are rare and will be swept by the future T-M12-style template
  // orphan cleanup; for POC we accept the near-zero orphan risk in
  // exchange for not needing a 2-phase create+update.
  const minioKey = buildTemplateObjectKey(userId, randomUUID());
  try {
    await putTemplate(minioKey, buffer);
  } catch (err) {
    console.error(
      '[api:templates:upload] MinIO write failed:',
      redactPhi(err instanceof Error ? err.message : err)
    );
    return apiError(
      'Could not store the template. Try again in a minute.',
      502
    );
  }

  const row = await prisma.transcribeTemplate.create({
    data: {
      userId,
      name,
      originalFileName: file.name || `${name}.docx`,
      minioKey,
      extractedText,
      tokens: tokensFound,
    },
    select: {
      id: true,
      name: true,
      originalFileName: true,
      tokens: true,
      createdAt: true,
    },
  });

  log.info('api:templates:upload', 'template uploaded', {
    userId,
    templateId: row.id,
    tokenCount: tokensFound.length,
    unsupportedCount: unsupported.length,
  });

  return NextResponse.json(
    {
      ...row,
      unsupportedTokens: unsupported,
    },
    { status: 201 }
  );
});

// ---------------------------------------------------------------------------
// GET /api/templates — list caller's non-deleted templates
// Response: 200 { templates: [{ id, name, originalFileName, tokens,
//                               createdAt, updatedAt }] }
// ---------------------------------------------------------------------------

export const GET = withApiHandler('api:templates:list', async () => {
  const session = await auth();
  const userId = session?.user?.id;
  if (!userId) return apiError('unauthorized', 401);

  const templates = await prisma.transcribeTemplate.findMany({
    where: { userId, deletedAt: null },
    orderBy: { createdAt: 'desc' },
    select: {
      id: true,
      name: true,
      originalFileName: true,
      tokens: true,
      createdAt: true,
      updatedAt: true,
    },
  });

  return NextResponse.json({ templates }, { status: 200 });
});
