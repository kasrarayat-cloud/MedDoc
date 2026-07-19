import { randomUUID } from 'node:crypto';

export const DOCX_MIME_TYPE =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

export const DEFAULT_TEMPLATE_TWIN_BUCKET =
  'transcribe-md-template-artifacts';

export type TemplateTwinArtifactKind = 'quarantine' | 'source' | 'output';

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

export interface CreateQuarantineArtifactKeyInput {
  practiceId: string;
  lineageId: string;
  lineageVersion: number;
  sha256: string;
  /** Test seam only. Production callers leave this unset and receive a UUID. */
  idFactory?: () => string;
}

export function createQuarantineArtifactKey({
  practiceId,
  lineageId,
  lineageVersion,
  sha256,
  idFactory = randomUUID,
}: CreateQuarantineArtifactKeyInput): string {
  if (!Number.isSafeInteger(lineageVersion) || lineageVersion < 1) {
    throw new InvalidTemplateTwinStorageInputError(
      'lineageVersion must be a positive integer.'
    );
  }
  const prefix = templateTwinTenantPrefix(practiceId);
  const lineage = assertOpaqueId(lineageId, 'lineageId');
  const objectId = assertOpaqueId(idFactory(), 'artifactId');
  const digest = assertSha256(sha256);
  return `${prefix}/quarantine/${lineage}/v${lineageVersion}/${objectId}/${digest}.docx`;
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
