// ============================================================================
// apps/transcribe-md — MinIO (S3-compatible) client (T-M4)
// ----------------------------------------------------------------------------
// One bucket per product — transcribe-md-audio — separate from Scribe's
// scribe-audio so the retention policies can diverge later (spec says
// clinic-configurable retention lives in Practice, and solo users have
// their own synthetic Practice anyway).
//
// Audio arrives via the upload API route (streams file → PUT here) and
// leaves via the worker's Layer 1 (downloadAudio → Deepgram batch).
// ============================================================================

import { Client as MinioClient, type BucketItemStat } from 'minio';
import type { Readable } from 'node:stream';

/** Shape of each item the MinIO listObjects stream yields. Named in the
 *  SDK but not conveniently exported — re-declared here so callers
 *  don't have to fish it out of the transitive types. */
export interface MinioObjectInfo {
  name: string;
  lastModified?: Date;
  size?: number;
  etag?: string;
}

const bucket =
  process.env.TRANSCRIBE_MD_MINIO_BUCKET?.trim() || 'transcribe-md-audio';
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

/** Idempotent — creates the bucket if it doesn't exist. Called from the
 *  upload route and at worker startup. */
export async function ensureBucket(): Promise<void> {
  if (bucketReady) return;
  const client = getMinio();
  const exists = await client.bucketExists(bucket).catch(() => false);
  if (!exists) {
    // Region blank = MinIO default. No public policy — reads always
    // go through the app with an authed session.
    await client.makeBucket(bucket, '');
  }
  bucketReady = true;
}

/** Stream audio bytes FROM the browser's upload request INTO MinIO. The
 *  upload route calls this so the app never buffers the whole file. */
export async function putAudioStream(
  objectKey: string,
  stream: Readable | Buffer,
  sizeBytes: number,
  mimeType: string
): Promise<void> {
  await ensureBucket();
  const client = getMinio();
  await client.putObject(bucket, objectKey, stream, sizeBytes, {
    'Content-Type': mimeType,
  });
}

/** Worker path — read the audio back out as a Buffer. For 500MB ceilings
 *  this stays under Node's default 2GB buffer limit with a wide margin;
 *  we'd want a streaming variant for arbitrarily-large files but that's
 *  out of T-M4 scope. */
export async function downloadAudio(objectKey: string): Promise<Buffer> {
  await ensureBucket();
  const client = getMinio();
  const stream = await client.getObject(bucket, objectKey);
  const chunks: Buffer[] = [];
  for await (const chunk of stream) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks);
}

export async function statAudio(
  objectKey: string
): Promise<BucketItemStat | null> {
  try {
    const client = getMinio();
    return await client.statObject(bucket, objectKey);
  } catch {
    return null;
  }
}

/** List every object under the transcribe-md audio bucket. Used by the
 *  T-M12 orphan-cleanup sweep. Paginates internally — the MinIO SDK's
 *  listObjects() returns an async stream that yields all matching
 *  items; we collect into an array. For the current scale (hundreds to
 *  low thousands of audio files) an in-memory array is fine; past
 *  ~100k objects the caller should switch to streaming iteration. */
export async function listAllAudioObjects(): Promise<MinioObjectInfo[]> {
  await ensureBucket();
  const client = getMinio();
  const stream = client.listObjects(bucket, '', true);
  const out: MinioObjectInfo[] = [];
  for await (const item of stream) {
    if (typeof item.name !== 'string' || item.name.length === 0) continue;
    out.push({
      name: item.name,
      lastModified: item.lastModified,
      size: item.size,
      etag: item.etag,
    });
  }
  return out;
}

/** Delete one audio object. Idempotent — MinIO's removeObject returns
 *  success even if the key doesn't exist. Callers should only invoke
 *  this after confirming the key has no DB reference. */
export async function deleteAudioObject(objectKey: string): Promise<void> {
  await ensureBucket();
  const client = getMinio();
  await client.removeObject(bucket, objectKey);
}

/** Sanitize user-provided filenames before including in the object key. */
export function sanitizeFilename(name: string): string {
  // Strip path, keep only ASCII alphanumerics + a few safe separators,
  // limit length. Extension preserved when present.
  const base = name.split(/[\\/]/).pop() ?? 'audio';
  return base.replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 80) || 'audio';
}

/** Deterministic object key scheme: {userId}/{visitId}/{ts}-{name}. */
export function buildAudioObjectKey(
  userId: string,
  visitId: string,
  filename: string
): string {
  const safe = sanitizeFilename(filename);
  return `${userId}/${visitId}/${Date.now()}-${safe}`;
}

export const TRANSCRIBE_MD_BUCKET = bucket;
