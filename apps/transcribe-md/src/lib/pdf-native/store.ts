// ============================================================================
// PDF native canvas storage (feat/pdf-native-fill). The doctor's BLANK template
// PDF (labels only, no patient data → PHI-safe) is stored under the template
// artifacts bucket at certify time; the export reads it back as the verbatim
// canvas. Anchors + the certified flag live on the template's styleProfile JSONB
// (set by certify, read by export — no review round-trip).
// ============================================================================
import { getMinio } from '@/lib/minio';
import { resolveTemplateTwinBucket } from '@/lib/template-twin/storage';

const canvasKey = (templateId: string): string => `pdf-native/${templateId}/canvas.pdf`;

/** Provision the artifacts bucket if absent (idempotent). */
export async function ensureArtifactBucket(): Promise<string> {
  const bucket = resolveTemplateTwinBucket();
  const client = getMinio();
  if (!(await client.bucketExists(bucket))) {
    await client.makeBucket(bucket, '');
  }
  return bucket;
}

/** Store the blank template PDF as the export canvas. */
export async function putTemplateCanvas(templateId: string, bytes: Buffer): Promise<void> {
  const bucket = await ensureArtifactBucket();
  await getMinio().putObject(bucket, canvasKey(templateId), bytes, bytes.length, {
    'Content-Type': 'application/pdf',
  });
}

/** Read the stored canvas back, or null when not present. */
export async function getTemplateCanvas(templateId: string): Promise<Buffer | null> {
  const bucket = resolveTemplateTwinBucket();
  try {
    const stream = await getMinio().getObject(bucket, canvasKey(templateId));
    const chunks: Buffer[] = [];
    for await (const chunk of stream) chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    return Buffer.concat(chunks);
  } catch {
    return null;
  }
}
