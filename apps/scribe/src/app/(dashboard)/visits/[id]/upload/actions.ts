'use server';

import { z } from 'zod';
import prisma from '@meddoc/db';
import { getSession } from '@/lib/auth';
import { tenantScope } from '@meddoc/auth';
import { presignUpload } from '@/lib/minio';

const PresignInputSchema = z.object({
  visitId: z.string().min(1),
  fileName: z.string().min(1).max(240),
  contentType: z
    .string()
    .regex(/^(audio|video)\//i)
    .max(120),
});

export interface PresignResult {
  uploadUrl: string;
  objectKey: string;
}

/**
 * Returns a presigned PUT URL for the visit's audio upload. Browser PUTs
 * directly to MinIO (spec §10 — do NOT proxy audio through the app).
 */
export async function createPresignedUploadUrlAction(input: {
  visitId: string;
  fileName: string;
  contentType: string;
}): Promise<PresignResult> {
  const session = await getSession();
  if (!session) throw new Error('Not authenticated.');

  const parsed = PresignInputSchema.safeParse(input);
  if (!parsed.success) {
    throw new Error(parsed.error.issues.map((i) => i.message).join(' '));
  }

  const visit = await prisma.scribeVisit.findFirst({
    where: {
      id: parsed.data.visitId,
      ...tenantScope(session),
      deletedAt: null,
    },
    select: { id: true, mode: true, status: true },
  });
  if (!visit) throw new Error('Visit not found.');
  if (visit.mode !== 'BATCH') {
    throw new Error('This visit is not in upload mode.');
  }
  if (visit.status !== 'DRAFT' && visit.status !== 'UPLOADING') {
    throw new Error(`Visit is in status ${visit.status}; cannot upload.`);
  }

  // Object key format: <practiceId>/<visitId>/<random>-<filename>
  // Practice prefix so ops can audit scope at the MinIO level.
  const slug = parsed.data.fileName.replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 80);
  const rand = Math.random().toString(36).slice(2, 10);
  const objectKey = `${session.user.practiceId}/${visit.id}/${rand}-${slug}`;

  const uploadUrl = await presignUpload(objectKey);

  // Persist the object key eagerly so even a dropped browser can later
  // resume by re-enqueueing the transcribe job.
  await prisma.scribeVisit.update({
    where: { id: visit.id },
    data: {
      status: 'UPLOADING',
      audioObjectKey: objectKey,
      sourceFileName: parsed.data.fileName,
    },
  });

  return { uploadUrl, objectKey };
}
