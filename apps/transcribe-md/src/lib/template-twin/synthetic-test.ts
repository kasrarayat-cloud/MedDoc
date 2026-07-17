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
import {
  assertTemplateTwinStagingQaEvidencePhiFree,
  assertTemplateTwinSyntheticEvidencePhiFree,
} from './synthetic-evidence-gate';
import { isTemplateTwinStagingQaFixtureSource } from './staging-qa-fixtures';
import { runWithTemplateTwinStagingQaCertificationProvider } from './staging-qa-certification-provider';
import {
  assertTemplateTwinSourceProvenance,
  bindTemplateTwinSyntheticProofToSourceProvenance,
  TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_MESSAGE,
} from './source-phi-evidence';
import {
  TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE,
  isSupportedTemplateTwinConcept,
} from './supported-concepts';
import {
  buildCanonicalCustomConceptEvidence,
  createCertifiedCustomConceptProvider,
  extractCertifiedCustomConcepts,
} from './custom-concepts';
import {
  customConceptSpecifications,
  fieldRequiresExplicitIntent,
  fieldsWithCertifiedCustomIntent,
  parsePersistedFieldIntent,
  templateTwinFieldIntentsSha256,
  unresolvedFieldIntent,
  type PersistedTemplateTwinFieldIntent,
} from './field-intent';
import { lockTemplateTwinRolloutForFinalClaim } from './rollout';

export class TemplateTwinSyntheticTestError extends Error {
  readonly code:
    | 'NOT_FOUND'
    | 'IMMUTABLE'
    | 'CONFLICT'
    | 'MAPPINGS_NOT_READY'
    | 'VALIDATION_FAILED'
    | 'SYNTHETIC_EVIDENCE_REJECTED'
    | 'SOURCE_PROVENANCE_INVALID'
    | 'ROLLOUT_CHANGED';

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

type PersistedIntentDecisionRow = Omit<
  PersistedTemplateTwinFieldIntent,
  'fieldDefinitionId' | 'fieldId'
>;

interface PersistedFieldWithIntent {
  fieldId: string;
  id: string;
  intentDecisions: PersistedIntentDecisionRow[];
  mapping: MappingRow | null;
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
  /** HTTP callers always provide this; legacy generic-template service tests
   * may omit it only when the IR has no explicit intent-bearing fields. */
  expectedFieldIntentsSha256?: string;
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
      lineageId: true,
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
              privacyScanEvidence: true,
            },
          },
          fields: {
            orderBy: { displayOrder: 'asc' },
            select: {
              fieldId: true,
              id: true,
              intentDecisions: {
                orderBy: { version: 'desc' },
                take: 1,
                select: {
                  id: true,
                  version: true,
                  intentKind: true,
                  supportedConcept: true,
                  customConceptId: true,
                  customSpec: true,
                  customSpecSha256: true,
                  reason: true,
                  decidedById: true,
                  decidedAt: true,
                },
              },
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
  let sourceProvenance;
  try {
    sourceProvenance = assertTemplateTwinSourceProvenance({
      privacyScanEvidence: compiled.sourceArtifact.privacyScanEvidence,
      requireBinding: false,
    });
  } catch {
    throw new TemplateTwinSyntheticTestError(
      'SOURCE_PROVENANCE_INVALID',
      TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_MESSAGE,
    );
  }
  if (compiled.certificationStatus === 'CERTIFIED') {
    throw new TemplateTwinSyntheticTestError(
      'IMMUTABLE',
      'Certified Template Twin versions cannot be retested or changed.',
    );
  }
  const persistedFields = compiled.fields as PersistedFieldWithIntent[];
  const mappings = persistedFields.map((field) => {
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
  const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
  const persistedFieldById = new Map(
    persistedFields.map((field) => [field.fieldId, field]),
  );
  const explicitIntents = ir.fields
    .filter(fieldRequiresExplicitIntent)
    .map((field) => {
      const persisted = persistedFieldById.get(field.fieldId);
      if (!persisted) {
        throw new TemplateTwinSyntheticTestError(
          'MAPPINGS_NOT_READY',
          'A placeholder field is missing its physician intent record.',
        );
      }
      const decision = persisted.intentDecisions[0];
      return {
        fieldId: field.fieldId,
        intent: decision
          ? parsePersistedFieldIntent({
              ...decision,
              fieldDefinitionId: persisted.id,
              fieldId: field.fieldId,
            } satisfies PersistedTemplateTwinFieldIntent)
          : unresolvedFieldIntent(),
      };
    });
  const fieldIntentsSha256 = templateTwinFieldIntentsSha256(explicitIntents);
  if (
    (explicitIntents.length > 0 && !input.expectedFieldIntentsSha256) ||
    (input.expectedFieldIntentsSha256 !== undefined &&
      fieldIntentsSha256 !== input.expectedFieldIntentsSha256)
  ) {
    throw new TemplateTwinSyntheticTestError(
      'CONFLICT',
      'Field intent changed after the page loaded. Reload before testing.',
    );
  }
  const intentByFieldId = new Map(
    explicitIntents.map((entry) => [entry.fieldId, entry.intent]),
  );
  const customSpecifications = customConceptSpecifications(explicitIntents);
  const effectiveFields = fieldsWithCertifiedCustomIntent({
    fields: ir.fields,
    intents: explicitIntents,
  });
  const conceptProviders =
    customSpecifications.length > 0
      ? [createCertifiedCustomConceptProvider(customSpecifications)]
      : [];
  const staticFieldIds = explicitIntents.flatMap((entry) =>
    entry.intent.intentKind === 'static' ? [entry.fieldId] : [],
  );
  if (
    mappings.some((item: SemanticMapping) => {
      const intent = intentByFieldId.get(item.fieldId);
      return (
        item.status !== 'certified' ||
        intent?.intentKind === 'unresolved' ||
        (intent?.intentKind === 'static'
          ? item.clinicalConcept !== null
          : !item.clinicalConcept)
      );
    })
  ) {
    throw new TemplateTwinSyntheticTestError(
      'MAPPINGS_NOT_READY',
      'Every field needs a physician-confirmed mapping before testing.',
    );
  }
  if (
    mappings.some(
      (item: SemanticMapping) =>
        item.clinicalConcept !== null &&
        !isSupportedTemplateTwinConcept(item.clinicalConcept, conceptProviders),
    )
  ) {
    throw new TemplateTwinSyntheticTestError(
      'MAPPINGS_NOT_READY',
      `${TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE}: One or more fields use clinical details that the current extractor cannot safely produce.`,
    );
  }

  const encounterMode = input.encounterMode ?? 'text';
  const providerResult =
    await runWithTemplateTwinStagingQaCertificationProvider({
      source: {
        sha256: compiled.sourceArtifact.sha256,
        sizeBytes: compiled.sourceArtifact.sizeBytes,
      },
      noteTemplateId: row.id,
      doctorId: input.actor.userId,
      practiceId: input.actor.practiceId,
      rolloutToken: input.actor.rolloutToken,
      encounterMode,
      evidenceText: input.encounterText,
      expectedMappingConfirmation: {
        mappingsSha256: input.expectedMappingsSha256,
        fieldIntentsSha256,
      },
      operation: async (providerVisitId) => {
        // Certification artifacts retain evidence anchors and filled values.
        // Gate the encounter before Layer 3 or storage so a mislabeled real
        // encounter is not persisted as a synthetic proof. For the exact
        // staging fixture, this privacy-provider call is itself inside the
        // deterministic provider context; it cannot fall through to live AI.
        try {
          const assertEvidencePhiFree =
            isTemplateTwinStagingQaFixtureSource({
              sha256: compiled.sourceArtifact.sha256,
              sizeBytes: compiled.sourceArtifact.sizeBytes,
            })
              ? assertTemplateTwinStagingQaEvidencePhiFree
              : assertTemplateTwinSyntheticEvidencePhiFree;
          await assertEvidencePhiFree({
            encounterText: input.encounterText,
            practiceId: input.actor.practiceId,
            userId: input.actor.userId,
            providerVisitId,
          });
        } catch {
          throw new TemplateTwinSyntheticTestError(
            'SYNTHETIC_EVIDENCE_REJECTED',
            'Use clearly labeled synthetic test evidence without patient identifiers.',
          );
        }

        const extracted =
          encounterMode === 'dictation'
            ? await extractTemplateTwinDictationEntities({
                practiceId: input.actor.practiceId,
                userId: input.actor.userId,
                noteTemplateId: row.id,
                providerVisitId,
                dictationText: input.encounterText,
              })
            : await extractTemplateTwinTextEntities({
                practiceId: input.actor.practiceId,
                userId: input.actor.userId,
                noteTemplateId: row.id,
                providerVisitId,
                rawText: input.encounterText,
              });
        const projectedFacts = projectEncounterFacts({
          mode: encounterMode,
          contextText: extracted.contextText,
          entities: extracted.entities as unknown as EncounterEntitySnapshot,
          asrQuality: 'unknown',
        });
        const customExtraction =
          customSpecifications.length > 0
            ? await extractCertifiedCustomConcepts({
                specifications: customSpecifications,
                evidence: buildCanonicalCustomConceptEvidence({
                  mode: encounterMode,
                  contextText: extracted.contextText,
                  asrQuality: 'unknown',
                }),
                practiceId: input.actor.practiceId,
                visitId:
                  providerVisitId ??
                  `template-twin-synthetic-${compiled.id}`,
                userId: input.actor.userId,
              })
            : null;
        return { extracted, projectedFacts, customExtraction };
      },
    });
  const { extracted, projectedFacts, customExtraction } = providerResult;
  const facts = [
    ...projectedFacts,
    ...(customExtraction?.facts ?? []),
  ];
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
    fieldIntentsSha256,
    staticFieldIds,
    conceptProviders,
    customExtraction,
    effectiveFields,
    customSpecifications,
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
      // This is the linearization point for the synthetic proof/output claim.
      // Storage and extraction may have completed, but a disable/re-enable
      // after admission makes the old token permanently stale. The unclaimed
      // object remains in the durable reconciliation ledger.
      const finalRollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.actor.practiceId,
        pinnedToken: input.actor.rolloutToken,
      });
      if (!finalRollout.allowed) {
        throw new TemplateTwinSyntheticTestError(
          'ROLLOUT_CHANGED',
          `${finalRollout.code}: Template Twin availability changed while the synthetic proof was being verified. Run the test again.`,
        );
      }
      const fresh = await tx.templateTwinCompiledVersion.findUnique({
        where: { id: compiled.id },
        select: {
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
              privacyScanEvidence: true,
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
      });
      if (!fresh || fresh.certificationStatus === 'CERTIFIED') {
        throw new TemplateTwinSyntheticTestError('IMMUTABLE', 'This template is already certified.');
      }
      try {
        assertTemplateTwinSourceProvenance({
          privacyScanEvidence: fresh.sourceArtifact.privacyScanEvidence,
          requireBinding: true,
          boundEvidenceSha256: sourceProvenance.evidenceSha256,
        });
      } catch {
        throw new TemplateTwinSyntheticTestError(
          'SOURCE_PROVENANCE_INVALID',
          TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_MESSAGE,
        );
      }
      if (
        fresh.sourceArtifact.practiceId !== compiled.sourceArtifact.practiceId ||
        fresh.sourceArtifact.validationStatus !== 'accepted' ||
        fresh.sourceArtifact.objectKey !== compiled.sourceArtifact.objectKey ||
        fresh.sourceArtifact.objectVersionId !==
          compiled.sourceArtifact.objectVersionId ||
        fresh.sourceArtifact.objectEtag !== compiled.sourceArtifact.objectEtag ||
        fresh.sourceArtifact.sha256 !== compiled.sourceArtifact.sha256 ||
        fresh.sourceArtifact.sizeBytes !== compiled.sourceArtifact.sizeBytes
      ) {
        throw new TemplateTwinSyntheticTestError(
          'SOURCE_PROVENANCE_INVALID',
          TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_MESSAGE,
        );
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
          latestTestFieldIntentsSha256: fieldIntentsSha256,
          latestTestOutputObjectKey: output.objectKey,
          latestTestOutputVersionId: output.objectVersionId,
          latestTestOutputEtag: output.objectEtag,
          latestTestOutputSha256: output.sha256,
          latestTestStaticContentSha256: ir.staticContentSha256,
          latestTestRoundTrip: asJson(
            bindTemplateTwinSyntheticProofToSourceProvenance(
              render.verification,
              sourceProvenance.evidenceSha256,
            ),
          ),
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
          sourcePrivacyScanEvidenceSha256:
            sourceProvenance.evidenceSha256,
          rolloutGlobalGeneration:
            input.actor.rolloutToken.globalGeneration.toString(),
          rolloutPracticeGeneration:
            input.actor.rolloutToken.practiceGeneration.toString(),
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
