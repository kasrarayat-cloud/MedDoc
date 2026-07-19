import {
  assertOpaqueId,
  assertSha256,
  type TemplateTwinArtifactKind,
} from './keys';

export interface ParsedTemplateTwinArtifactKey {
  practiceId: string;
  kind: TemplateTwinArtifactKind;
  sha256: string;
}

/**
 * Parse only keys emitted by keys.ts. Any additional segment, path traversal,
 * filename, or malformed digest is rejected rather than normalized.
 */
export function parseTemplateTwinArtifactKey(
  objectKey: string
): ParsedTemplateTwinArtifactKey | null {
  if (
    !objectKey ||
    objectKey.startsWith('/') ||
    objectKey.endsWith('/') ||
    objectKey.includes('\\')
  ) {
    return null;
  }

  const parts = objectKey.split('/');
  if (parts.some((part) => part === '.' || part === '..')) return null;
  if (
    parts.length !== 8 ||
    parts[0] !== 'practices' ||
    parts[2] !== 'template-twin'
  ) {
    return null;
  }

  try {
    const practiceId = assertOpaqueId(parts[1] ?? '', 'practiceId');
    const category = parts[3];
    const filename = parts[7] ?? '';
    if (!filename.endsWith('.docx')) return null;
    const sha256 = assertSha256(filename.slice(0, -5));

    if (category === 'sources') {
      assertOpaqueId(parts[4] ?? '', 'lineageId');
      if (!/^v[1-9][0-9]*$/.test(parts[5] ?? '')) return null;
      assertOpaqueId(parts[6] ?? '', 'artifactId');
      return { practiceId, kind: 'source', sha256 };
    }

    if (category === 'quarantine') {
      assertOpaqueId(parts[4] ?? '', 'lineageId');
      if (!/^v[1-9][0-9]*$/.test(parts[5] ?? '')) return null;
      assertOpaqueId(parts[6] ?? '', 'artifactId');
      return { practiceId, kind: 'quarantine', sha256 };
    }

    if (category === 'candidates') {
      assertOpaqueId(parts[4] ?? '', 'candidateId');
      if (!/^v[1-9][0-9]*$/.test(parts[5] ?? '')) return null;
      assertOpaqueId(parts[6] ?? '', 'artifactId');
      return { practiceId, kind: 'candidate', sha256 };
    }

    if (category === 'outputs') {
      assertOpaqueId(parts[4] ?? '', 'visitId');
      assertSha256(parts[5] ?? '', 'manifestSha256');
      assertOpaqueId(parts[6] ?? '', 'artifactId');
      return { practiceId, kind: 'output', sha256 };
    }
  } catch {
    return null;
  }

  return null;
}

export function isTenantOwnedArtifactKey(input: {
  objectKey: string;
  practiceId: string;
  kind?: TemplateTwinArtifactKind;
}): boolean {
  const parsed = parseTemplateTwinArtifactKey(input.objectKey);
  if (!parsed) return false;
  if (parsed.practiceId !== input.practiceId) return false;
  return input.kind === undefined || parsed.kind === input.kind;
}

export class TemplateTwinArtifactNotFoundError extends Error {
  readonly code = 'TEMPLATE_TWIN_ARTIFACT_NOT_FOUND';

  constructor() {
    // Deliberately indistinguishable from a missing record. Callers can map this
    // to 404 without revealing that another tenant owns a supplied object key.
    super('Template Twin artifact not found.');
    this.name = 'TemplateTwinArtifactNotFoundError';
  }
}

export function assertTenantOwnedArtifactKey(input: {
  objectKey: string;
  practiceId: string;
  kind?: TemplateTwinArtifactKind;
}): ParsedTemplateTwinArtifactKey {
  const parsed = parseTemplateTwinArtifactKey(input.objectKey);
  if (
    !parsed ||
    parsed.practiceId !== input.practiceId ||
    (input.kind !== undefined && parsed.kind !== input.kind)
  ) {
    throw new TemplateTwinArtifactNotFoundError();
  }
  return parsed;
}

export interface TemplateTwinActor {
  userId: string;
  practiceId: string;
}

export interface TemplateTwinOwnedRecord {
  practiceId: string;
  /** NoteTemplate doctor owner, when the record has one. */
  doctorId?: string | null;
  /** Source-artifact uploader, when the record has one. */
  uploadedById?: string | null;
}

/** Both tenant and physician ownership are required for v1 mutations. */
export function isTemplateTwinRecordOwner(
  actor: TemplateTwinActor,
  record: TemplateTwinOwnedRecord
): boolean {
  if (actor.practiceId !== record.practiceId) return false;
  const ownerId = record.doctorId ?? record.uploadedById ?? null;
  return ownerId !== null && ownerId === actor.userId;
}

export function assertTemplateTwinRecordOwner(
  actor: TemplateTwinActor,
  record: TemplateTwinOwnedRecord
): void {
  if (!isTemplateTwinRecordOwner(actor, record)) {
    throw new TemplateTwinArtifactNotFoundError();
  }
}
