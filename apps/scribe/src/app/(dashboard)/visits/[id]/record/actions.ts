'use server';

import { z } from 'zod';
import prisma from '@meddoc/db';
import { getSession } from '@/lib/auth';
import { tenantScope } from '@meddoc/auth';
import { presignUpload } from '@/lib/minio';

/**
 * Presign a PUT URL so the browser can upload the live-recording audio
 * blob directly to MinIO after the visit ends. Called by RecordClient
 * during the end-of-visit flow.
 *
 * Mirrors createPresignedUploadUrlAction (batch) but:
 *   - Requires mode=LIVE
 *   - Requires status=RECORDING (WS_CONNECTED already ran)
 *   - Hard-codes the sourceFileName to live-recording.webm (browser
 *     MediaRecorder always outputs audio/webm;codecs=opus per spec §9 D2)
 */

const LiveUploadInputSchema = z.object({
  visitId: z.string().min(1),
});

export interface LivePresignResult {
  uploadUrl: string;
  objectKey: string;
  sourceFileName: string;
}

export async function presignLiveUploadAction(input: {
  visitId: string;
}): Promise<LivePresignResult> {
  const session = await getSession();
  if (!session) throw new Error('Not authenticated.');

  const parsed = LiveUploadInputSchema.safeParse(input);
  if (!parsed.success) {
    throw new Error(parsed.error.issues.map((i) => i.message).join(' '));
  }

  const visit = await prisma.scribeVisit.findFirst({
    where: {
      id: parsed.data.visitId,
      ...tenantScope(session),
      deletedAt: null,
    },
    select: { id: true, mode: true, status: true, userId: true },
  });
  if (!visit) throw new Error('Visit not found.');
  if (visit.userId !== session.user.id) throw new Error('Visit not found.');
  if (visit.mode !== 'LIVE') {
    throw new Error('This visit is not in live mode.');
  }
  if (visit.status !== 'RECORDING') {
    throw new Error(`Visit is ${visit.status}; cannot upload live audio.`);
  }

  const sourceFileName = 'live-recording.webm';
  const rand = Math.random().toString(36).slice(2, 10);
  const objectKey = `${session.user.practiceId}/${visit.id}/${rand}-${sourceFileName}`;

  const uploadUrl = await presignUpload(objectKey);

  // Persist eagerly so even if the browser drops after the PUT, the
  // /live-complete route (or a retry) can find the key on the visit row.
  await prisma.scribeVisit.update({
    where: { id: visit.id },
    data: {
      audioObjectKey: objectKey,
      sourceFileName,
    },
  });

  return { uploadUrl, objectKey, sourceFileName };
}
