import { randomUUID } from 'node:crypto';

export const DOCX_MIME_TYPE =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

export const DEFAULT_TEMPLATE_TWIN_BUCKET =
  'transcribe-md-template-artifacts';

/**
 * ⚠️ `upload` IS NOT A TWIN ARTIFACT, AND IT LIVES HERE ANYWAY — deliberately.
 *
 * RC-2 (ruling #106(b)) keeps the doctor's original `.docx` from the moment it
 * is received, BEFORE extraction, so a failed parse can no longer destroy the
 * only copy. At that moment there is no template, no lineage and no version —
 * the row is created later — so it cannot use the `source` key shape, which
 * asserts all three.
 *
 * It reuses this module rather than growing a parallel store because the parts
 * that matter are identical: the same private bucket, the same practice-scoped
 * prefix, the same tenant-ownership parsing, the same digest-verified put. A
 * second store would drift from this one on the day either is fixed.
 *
 * ⚠️ AND IT IS A DISTINCT CATEGORY, NOT A SYNTHETIC LINEAGE. Filing pre-template
 * bytes under `sources/` with an invented lineage id would make them
 * indistinguishable from real twin sources to every sweep and ownership check
 * that reads this namespace — a category error that is cheap to avoid now and
 * expensive to unpick later.
 */
export type TemplateTwinArtifactKind = 'source' | 'output' | 'upload';

const SAFE_OPAQUE_ID = /^[A-Za-z0-9_-]{1,128}$/;
const SHA256 = /^[a-f0-9]{64}$/;
const S3_BUCKET = /^(?=.{3,63}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/;

export class InvalidTemplateTwinStorageInputError extends Error {
  readonly code = 'TEMPLATE_TWIN_STORAGE_INPUT_INVALID';

  constructor(message = 'Invalid Template Twin artifact metadata.') {
    super(message);
    this.name = 'InvalidTemplateTwinStorageInputError';
  }
}

export function assertOpaqueId(value: string, fieldName: string): string {
  if (!SAFE_OPAQUE_ID.test(value)) {
    throw new InvalidTemplateTwinStorageInputError(
      `${fieldName} must be an opaque server-generated identifier.`
    );
  }
  return value;
}

export function assertSha256(value: string, fieldName = 'sha256'): string {
  if (!SHA256.test(value)) {
    throw new InvalidTemplateTwinStorageInputError(
      `${fieldName} must be a lowercase SHA-256 digest.`
    );
  }
  return value;
}

export function resolveTemplateTwinBucket(
  env: Readonly<Record<string, string | undefined>> = process.env
): string {
  const bucket =
    env.TRANSCRIBE_MD_TEMPLATE_BUCKET?.trim() ||
    DEFAULT_TEMPLATE_TWIN_BUCKET;
  if (!S3_BUCKET.test(bucket) || bucket.includes('..')) {
    throw new InvalidTemplateTwinStorageInputError(
      'TRANSCRIBE_MD_TEMPLATE_BUCKET is not a valid private bucket name.'
    );
  }
  return bucket;
}

export function templateTwinTenantPrefix(practiceId: string): string {
  return `practices/${assertOpaqueId(practiceId, 'practiceId')}/template-twin`;
}

export interface CreateSourceArtifactKeyInput {
  practiceId: string;
  lineageId: string;
  templateVersion: number;
  sha256: string;
  /** Test seam only. Production callers leave this unset and receive a UUID. */
  idFactory?: () => string;
}

export function createSourceArtifactKey({
  practiceId,
  lineageId,
  templateVersion,
  sha256,
  idFactory = randomUUID,
}: CreateSourceArtifactKeyInput): string {
  if (!Number.isSafeInteger(templateVersion) || templateVersion < 1) {
    throw new InvalidTemplateTwinStorageInputError(
      'templateVersion must be a positive integer.'
    );
  }
  const prefix = templateTwinTenantPrefix(practiceId);
  const lineage = assertOpaqueId(lineageId, 'lineageId');
  const objectId = assertOpaqueId(idFactory(), 'artifactId');
  const digest = assertSha256(sha256);
  return `${prefix}/sources/${lineage}/v${templateVersion}/${objectId}/${digest}.docx`;
}

export interface CreateUploadArtifactKeyInput {
  practiceId: string;
  /** Opaque id minted per upload attempt. NOT a template id — no template
   *  exists yet, which is the entire reason this key shape is needed. */
  uploadId: string;
  sha256: string;
}

/**
 * `practices/<practiceId>/template-twin/uploads/<uploadId>/<sha256>.docx`
 *
 * ⚠️ SEVEN segments, not eight — and an earlier version of this comment claimed
 * eight while the code produced seven, which is exactly the defect it caused.
 * `parseTemplateTwinArtifactKey` rejected EVERY upload key, so nothing could
 * have been bound through the tenant guard. The comment asserted an invariant
 * the line below it did not have, and no test compared them.
 *
 * Seven is correct: `sources` carries a lineage AND a version, `outputs` a visit
 * AND a manifest digest, and an upload has NEITHER — no template exists yet,
 * which is the entire reason this kind was added. The parser now takes its
 * length per category rather than flatly.
 *
 * The `uploadId` is repeated in the artifact-id position because an upload IS
 * its own artifact; a second random id would suggest a grouping that does not
 * exist. The parser REQUIRES the two to be equal, which is what stops a crafted
 * key smuggling an unrelated id through the second position.
 *
 * ⚠️ Round-tripped against the parser for all three kinds by
 * `ownership.test.ts` — a key shape and its parser are one contract in two
 * files, and this pair has already drifted once.
 */
export function createUploadArtifactKey({
  practiceId,
  uploadId,
  sha256,
}: CreateUploadArtifactKeyInput): string {
  const prefix = templateTwinTenantPrefix(practiceId);
  const upload = assertOpaqueId(uploadId, 'uploadId');
  const digest = assertSha256(sha256);
  return `${prefix}/uploads/${upload}/${upload}/${digest}.docx`;
}

export interface CreateOutputArtifactKeyInput {
  practiceId: string;
  visitId: string;
  manifestSha256: string;
  outputSha256: string;
  /** Test seam only. Production callers leave this unset and receive a UUID. */
  idFactory?: () => string;
}

export function createOutputArtifactKey({
  practiceId,
  visitId,
  manifestSha256,
  outputSha256,
  idFactory = randomUUID,
}: CreateOutputArtifactKeyInput): string {
  const prefix = templateTwinTenantPrefix(practiceId);
  const visit = assertOpaqueId(visitId, 'visitId');
  const manifest = assertSha256(manifestSha256, 'manifestSha256');
  const objectId = assertOpaqueId(idFactory(), 'artifactId');
  const output = assertSha256(outputSha256, 'outputSha256');
  return `${prefix}/outputs/${visit}/${manifest}/${objectId}/${output}.docx`;
}
