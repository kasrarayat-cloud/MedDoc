import { randomUUID } from 'node:crypto';

import { Prisma } from '@prisma/client';
import prisma from '@meddoc/db';

import {
  extractTemplateTwinDictationEntities,
  extractTemplateTwinTextEntities,
} from '@/worker/layers/03-extract-entities';

import { enqueueTemplateTwinAudit } from './audit-outbox';
import { prepareTemplateTwinFill } from './fill-engine';
import {
  projectEncounterFacts,
  type EncounterEntitySnapshot,
} from './encounter-facts';
import { SemanticMappingSchema, TemplateDocIRSchema, type SemanticMapping } from './ir';
import { templateTwinMappingsSha256 } from './mapping-hash';
import {
  claimTemplateTwinObject,
  createTemplateTwinArtifactStore,
  type TemplateTwinArtifactStore,
} from './storage';
import type { TemplateTwinActor } from './certification-lifecycle';
import { readTemplateTwinWorkspace } from './workspace-read';
import { assertTemplateTwinSyntheticEvidencePhiFree } from './synthetic-evidence-gate';
import {
  TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE,
  isSupportedTemplateTwinConcept,
} from './supported-concepts';

export class TemplateTwinSyntheticTestError extends Error {
  readonly code:
    | 'NOT_FOUND'
    | 'IMMUTABLE'
    | 'CONFLICT'
    | 'MAPPINGS_NOT_READY'
    | 'VALIDATION_FAILED'
    | 'SYNTHETIC_EVIDENCE_REJECTED';

  constructor(code: TemplateTwinSyntheticTestError['code'], message: string) {
    super(message);
    this.name = 'TemplateTwinSyntheticTestError';
    this.code = code;
  }
}

interface MappingRow {
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
}

function mapping(fieldId: string, row: MappingRow): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId,
    clinicalConcept: row.clinicalConcept,
    expectedDataType: row.expectedDataType,
    polarityBehavior: row.polarityBehavior,
    temporality: row.temporality,
    laterality: row.laterality,
    unitPolicy: row.unitPolicy,
    approvedSynonyms: Array.isArray(row.approvedSynonyms) ? row.approvedSynonyms : [],
    required: row.required,
    blankPolicy: row.blankPolicy,
    unknownPolicy: row.unknownPolicy,
    practiceDefault: row.practiceDefault,
    status: row.mappingStatus.toLowerCase(),
  });
}

function asJson(value: unknown): Prisma.InputJsonValue {
  return value as Prisma.InputJsonValue;
}

export async function runTemplateTwinSyntheticTest(input: {
  noteTemplateId: string;
  actor: TemplateTwinActor;
  expectedMappingsSha256: string;
  encounterText: string;
  encounterMode?: 'text' | 'dictation';
  storage?: TemplateTwinArtifactStore;
}) {
  const row = await prisma.noteTemplate.findFirst({
    where: {
      id: input.noteTemplateId,
      doctorId: input.actor.userId,
      templateKind: 'template_twin_docx',
    },
    select: {
      id: true,
      version: true,
      templateTwinCompiledVersion: {
        select: {
          id: true,
          compiledDocumentIr: true,
          certificationStatus: true,
          sourceArtifact: {
            select: {
              practiceId: true,
              objectKey: true,
              objectVersionId: true,
              objectEtag: true,
              sha256: true,
              sizeBytes: true,
              validationStatus: true,
            },
          },
          fields: {
            orderBy: { displayOrder: 'asc' },
            select: {
              fieldId: true,
              mapping: {
                select: {
                  clinicalConcept: true,
                  expectedDataType: true,
                  polarityBehavior: true,
                  temporality: true,
                  laterality: true,
                  unitPolicy: true,
                  approvedSynonyms: true,
                  required: true,
                  blankPolicy: true,
                  unknownPolicy: true,
                  practiceDefault: true,
                  mappingStatus: true,
                },
              },
            },
          },
        },
      },
    },
  });
  const compiled = row?.templateTwinCompiledVersion;
  if (
    !row ||
    !compiled ||
    compiled.sourceArtifact.practiceId !== input.actor.practiceId ||
    compiled.sourceArtifact.validationStatus !== 'accepted' ||
    !compiled.sourceArtifact.objectKey ||
    !compiled.sourceArtifact.objectVersionId ||
    !compiled.sourceArtifact.objectEtag
  ) {
    throw new TemplateTwinSyntheticTestError('NOT_FOUND', 'Template Twin version not found.');
  }
  if (compiled.certificationStatus === 'CERTIFIED') {
    throw new TemplateTwinSyntheticTestError(
      'IMMUTABLE',
      'Certified Template Twin versions cannot be retested or changed.',
    );
  }
  const mappings = compiled.fields.map((field: { fieldId: string; mapping: MappingRow | null }) => {
    if (!field.mapping) {
      throw new TemplateTwinSyntheticTestError(
        'MAPPINGS_NOT_READY',
        'Every field needs a physician-confirmed mapping before testing.',
      );
    }
    return mapping(field.fieldId, field.mapping);
  });
  const mappingsSha256 = templateTwinMappingsSha256(mappings);
  if (mappingsSha256 !== input.expectedMappingsSha256) {
    throw new TemplateTwinSyntheticTestError(
      'CONFLICT',
      'Mappings changed after the page loaded. Reload before testing.',
    );
  }
  if (mappings.some((item: SemanticMapping) => item.status !== 'certified' || !item.clinicalConcept)) {
    throw new TemplateTwinSyntheticTestError(
      'MAPPINGS_NOT_READY',
      'Every field needs a physician-confirmed mapping before testing.',
    );
  }
  if (
    mappings.some(
      (item: SemanticMapping) =>
        item.clinicalConcept !== null &&
        !isSupportedTemplateTwinConcept(item.clinicalConcept),
    )
  ) {
    throw new TemplateTwinSyntheticTestError(
      'MAPPINGS_NOT_READY',
      `${TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE}: One or more fields use clinical details that the current extractor cannot safely produce.`,
    );
  }

  // Certification artifacts retain evidence anchors and filled values. Gate
  // the encounter before Layer 3 or storage so a mislabeled real encounter is
  // not persisted as a synthetic proof.
  try {
    await assertTemplateTwinSyntheticEvidencePhiFree({
      encounterText: input.encounterText,
      practiceId: input.actor.practiceId,
      userId: input.actor.userId,
    });
  } catch {
    throw new TemplateTwinSyntheticTestError(
      'SYNTHETIC_EVIDENCE_REJECTED',
      'Use clearly labeled synthetic test evidence without patient identifiers.',
    );
  }

  const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
  const encounterMode = input.encounterMode ?? 'text';
  const extracted = encounterMode === 'dictation'
    ? await extractTemplateTwinDictationEntities({
        practiceId: input.actor.practiceId,
        userId: input.actor.userId,
        noteTemplateId: row.id,
        dictationText: input.encounterText,
      })
    : await extractTemplateTwinTextEntities({
        practiceId: input.actor.practiceId,
        userId: input.actor.userId,
        noteTemplateId: row.id,
        rawText: input.encounterText,
      });
  const facts = projectEncounterFacts({
    mode: encounterMode,
    contextText: extracted.contextText,
    entities: extracted.entities as unknown as EncounterEntitySnapshot,
    asrQuality: 'unknown',
  });
  const storage = input.storage ?? createTemplateTwinArtifactStore();
  const source = await storage.readSourceArtifact({
    practiceId: input.actor.practiceId,
    objectKey: compiled.sourceArtifact.objectKey,
    expectedObjectVersionId: compiled.sourceArtifact.objectVersionId,
    expectedObjectEtag: compiled.sourceArtifact.objectEtag,
    expectedSha256: compiled.sourceArtifact.sha256,
    expectedSizeBytes: compiled.sourceArtifact.sizeBytes,
  });
  const prepared = await prepareTemplateTwinFill({
    // Certification runs do not have a visit row. Bind their immutable test
    // manifest to the exact synthetic review text with a fixed local version;
    // visit fills always use the persisted SOAP version instead.
    soapVersion: 1,
    soapFinal: extracted.contextText,
    compiledVersionId: compiled.id,
    noteTemplateId: row.id,
    noteTemplateVersion: row.version,
    ir,
    mappings,
    facts,
    source,
    resolverModelVersion:
      process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-sonnet-4-6',
    validationNow: new Date(),
    allowUncertifiedForSyntheticTest: true,
  });
  if (!prepared.render) {
    const blockers = prepared.manifest.validation.issues.filter(
      (issue) => issue.severity === 'blocking',
    ).length;
    throw new TemplateTwinSyntheticTestError(
      'VALIDATION_FAILED',
      `The synthetic encounter left ${blockers} blocking field check${blockers === 1 ? '' : 's'}. Add direct synthetic evidence or correct the mapping, then test again.`,
    );
  }
  const render = prepared.render;
  const output = await storage.storeOutputArtifact({
    practiceId: input.actor.practiceId,
    visitId: `synthetic_${compiled.id}`,
    manifestSha256: prepared.manifestSha256,
    bytes: render.document,
  });
  // Generated once outside the serializable callback: a database retry uses
  // the same key, while an explicit physician re-test remains a distinct
  // audited action even when deterministic rendering reuses identical bytes.
  const syntheticTestEventKey =
    `template-twin:synthetic-tested:${compiled.id}:${randomUUID()}`;

  await prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      const fresh = await tx.templateTwinCompiledVersion.findUnique({
        where: { id: compiled.id },
        select: {
          certificationStatus: true,
          fields: {
            orderBy: { displayOrder: 'asc' },
            select: {
              fieldId: true,
              mapping: {
                select: {
                  clinicalConcept: true,
                  expectedDataType: true,
                  polarityBehavior: true,
                  temporality: true,
                  laterality: true,
                  unitPolicy: true,
                  approvedSynonyms: true,
                  required: true,
                  blankPolicy: true,
                  unknownPolicy: true,
                  practiceDefault: true,
                  mappingStatus: true,
                },
              },
            },
          },
        },
      });
      if (!fresh || fresh.certificationStatus === 'CERTIFIED') {
        throw new TemplateTwinSyntheticTestError('IMMUTABLE', 'This template is already certified.');
      }
      const freshMappings = fresh.fields.map((field: { fieldId: string; mapping: MappingRow | null }) => {
        if (!field.mapping) {
          throw new TemplateTwinSyntheticTestError('CONFLICT', 'Mappings changed during the test.');
        }
        return mapping(field.fieldId, field.mapping);
      });
      if (templateTwinMappingsSha256(freshMappings) !== mappingsSha256) {
        throw new TemplateTwinSyntheticTestError('CONFLICT', 'Mappings changed during the test.');
      }
      await tx.templateTwinCompiledVersion.update({
        where: { id: compiled.id },
        data: {
          latestSyntheticTestManifest: asJson(prepared.manifest),
          latestTestMappingsSha256: mappingsSha256,
          latestTestOutputObjectKey: output.objectKey,
          latestTestOutputVersionId: output.objectVersionId,
          latestTestOutputEtag: output.objectEtag,
          latestTestOutputSha256: output.sha256,
          latestTestStaticContentSha256: ir.staticContentSha256,
          latestTestRoundTrip: asJson(render.verification),
          latestTestVerifiedAt: new Date(),
        },
      });
      await claimTemplateTwinObject(tx, {
        objectKey: output.objectKey,
        practiceId: input.actor.practiceId,
        claimType: 'compiled_test_output',
        claimId: compiled.id,
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: syntheticTestEventKey,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: 'TEMPLATE_TWIN_SYNTHETIC_TESTED',
        targetType: 'TemplateTwinCompiledVersion',
        targetId: compiled.id,
        metadata: {
          templateVersion: row.version,
          mappingsSha256,
          outputSha256: output.sha256,
          outputVersionId: output.objectVersionId,
          outputEtag: output.objectEtag,
          fieldCount: prepared.manifest.fields.length,
          verified: true,
          inputMode: encounterMode,
        },
      });
    },
    { isolationLevel: 'Serializable' },
  );
  const workspace = await readTemplateTwinWorkspace({
    noteTemplateId: row.id,
    doctorId: input.actor.userId,
    practiceId: input.actor.practiceId,
  });
  if (!workspace) {
    throw new TemplateTwinSyntheticTestError('NOT_FOUND', 'Template Twin version not found.');
  }
  return workspace;
}
