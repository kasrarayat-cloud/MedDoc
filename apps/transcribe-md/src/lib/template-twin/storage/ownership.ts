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
  // ⚠️ LENGTH IS PER-CATEGORY, NOT GLOBAL, AND THIS USED TO BE A FLAT `!== 8`.
  // `sources` and `outputs` carry a lineage+version or a visit+manifest, so they
  // are eight segments. An `upload` has NEITHER — no template exists yet, which
  // is the whole reason that kind was added — so it is SEVEN, and a flat check
  // rejected every legitimately generated upload key.
  //
  // The alternative was padding the upload key with a segment that means
  // nothing, to satisfy a number. A key shape should describe what the thing IS;
  // inventing a `v1` for something with no versions would have made the key lie
  // to every future reader in order to keep one comparison simple.
  const expectedLength = parts[3] === 'uploads' ? 7 : 8;
  if (
    parts.length !== expectedLength ||
    parts[0] !== 'practices' ||
    parts[2] !== 'template-twin'
  ) {
    return null;
  }

  try {
    const practiceId = assertOpaqueId(parts[1] ?? '', 'practiceId');
    const category = parts[3];
    const filename = parts[expectedLength - 1] ?? '';
    if (!filename.endsWith('.docx')) return null;
    const sha256 = assertSha256(filename.slice(0, -5));

    if (category === 'sources') {
      assertOpaqueId(parts[4] ?? '', 'lineageId');
      if (!/^v[1-9][0-9]*$/.test(parts[5] ?? '')) return null;
      assertOpaqueId(parts[6] ?? '', 'artifactId');
      return { practiceId, kind: 'source', sha256 };
    }

    if (category === 'uploads') {
      // Both id segments are the uploadId — an upload IS its own artifact, so
      // a second random id would suggest a grouping that does not exist.
      // Requiring them EQUAL is what stops a crafted key smuggling an
      // unrelated id through the second position.
      const uploadId = assertOpaqueId(parts[4] ?? '', 'uploadId');
      if (parts[5] !== uploadId) return null;
      return { practiceId, kind: 'upload', sha256 };
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
