// ============================================================================
// apps/scribe — MinIO (S3-compatible) client
// ----------------------------------------------------------------------------
// Browsers upload audio directly to MinIO via presigned URLs (spec §10 —
// do NOT proxy through the app server). The worker downloads audio by
// object key when transcribe_batch fires. Bucket name + credentials come
// from env; ensureBucket() is called lazily on first use and is
// idempotent.
// ============================================================================

import { Client as MinioClient } from 'minio';

const bucket = process.env.MINIO_BUCKET?.trim() || 'scribe-audio';
const endpoint = process.env.MINIO_ENDPOINT?.trim() || 'minio';
const [host, portStr] = endpoint.split(':');
const port = portStr ? Number.parseInt(portStr, 10) : 9000;
const useSSL = (process.env.MINIO_USE_SSL ?? 'false').toLowerCase() === 'true';

let clientSingleton: MinioClient | null = null;
let bucketReady = false;

export function getMinio(): MinioClient {
  if (clientSingleton) return clientSingleton;
  const accessKey = process.env.MINIO_ACCESS_KEY;
  const secretKey = process.env.MINIO_SECRET_KEY;
  if (!accessKey || !secretKey) {
    throw new Error('MINIO_ACCESS_KEY / MINIO_SECRET_KEY are not set.');
  }
  clientSingleton = new MinioClient({
    endPoint: host,
    port,
    useSSL,
    accessKey,
    secretKey,
  });
  return clientSingleton;
}

export async function ensureBucket(): Promise<void> {
  if (bucketReady) return;
  const client = getMinio();
  const exists = await client.bucketExists(bucket).catch(() => false);
  if (!exists) {
    await client.makeBucket(bucket);
  }
  bucketReady = true;
}

export const SCRIBE_BUCKET = bucket;

/**
 * Presigned PUT URL for direct browser upload. 10 min expiry — long
 * enough for a slow 2hr audio upload, short enough that a leaked URL
 * is mostly harmless.
 */
export async function presignUpload(
  objectKey: string,
  expirySeconds = 600
): Promise<string> {
  await ensureBucket();
  return getMinio().presignedPutObject(bucket, objectKey, expirySeconds);
}

export async function downloadObject(objectKey: string): Promise<Buffer> {
  const client = getMinio();
  const stream = await client.getObject(bucket, objectKey);
  const chunks: Buffer[] = [];
  for await (const chunk of stream) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks);
}

export async function statObject(objectKey: string): Promise<{ size: number } | null> {
  try {
    const client = getMinio();
    const stat = await client.statObject(bucket, objectKey);
    return { size: stat.size };
  } catch {
    return null;
  }
}
