import { Prisma } from '@prisma/client';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  audit: vi.fn(),
  certificationCreate: vi.fn(),
  compiledCreate: vi.fn(),
  compiledFindUnique: vi.fn(),
  compiledUpdate: vi.fn(),
  extractDictation: vi.fn(),
  extractText: vi.fn(),
  fieldUpdateMany: vi.fn(),
  mappingUpdate: vi.fn(),
  modelComplete: vi.fn(),
  noteCreate: vi.fn(),
  noteFindFirst: vi.fn(),
  noteUpdate: vi.fn(),
  noteUpdateMany: vi.fn(),
  sourceCreate: vi.fn(),
  transaction: vi.fn(),
  ledgerUpdate: vi.fn(),
  ledgerFind: vi.fn(),
  outboxCreate: vi.fn(),
}));

vi.mock('@meddoc/ai', () => ({
  delimiterSystemSuffix: () => '',
  modelClient: { complete: mocks.modelComplete },
  wrapAsData: (value: string) => ({
    wrapped: value,
    injectionAttemptDetected: false,
  }),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    $transaction: mocks.transaction,
    noteTemplate: {
      create: mocks.noteCreate,
      findFirst: mocks.noteFindFirst,
      update: mocks.noteUpdate,
      updateMany: mocks.noteUpdateMany,
    },
    templateTwinCertification: { create: mocks.certificationCreate },
    templateTwinCompiledVersion: {
      create: mocks.compiledCreate,
      findUnique: mocks.compiledFindUnique,
      update: mocks.compiledUpdate,
    },
    templateTwinFieldDefinition: { updateMany: mocks.fieldUpdateMany },
    templateTwinSemanticMapping: { update: mocks.mappingUpdate },
    templateTwinSourceArtifact: { create: mocks.sourceCreate },
    templateTwinObjectLedger: {
      updateMany: mocks.ledgerUpdate,
      findUnique: mocks.ledgerFind,
    },
    templateTwinAuditOutbox: { create: mocks.outboxCreate },
  },
  prisma: {
    $transaction: mocks.transaction,
  },
}));

vi.mock('@/lib/audit', () => ({ logAudit: mocks.audit }));
vi.mock('@/worker/layers/03-extract-entities', () => ({
  extractTemplateTwinDictationEntities: mocks.extractDictation,
  extractTemplateTwinTextEntities: mocks.extractText,
}));

import {
  certifyAndActivateTemplateTwin,
  updateTemplateTwinMappings,
} from '../certification-lifecycle';
import { createTemplateTwinDraft } from '../create-draft';
import type { SemanticMapping } from '../ir';
import { templateTwinMappingsSha256 } from '../mapping-hash';
import {
  createTemplateTwinArtifactStore,
  type TemplateTwinObjectClient,
} from '../storage';
import { runTemplateTwinSyntheticTest } from '../synthetic-test';
import { readTemplateTwinWorkspace } from '../workspace-read';
import { TEMPLATE_TWIN_QA_STORAGE_EXCEPTION_ATTESTATION } from '../storage/readiness';
import {
  buildTemplateTwinIntegrationFixture,
  SYNTHETIC_CONTEXT,
  SYNTHETIC_ENTITIES,
} from './integration-fixture';

const ACTOR = {
  userId: 'doctor-stateful-synthetic',
  userEmail: 'stateful-doctor@synthetic.test',
  practiceId: 'practice-stateful-synthetic',
};
const PRIOR_TEMPLATE_ID = 'prior-structured-template';

interface MemoryMapping {
  id: string;
  fieldDefinitionId: string;
  clinicalConcept: string | null;
  expectedDataType: string;
  polarityBehavior: string;
  temporality: string | null;
  laterality: string | null;
  unitPolicy: string | null;
  approvedSynonyms: unknown;
  required: boolean;
  blankPolicy: string;
  unknownPolicy: string;
  practiceDefault: string | null;
  mappingStatus: string;
  proposedByModel: string | null;
  approvedById: string | null;
  approvedAt: Date | null;
}

interface MemoryField {
  id: string;
  compiledVersionId: string;
  fieldId: string;
  displayOrder: number;
  originalLabel: string;
  fieldKind: string;
  allowedOptions: unknown;
  rendererBinding: unknown;
  detectionStatus: string;
  clinicallyMaterial: boolean;
  criticality: string;
  required: boolean;
  mapping: MemoryMapping;
}

interface MemorySource {
  id: string;
  practiceId: string;
  createdById: string;
  lineageId: string;
  lineageVersion: number;
  objectKey: string;
  objectVersionId: string;
  objectEtag: string;
  sha256: string;
  mimeType: string;
  sizeBytes: number;
  validationStatus: string;
  rejectionCodes: string[];
}

interface MemoryCertification {
  id: string;
  compiledVersionId: string;
  certifiedById: string;
  compiledStructureSha256: string;
  approvedMappingsSha256: string;
  syntheticTestManifest: unknown;
  testOutputObjectKey: string;
  testOutputVersionId: string;
  testOutputEtag: string;
  testOutputSha256: string;
  certifiedAt: Date;
}

interface MemoryCompiled {
  id: string;
  sourceArtifactId: string;
  noteTemplateId: string;
  compilerVersion: string;
  irSchemaVersion: number;
  compiledAt: Date;
  compiledDocumentIr: unknown;
  unsupportedElements: unknown;
  structureSha256: string;
  staticContentSha256: string;
  certificationStatus: string;
  blockingUnsupportedCount: number;
  latestSyntheticTestManifest: unknown;
  latestTestMappingsSha256: string | null;
  latestTestOutputObjectKey: string | null;
  latestTestOutputVersionId: string | null;
  latestTestOutputEtag: string | null;
  latestTestOutputSha256: string | null;
  latestTestStaticContentSha256: string | null;
  latestTestRoundTrip: unknown;
  latestTestVerifiedAt: Date | null;
  sourceArtifact: MemorySource;
  fields: MemoryField[];
  certification: MemoryCertification | null;
}

interface MemoryTemplate {
  id: string;
  doctorId: string;
  name: string;
  encounterType: string | null;
  sections: unknown;
  styleProfile: unknown;
  specialtyBaseline: string | null;
  version: number;
  status: string;
  isSystemDefault: boolean;
  lineageId: string;
  parentVersionId: string | null;
  templateKind: string;
  templateTwinCompiledVersion: MemoryCompiled | null;
}

interface MemoryDatabase {
  templates: Map<string, MemoryTemplate>;
  sources: Map<string, MemorySource>;
  compiled: Map<string, MemoryCompiled>;
  certifications: Map<string, MemoryCertification>;
}

interface StoredObject {
  bytes: Buffer;
  metadata: Record<string, string>;
  versionId: string;
  etag: string;
}

let database: MemoryDatabase;

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Expected synthetic Prisma record');
  }
  return value as Record<string, unknown>;
}

function nullableDatabaseValue(value: unknown): unknown {
  return value === Prisma.DbNull || value === Prisma.JsonNull ? null : value;
}

function templateForQuery(args: unknown): MemoryTemplate | null | Record<string, unknown> {
  const where = record(record(args).where);
  if (where.isSystemDefault === true) {
    return {
      sections: [{ key: 'subjective', label: 'Subjective', order: 1 }],
      styleProfile: { tone: 'concise' },
      specialtyBaseline: null,
    };
  }
  const id = typeof where.id === 'string' ? where.id : null;
  const template = id ? database.templates.get(id) ?? null : null;
  if (!template) return null;
  if (typeof where.doctorId === 'string' && template.doctorId !== where.doctorId) {
    return null;
  }
  if (
    typeof where.templateKind === 'string' &&
    template.templateKind !== where.templateKind
  ) {
    return null;
  }
  if (typeof where.status === 'string' && template.status !== where.status) {
    return null;
  }
  if (typeof where.version === 'number' && template.version !== where.version) {
    return null;
  }
  return template;
}

function configureInMemoryPrisma(): void {
  mocks.noteFindFirst.mockImplementation(templateForQuery);
  mocks.noteCreate.mockImplementation(async (args: unknown) => {
    const data = record(record(args).data);
    const template = {
      ...data,
      templateTwinCompiledVersion: null,
    } as unknown as MemoryTemplate;
    database.templates.set(template.id, template);
    return template;
  });
  mocks.sourceCreate.mockImplementation(async (args: unknown) => {
    const data = record(record(args).data);
    const source = { ...data } as unknown as MemorySource;
    database.sources.set(source.id, source);
    return source;
  });
  mocks.compiledCreate.mockImplementation(async (args: unknown) => {
    const data = record(record(args).data);
    const source = database.sources.get(String(data.sourceArtifactId));
    const template = database.templates.get(String(data.noteTemplateId));
    if (!source || !template) throw new Error('Synthetic relation missing');
    const nestedFields = record(data.fields).create;
    if (!Array.isArray(nestedFields)) throw new Error('Synthetic fields missing');
    const compiledId = String(data.id);
    const fields = nestedFields.map((rawField, index): MemoryField => {
      const field = record(rawField);
      const mappingData = record(record(field.mapping).create);
      const fieldId = `field-stateful-${index + 1}`;
      const mapping: MemoryMapping = {
        ...(mappingData as unknown as Omit<MemoryMapping, 'id' | 'fieldDefinitionId'>),
        id: `mapping-stateful-${index + 1}`,
        fieldDefinitionId: fieldId,
        approvedById: null,
        approvedAt: null,
      };
      return {
        ...(field as unknown as Omit<MemoryField, 'id' | 'compiledVersionId' | 'mapping'>),
        id: fieldId,
        compiledVersionId: compiledId,
        mapping,
      };
    });
    const compiled: MemoryCompiled = {
      ...(data as unknown as Omit<
        MemoryCompiled,
        | 'compiledAt'
        | 'latestSyntheticTestManifest'
        | 'latestTestMappingsSha256'
        | 'latestTestOutputObjectKey'
        | 'latestTestOutputVersionId'
        | 'latestTestOutputEtag'
        | 'latestTestOutputSha256'
        | 'latestTestStaticContentSha256'
        | 'latestTestRoundTrip'
        | 'latestTestVerifiedAt'
        | 'sourceArtifact'
        | 'fields'
        | 'certification'
      >),
      compiledAt: new Date('2026-07-15T10:00:00.000Z'),
      latestSyntheticTestManifest: null,
      latestTestMappingsSha256: null,
      latestTestOutputObjectKey: null,
      latestTestOutputVersionId: null,
      latestTestOutputEtag: null,
      latestTestOutputSha256: null,
      latestTestStaticContentSha256: null,
      latestTestRoundTrip: null,
      latestTestVerifiedAt: null,
      sourceArtifact: source,
      fields,
      certification: null,
    };
    database.compiled.set(compiled.id, compiled);
    template.templateTwinCompiledVersion = compiled;
    return compiled;
  });
  mocks.mappingUpdate.mockImplementation(async (args: unknown) => {
    const input = record(args);
    const where = record(input.where);
    const data = record(input.data);
    for (const compiled of database.compiled.values()) {
      const field = compiled.fields.find(
        (candidate) => candidate.mapping.id === where.id,
      );
      if (!field) continue;
      Object.assign(field.mapping, data);
      return field.mapping;
    }
    throw new Error('Synthetic mapping not found');
  });
  mocks.compiledFindUnique.mockImplementation(async (args: unknown) => {
    const id = String(record(record(args).where).id);
    return database.compiled.get(id) ?? null;
  });
  mocks.compiledUpdate.mockImplementation(async (args: unknown) => {
    const input = record(args);
    const id = String(record(input.where).id);
    const compiled = database.compiled.get(id);
    if (!compiled) throw new Error('Synthetic compilation not found');
    for (const [key, value] of Object.entries(record(input.data))) {
      (compiled as unknown as Record<string, unknown>)[key] =
        nullableDatabaseValue(value);
    }
    return compiled;
  });
  mocks.fieldUpdateMany.mockImplementation(async (args: unknown) => {
    const input = record(args);
    const compiledId = String(record(input.where).compiledVersionId);
    const status = String(record(input.data).detectionStatus);
    const compiled = database.compiled.get(compiledId);
    if (!compiled) return { count: 0 };
    for (const field of compiled.fields) field.detectionStatus = status;
    return { count: compiled.fields.length };
  });
  mocks.noteUpdateMany.mockImplementation(async (args: unknown) => {
    const input = record(args);
    const where = record(input.where);
    const data = record(input.data);
    const excluded = record(where.NOT).id;
    let count = 0;
    for (const template of database.templates.values()) {
      if (
        template.doctorId === where.doctorId &&
        template.encounterType === where.encounterType &&
        template.status === where.status &&
        template.id !== excluded
      ) {
        Object.assign(template, data);
        count += 1;
      }
    }
    return { count };
  });
  mocks.noteUpdate.mockImplementation(async (args: unknown) => {
    const input = record(args);
    const id = String(record(input.where).id);
    const template = database.templates.get(id);
    if (!template) throw new Error('Synthetic template not found');
    Object.assign(template, record(input.data));
    return template;
  });
  mocks.certificationCreate.mockImplementation(async (args: unknown) => {
    const data = record(record(args).data);
    const compiled = database.compiled.get(String(data.compiledVersionId));
    if (!compiled) throw new Error('Synthetic compilation not found');
    const certification: MemoryCertification = {
      ...(data as unknown as Omit<MemoryCertification, 'id' | 'certifiedAt'>),
      id: 'certification-stateful-synthetic',
      certifiedAt: new Date('2026-07-15T12:00:00.000Z'),
    };
    compiled.certification = certification;
    database.certifications.set(certification.id, certification);
    return certification;
  });
  mocks.transaction.mockImplementation(
    async (callback: (client: unknown) => Promise<unknown>) =>
      callback({
        noteTemplate: {
          create: mocks.noteCreate,
          findFirst: mocks.noteFindFirst,
          update: mocks.noteUpdate,
          updateMany: mocks.noteUpdateMany,
        },
        templateTwinCertification: { create: mocks.certificationCreate },
        templateTwinCompiledVersion: {
          create: mocks.compiledCreate,
          findUnique: mocks.compiledFindUnique,
          update: mocks.compiledUpdate,
        },
        templateTwinFieldDefinition: { updateMany: mocks.fieldUpdateMany },
        templateTwinSemanticMapping: { update: mocks.mappingUpdate },
        templateTwinSourceArtifact: { create: mocks.sourceCreate },
        templateTwinObjectLedger: {
          updateMany: mocks.ledgerUpdate,
          findUnique: mocks.ledgerFind,
        },
        templateTwinAuditOutbox: { create: mocks.outboxCreate },
      }),
  );
}

function createInMemoryObjectClient() {
  const objects = new Map<string, StoredObject>();
  let putCount = 0;
  const missing = () => Object.assign(new Error('Synthetic object missing'), { code: 'NotFound' });
  const client: TemplateTwinObjectClient = {
    async bucketExists() {
      return true;
    },
    async getBucketPolicy() {
      throw Object.assign(new Error('Synthetic bucket has no anonymous policy'), {
        code: 'NoSuchBucketPolicy',
      });
    },
    async getBucketVersioning() {
      return { Status: 'Enabled' };
    },
    async getObjectLockConfig() {
      return { objectLockEnabled: 'Enabled' };
    },
    async statObject(_bucket, objectKey, options) {
      const item = objects.get(objectKey);
      if (!item) throw missing();
      if (options?.versionId && options.versionId !== item.versionId) {
        throw Object.assign(new Error('Synthetic object version missing'), {
          code: 'NoSuchVersion',
        });
      }
      return {
        size: item.bytes.byteLength,
        metaData: item.metadata,
        versionId: item.versionId,
        etag: item.etag,
      };
    },
    async putObject(_bucket, objectKey, bytes, _sizeBytes, metadata) {
      if (objects.has(objectKey)) {
        throw Object.assign(new Error('Synthetic put-once collision'), {
          code: 'PreconditionFailed',
          statusCode: 412,
        });
      }
      putCount += 1;
      const versionId = `synthetic-version-${putCount}`;
      const etag = `synthetic-etag-${putCount}`;
      objects.set(objectKey, {
        bytes: Buffer.from(bytes),
        metadata: { ...metadata },
        versionId,
        etag,
      });
      return { versionId, etag };
    },
    async getObject(_bucket, objectKey, options) {
      const item = objects.get(objectKey);
      if (!item) throw missing();
      if (options?.versionId && options.versionId !== item.versionId) {
        throw Object.assign(new Error('Synthetic object version missing'), {
          code: 'NoSuchVersion',
        });
      }
      return (async function* stream() {
        yield Buffer.from(item.bytes);
      })();
    },
  };
  return { client, objects, getPutCount: () => putCount };
}

function proposalMappings(mappings: readonly SemanticMapping[]) {
  return mappings.map((mapping) => ({
    ...mapping,
    status: 'recognized' as const,
    practiceDefault: null,
  }));
}

function compiledForTemplate(noteTemplateId: string): MemoryCompiled {
  const compiled = database.templates.get(noteTemplateId)?.templateTwinCompiledVersion;
  if (!compiled) throw new Error('Synthetic compiled version missing');
  return compiled;
}

beforeEach(() => {
  vi.clearAllMocks();
  database = {
    templates: new Map(),
    sources: new Map(),
    compiled: new Map(),
    certifications: new Map(),
  };
  database.templates.set(PRIOR_TEMPLATE_ID, {
    id: PRIOR_TEMPLATE_ID,
    doctorId: ACTOR.userId,
    name: 'Prior structured template',
    encounterType: 'Synthetic stateful visit',
    sections: [],
    styleProfile: {},
    specialtyBaseline: null,
    version: 1,
    status: 'active',
    isSystemDefault: false,
    lineageId: 'prior-structured-lineage',
    parentVersionId: null,
    templateKind: 'structured',
    templateTwinCompiledVersion: null,
  });
  configureInMemoryPrisma();
  mocks.audit.mockResolvedValue(undefined);
  mocks.ledgerUpdate.mockResolvedValue({ count: 1 });
  mocks.ledgerFind.mockResolvedValue(null);
  mocks.outboxCreate.mockResolvedValue({ id: 'outbox-stateful-synthetic' });
  mocks.extractText.mockResolvedValue({
    contextText: SYNTHETIC_CONTEXT,
    entities: SYNTHETIC_ENTITIES,
  });
  mocks.extractDictation.mockResolvedValue({
    contextText: SYNTHETIC_CONTEXT,
    entities: SYNTHETIC_ENTITIES,
  });
});

describe('Template Twin stateful upload-to-certification integration', () => {
  it('carries one immutable DOCX through real compile, mapping, proof invalidation, rerender, and activation', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    mocks.modelComplete.mockImplementation(
      async (request: { purpose: string }) => {
        if (request.purpose === 'tm_template_phi_scan') {
          return { phiFields: [], anyUncertain: false };
        }
        if (request.purpose === 'tm_template_synthetic_phi_scan') {
          return {
            directIdentifierClasses: [],
            appearsExplicitlySynthetic: true,
            anyUncertain: false,
          };
        }
        if (request.purpose === 'tm_template_parse') {
          return { mappings: proposalMappings(fixture.mappings) };
        }
        throw new Error(`Unexpected synthetic model purpose: ${request.purpose}`);
      },
    );
    const memory = createInMemoryObjectClient();
    const storage = createTemplateTwinArtifactStore({
      bucket: 'synthetic-template-artifacts-qa',
      clientFactory: () => memory.client,
      idFactory: () => 'immutable-synthetic-artifact',
      readinessEnv: {
        TEMPLATE_TWIN_STORAGE_PROFILE: 'qa',
        TEMPLATE_TWIN_QA_STORAGE_ENCRYPTION_AT_REST_ATTESTATION:
          TEMPLATE_TWIN_QA_STORAGE_EXCEPTION_ATTESTATION,
        TEMPLATE_TWIN_QA_STORAGE_TLS_EXPECTATION_ATTESTATION:
          TEMPLATE_TWIN_QA_STORAGE_EXCEPTION_ATTESTATION,
        TEMPLATE_TWIN_QA_STORAGE_LEAST_PRIVILEGE_ATTESTATION:
          TEMPLATE_TWIN_QA_STORAGE_EXCEPTION_ATTESTATION,
        TEMPLATE_TWIN_QA_STORAGE_LIFECYCLE_RETENTION_ATTESTATION:
          TEMPLATE_TWIN_QA_STORAGE_EXCEPTION_ATTESTATION,
        TEMPLATE_TWIN_QA_STORAGE_BACKUP_RESTORE_ATTESTATION:
          TEMPLATE_TWIN_QA_STORAGE_EXCEPTION_ATTESTATION,
        MOCK_AI_CALLS: 'true',
        DATABASE_URL: 'postgresql://synthetic@postgres/meddoc_qa_test',
      },
      objectLedgerClient: null,
    });

    const draft = await createTemplateTwinDraft({
      source: fixture.source,
      identity: {
        name: 'Synthetic stateful intake',
        encounterType: 'Synthetic stateful visit',
        versionDescription: 'Initial synthetic QA version',
      },
      actor: ACTOR,
      storage,
    });
    const draftWorkspace = await readTemplateTwinWorkspace({
      noteTemplateId: draft.noteTemplateId,
      doctorId: ACTOR.userId,
      practiceId: ACTOR.practiceId,
    });
    expect(draftWorkspace).not.toBeNull();
    expect(draftWorkspace).toMatchObject({
      template: { status: 'draft', certificationStatus: 'needs_confirmation' },
      stats: {
        totalFields: fixture.ir.fields.length,
        dropdowns: 1,
        checkboxes: 1,
        tables: 1,
      },
      unsupported: fixture.ir.unsupported,
      latestSyntheticTest: null,
    });
    expect(draftWorkspace!.fields.map((item) => item.field.fieldId)).toEqual(
      fixture.ir.fields.map((field) => field.fieldId),
    );
    expect(database.templates.get(PRIOR_TEMPLATE_ID)?.status).toBe('active');

    await expect(
      certifyAndActivateTemplateTwin({
        noteTemplateId: draft.noteTemplateId,
        actor: ACTOR,
        expectedMappingsSha256: draftWorkspace!.mappingsSha256,
      }),
    ).rejects.toMatchObject({ code: 'CERTIFICATION_BLOCKED' });
    expect(database.templates.get(draft.noteTemplateId)?.status).toBe('draft');
    expect(database.certifications.size).toBe(0);

    const confirmed = await updateTemplateTwinMappings({
      noteTemplateId: draft.noteTemplateId,
      actor: ACTOR,
      expectedMappingsSha256: draftWorkspace!.mappingsSha256,
      mappings: fixture.mappings,
    });
    expect(confirmed.mappingsSha256).toBe(
      templateTwinMappingsSha256(fixture.mappings),
    );
    expect(confirmed.fields.every((item) => item.mapping.status === 'certified')).toBe(true);

    await expect(
      certifyAndActivateTemplateTwin({
        noteTemplateId: draft.noteTemplateId,
        actor: ACTOR,
        expectedMappingsSha256: confirmed.mappingsSha256,
      }),
    ).rejects.toMatchObject({ code: 'CERTIFICATION_BLOCKED' });
    expect(database.templates.get(draft.noteTemplateId)?.status).toBe('draft');

    const firstProof = await runTemplateTwinSyntheticTest({
      noteTemplateId: draft.noteTemplateId,
      actor: ACTOR,
      expectedMappingsSha256: confirmed.mappingsSha256,
      encounterText: SYNTHETIC_CONTEXT,
      encounterMode: 'text',
      storage,
    });
    expect(firstProof.latestSyntheticTest).toMatchObject({
      mappingsSha256: confirmed.mappingsSha256,
      roundTripVerified: true,
    });
    expect(compiledForTemplate(draft.noteTemplateId).latestTestRoundTrip).toMatchObject({
      verified: true,
      packageCheck: 'verified',
      fieldCheck: 'verified',
      staticRegionCheck: 'verified',
      sourceSha256: fixture.ir.source.sha256,
    });

    const changedMappings = firstProof.fields.map((item, index) =>
      index === 0
        ? {
            ...item.mapping,
            approvedSynonyms: [...item.mapping.approvedSynonyms, 'chief_concern'],
          }
        : item.mapping,
    );
    const changedHash = templateTwinMappingsSha256(changedMappings);
    expect(changedHash).not.toBe(firstProof.mappingsSha256);
    const invalidated = await updateTemplateTwinMappings({
      noteTemplateId: draft.noteTemplateId,
      actor: ACTOR,
      expectedMappingsSha256: firstProof.mappingsSha256,
      mappings: changedMappings,
    });
    expect(invalidated.mappingsSha256).toBe(changedHash);
    expect(invalidated.latestSyntheticTest).toBeNull();
    expect(compiledForTemplate(draft.noteTemplateId)).toMatchObject({
      latestSyntheticTestManifest: null,
      latestTestMappingsSha256: null,
      latestTestOutputObjectKey: null,
      latestTestOutputVersionId: null,
      latestTestOutputEtag: null,
      latestTestOutputSha256: null,
      latestTestRoundTrip: null,
      latestTestVerifiedAt: null,
    });

    await expect(
      runTemplateTwinSyntheticTest({
        noteTemplateId: draft.noteTemplateId,
        actor: ACTOR,
        expectedMappingsSha256: firstProof.mappingsSha256,
        encounterText: SYNTHETIC_CONTEXT,
        encounterMode: 'text',
        storage,
      }),
    ).rejects.toMatchObject({ code: 'CONFLICT' });
    await expect(
      certifyAndActivateTemplateTwin({
        noteTemplateId: draft.noteTemplateId,
        actor: ACTOR,
        expectedMappingsSha256: changedHash,
      }),
    ).rejects.toMatchObject({ code: 'CERTIFICATION_BLOCKED' });
    expect(database.templates.get(draft.noteTemplateId)?.status).toBe('draft');

    const refreshedProof = await runTemplateTwinSyntheticTest({
      noteTemplateId: draft.noteTemplateId,
      actor: ACTOR,
      expectedMappingsSha256: changedHash,
      encounterText: SYNTHETIC_CONTEXT,
      encounterMode: 'text',
      storage,
    });
    expect(refreshedProof.latestSyntheticTest).toMatchObject({
      mappingsSha256: changedHash,
      roundTripVerified: true,
    });

    const certified = await certifyAndActivateTemplateTwin({
      noteTemplateId: draft.noteTemplateId,
      actor: ACTOR,
      expectedMappingsSha256: changedHash,
      expectedSyntheticTestProvenanceSha256:
        refreshedProof.latestSyntheticTest!.provenanceSha256,
    });
    expect(certified.template).toMatchObject({
      status: 'active',
      certificationStatus: 'certified',
    });
    expect(certified.canEdit).toBe(false);
    expect(database.templates.get(PRIOR_TEMPLATE_ID)?.status).toBe('inactive');
    expect(database.certifications.size).toBe(1);
    expect(compiledForTemplate(draft.noteTemplateId).certification).toMatchObject({
      compiledStructureSha256: fixture.ir.structureSha256,
      approvedMappingsSha256: changedHash,
      testOutputSha256: refreshedProof.latestSyntheticTest!.outputSha256,
    });

    const sourceObjects = [...memory.objects.entries()].filter(([key]) =>
      key.includes('/sources/'),
    );
    const outputObjects = [...memory.objects.entries()].filter(([key]) =>
      key.includes('/outputs/'),
    );
    expect(sourceObjects).toHaveLength(1);
    expect(sourceObjects[0]![1].bytes).toEqual(fixture.source);
    expect(outputObjects).toHaveLength(2);
    expect(new Set(outputObjects.map(([key]) => key)).size).toBe(2);
    expect(
      outputObjects.every(([, artifact]) => artifact.bytes.byteLength > 0),
    ).toBe(true);
    expect(memory.getPutCount()).toBe(3);
    expect(mocks.modelComplete.mock.calls.map((call) => call[0].purpose)).toEqual([
      'tm_template_phi_scan',
      'tm_template_parse',
      'tm_template_synthetic_phi_scan',
      'tm_template_synthetic_phi_scan',
    ]);
    expect(mocks.extractText).toHaveBeenCalledTimes(2);
    const syntheticAuditRows = mocks.outboxCreate.mock.calls
      .map((call) => record(call[0]).data)
      .map(record)
      .filter(
        (data) => data.action === 'TEMPLATE_TWIN_SYNTHETIC_TESTED',
      );
    expect(syntheticAuditRows).toHaveLength(2);
    expect(
      new Set(syntheticAuditRows.map((data) => data.eventKey)).size,
    ).toBe(2);
    expect(syntheticAuditRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          practiceId: ACTOR.practiceId,
          actorId: ACTOR.userId,
          actorEmailSnapshot: ACTOR.userEmail,
          targetType: 'TemplateTwinCompiledVersion',
          metadata: expect.objectContaining({ verified: true, inputMode: 'text' }),
        }),
      ]),
    );
  });
});
