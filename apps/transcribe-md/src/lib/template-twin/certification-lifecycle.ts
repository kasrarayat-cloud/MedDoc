import { Prisma } from '@prisma/client';
import prisma from '@meddoc/db';

import {
  SemanticMappingSchema,
  TEMPLATE_TWIN_RENDERER_VERSION,
  TEMPLATE_TWIN_RESOLVER_VERSION,
  TemplateDocIRSchema,
  TemplateTwinFillManifestSchema,
  templateTwinCounts,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
} from './ir';
import { isMappingTypeCompatible } from './semantic-mapping';
import { templateTwinMappingsSha256 } from './mapping-hash';
import { readTemplateTwinWorkspace } from './workspace-read';
import type { TemplateTwinWorkspace } from './client-types';
import { parseTemplateTwinArtifactKey } from './storage';
import { canonicalSha256 } from './canonical';
import { validateTemplateTwin } from './validation';
import {
  TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE,
  TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_REASON,
  isSupportedTemplateTwinConcept,
} from './supported-concepts';
import { evaluateTemplateTwinCertificationCoverage } from './certification-coverage';
import { enqueueTemplateTwinAudit } from './audit-outbox';
import { templateTwinSyntheticTestProvenanceSha256 } from './synthetic-test-provenance';
import {
  assertTemplateTwinSourceProvenance,
  templateTwinSyntheticProofSourceEvidenceSha256,
  TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_MESSAGE,
} from './source-phi-evidence';

export class TemplateTwinLifecycleError extends Error {
  readonly code:
    | 'NOT_FOUND'
    | 'IMMUTABLE'
    | 'CONFLICT'
    | 'FIELD_SET_MISMATCH'
    | 'MAPPING_INVALID'
    | 'UNSUPPORTED_CLINICAL_CONCEPT'
    | 'CERTIFICATION_BLOCKED';

  constructor(code: TemplateTwinLifecycleError['code'], message: string) {
    super(message);
    this.name = 'TemplateTwinLifecycleError';
    this.code = code;
  }
}

export interface TemplateTwinActor {
  userId: string;
  userEmail: string;
  practiceId: string;
}

interface PersistedMappingRow {
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

function fromPersistedMapping(
  fieldId: string,
  row: PersistedMappingRow,
): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId,
    clinicalConcept: row.clinicalConcept,
    expectedDataType: row.expectedDataType,
    polarityBehavior: row.polarityBehavior,
    temporality: row.temporality,
    laterality: row.laterality,
    unitPolicy: row.unitPolicy,
    approvedSynonyms: Array.isArray(row.approvedSynonyms)
      ? row.approvedSynonyms
      : [],
    required: row.required,
    blankPolicy: row.blankPolicy,
    unknownPolicy: row.unknownPolicy,
    practiceDefault: row.practiceDefault,
    status: row.mappingStatus.toLowerCase(),
  });
}

function dbStatus(
  status: SemanticMapping['status'],
): 'RECOGNIZED' | 'NEEDS_CONFIRMATION' | 'UNSUPPORTED' | 'CERTIFIED' {
  switch (status) {
    case 'recognized':
      return 'RECOGNIZED';
    case 'needs_confirmation':
      return 'NEEDS_CONFIRMATION';
    case 'unsupported':
      return 'UNSUPPORTED';
    case 'certified':
      return 'CERTIFIED';
  }
}

function asJson(value: unknown): Prisma.InputJsonValue {
  return value as Prisma.InputJsonValue;
}

function validPracticeDefault(
  field: TemplateField,
  mapping: SemanticMapping,
): boolean {
  const raw = mapping.practiceDefault;
  if (raw === null) return true;
  if (mapping.status !== 'certified') return false;
  switch (field.kind) {
    case 'narrative_text':
      return raw.trim().length > 0;
    case 'single_select':
      return field.allowedOptions.some(
        (option) => option.value === raw || option.displayText === raw,
      );
    case 'multi_select':
      return false;
    case 'checkbox':
      return raw === 'true' || raw === 'false';
    case 'date': {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return false;
      const date = new Date(`${raw}T00:00:00Z`);
      return !Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === raw;
    }
    case 'number':
      return /^[-+]?(?:\d+(?:\.\d+)?|\.\d+)$/.test(raw.trim());
    case 'measurement':
      return /^[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s+\S+)?$/.test(raw.trim());
  }
}

async function loadOwnedCompilation(
  client: Prisma.TransactionClient,
  noteTemplateId: string,
  actor: TemplateTwinActor,
) {
  const row = await client.noteTemplate.findFirst({
    where: {
      id: noteTemplateId,
      doctorId: actor.userId,
      templateKind: 'template_twin_docx',
    },
    select: {
      id: true,
      doctorId: true,
      encounterType: true,
      version: true,
      status: true,
      templateTwinCompiledVersion: {
        select: {
          id: true,
          compiledDocumentIr: true,
          certificationStatus: true,
          blockingUnsupportedCount: true,
          latestSyntheticTestManifest: true,
          latestTestMappingsSha256: true,
          latestTestOutputObjectKey: true,
          latestTestOutputVersionId: true,
          latestTestOutputEtag: true,
          latestTestOutputSha256: true,
          latestTestStaticContentSha256: true,
          latestTestRoundTrip: true,
          latestTestVerifiedAt: true,
          certification: { select: { id: true } },
          sourceArtifact: {
            select: {
              practiceId: true,
              objectVersionId: true,
              objectEtag: true,
              sha256: true,
              validationStatus: true,
              privacyScanEvidence: true,
            },
          },
          fields: {
            orderBy: { displayOrder: 'asc' },
            select: {
              id: true,
              fieldId: true,
              detectionStatus: true,
              mapping: {
                select: {
                  id: true,
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
  if (
    !row?.templateTwinCompiledVersion ||
    row.templateTwinCompiledVersion.sourceArtifact.practiceId !== actor.practiceId
  ) {
    throw new TemplateTwinLifecycleError('NOT_FOUND', 'Template Twin version not found.');
  }
  return { template: row, compiled: row.templateTwinCompiledVersion };
}

function currentMappings(compiled: Awaited<ReturnType<typeof loadOwnedCompilation>>['compiled']) {
  return compiled.fields.map((field) => {
    if (!field.mapping) {
      throw new TemplateTwinLifecycleError(
        'FIELD_SET_MISMATCH',
        'A compiled field has no semantic mapping.',
      );
    }
    return fromPersistedMapping(field.fieldId, field.mapping);
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Certification must bind the synthetic proof to this exact immutable
 * source, compiled static region, and persisted output. A truthy `verified`
 * bit alone is not an integrity boundary. */
function isVerifiedSyntheticProof(input: {
  roundTrip: unknown;
  sourceSha256: string;
  outputSha256: string;
  staticContentSha256: string;
  expectedStaticContentSha256: string;
  expectedFields: ReadonlyArray<{
    fieldId: string;
    partName: string;
    bindingPath: string;
    valueSha256: string;
    occurrences: number;
  }>;
}): boolean {
  if (!isRecord(input.roundTrip)) return false;
  const proof = input.roundTrip;
  const proofFields = Array.isArray(proof.fields) ? proof.fields : [];
  const fieldProofById = new Map<string, Record<string, unknown>>();
  for (const candidate of proofFields) {
    if (!isRecord(candidate) || typeof candidate.fieldId !== 'string') {
      return false;
    }
    if (fieldProofById.has(candidate.fieldId)) return false;
    fieldProofById.set(candidate.fieldId, candidate);
  }
  const fieldsVerified =
    fieldProofById.size === input.expectedFields.length &&
    input.expectedFields.every((expected) => {
      const field = fieldProofById.get(expected.fieldId);
      return Boolean(
        field &&
          field.status === 'verified' &&
          field.partName === expected.partName &&
          field.bindingPath === expected.bindingPath &&
          field.valueSha256 === expected.valueSha256 &&
          Number.isSafeInteger(expected.occurrences) &&
          expected.occurrences > 0 &&
          field.occurrences === expected.occurrences,
      );
    });
  return (
    input.staticContentSha256 === input.expectedStaticContentSha256 &&
    proof.verified === true &&
    proof.packageCheck === 'verified' &&
    proof.fieldCheck === 'verified' &&
    proof.staticRegionCheck === 'verified' &&
    proof.sourceSha256 === input.sourceSha256 &&
    proof.outputSha256 === input.outputSha256 &&
    Number.isSafeInteger(proof.untouchedEntriesVerified) &&
    Number(proof.untouchedEntriesVerified) >= 0 &&
    Number.isSafeInteger(proof.modifiedPartsVerified) &&
    Number(proof.modifiedPartsVerified) >= 0 &&
    fieldsVerified &&
    Array.isArray(proof.warningCodes) &&
    proof.warningCodes.every((code) => typeof code === 'string')
  );
}

function isVerifiedSyntheticManifest(input: {
  manifest: unknown;
  outputObjectKey: string;
  compiledVersionId: string;
  noteTemplateId: string;
  noteTemplateVersion: number;
  ir: TemplateDocIR;
  mappings: readonly SemanticMapping[];
}): boolean {
  const parsed = TemplateTwinFillManifestSchema.safeParse(input.manifest);
  if (!parsed.success) return false;
  const manifest = parsed.data;
  const keyParts = input.outputObjectKey.split('/');
  if (
    keyParts.length !== 8 ||
    keyParts[5] !== canonicalSha256(manifest) ||
    manifest.compiledVersionId !== input.compiledVersionId ||
    manifest.noteTemplateId !== input.noteTemplateId ||
    manifest.noteTemplateVersion !== input.noteTemplateVersion ||
    manifest.compilerVersion !== input.ir.compilerVersion ||
    manifest.resolverVersion !== TEMPLATE_TWIN_RESOLVER_VERSION ||
    manifest.rendererVersion !== TEMPLATE_TWIN_RENDERER_VERSION
  ) {
    return false;
  }
  const expectedFieldIds = input.ir.fields.map((field) => field.fieldId).sort();
  const manifestFieldIds = manifest.fields.map((field) => field.fieldId).sort();
  if (
    new Set(manifestFieldIds).size !== expectedFieldIds.length ||
    canonicalSha256(manifestFieldIds) !== canonicalSha256(expectedFieldIds) ||
    canonicalSha256(manifest.counts) !==
      canonicalSha256(templateTwinCounts(manifest.fields, input.ir.fields))
  ) {
    return false;
  }
  const reproduced = validateTemplateTwin({
    fields: input.ir.fields,
    mappings: input.mappings,
    facts: manifest.facts,
    resolutions: manifest.fields,
    tables: input.ir.tables,
    unsupported: input.ir.unsupported,
    allowUncertifiedForSyntheticTest: true,
    now: manifest.validation.checkedAt,
  });
  return (
    reproduced.valid &&
    reproduced.issues.every((issue) => issue.severity !== 'blocking') &&
    canonicalSha256(reproduced) === canonicalSha256(manifest.validation)
  );
}

async function refreshedWorkspace(
  noteTemplateId: string,
  actor: TemplateTwinActor,
): Promise<TemplateTwinWorkspace> {
  const workspace = await readTemplateTwinWorkspace({
    noteTemplateId,
    doctorId: actor.userId,
    practiceId: actor.practiceId,
  });
  if (!workspace) {
    throw new TemplateTwinLifecycleError('NOT_FOUND', 'Template Twin version not found.');
  }
  return workspace;
}

export async function updateTemplateTwinMappings(input: {
  noteTemplateId: string;
  actor: TemplateTwinActor;
  expectedMappingsSha256: string;
  mappings: readonly SemanticMapping[];
}): Promise<TemplateTwinWorkspace> {
  await prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      const { template, compiled } = await loadOwnedCompilation(
        tx,
        input.noteTemplateId,
        input.actor,
      );
      if (compiled.certification || compiled.certificationStatus === 'CERTIFIED') {
        throw new TemplateTwinLifecycleError(
          'IMMUTABLE',
          'Certified Template Twin versions cannot be edited.',
        );
      }

      const before = currentMappings(compiled);
      const beforeHash = templateTwinMappingsSha256(before);
      if (beforeHash !== input.expectedMappingsSha256) {
        throw new TemplateTwinLifecycleError(
          'CONFLICT',
          'This mapping draft changed in another tab. Reload before saving.',
        );
      }

      const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
      const fieldById = new Map(ir.fields.map((field) => [field.fieldId, field]));
      const parsed = input.mappings.map((mapping) => SemanticMappingSchema.parse(mapping));
      const byId = new Map<string, SemanticMapping>();
      for (const mapping of parsed) {
        if (byId.has(mapping.fieldId)) {
          throw new TemplateTwinLifecycleError(
            'FIELD_SET_MISMATCH',
            'A field has more than one mapping.',
          );
        }
        byId.set(mapping.fieldId, mapping);
      }
      if (
        byId.size !== fieldById.size ||
        [...byId.keys()].some((fieldId) => !fieldById.has(fieldId))
      ) {
        throw new TemplateTwinLifecycleError(
          'FIELD_SET_MISMATCH',
          'Mappings must preserve the exact compiler field set.',
        );
      }

      for (const mapping of parsed) {
        const field = fieldById.get(mapping.fieldId)!;
        if (
          mapping.clinicalConcept !== null &&
          !isSupportedTemplateTwinConcept(mapping.clinicalConcept)
        ) {
          throw new TemplateTwinLifecycleError(
            'UNSUPPORTED_CLINICAL_CONCEPT',
            `${TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE}: ${TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_REASON}`,
          );
        }
        if (
          mapping.status === 'unsupported' ||
          !isMappingTypeCompatible(field, mapping) ||
          !validPracticeDefault(field, mapping) ||
          (mapping.status === 'certified' && !mapping.clinicalConcept)
        ) {
          throw new TemplateTwinLifecycleError(
            'MAPPING_INVALID',
            `The approved mapping for field ${field.displayOrder + 1} is incomplete or incompatible.`,
          );
        }
      }

      const afterHash = templateTwinMappingsSha256(parsed);
      if (afterHash === beforeHash) return;

      const persistedByFieldId = new Map(
        compiled.fields.map((field) => [field.fieldId, field]),
      );
      for (const mapping of parsed) {
        const persisted = persistedByFieldId.get(mapping.fieldId);
        if (!persisted?.mapping) {
          throw new TemplateTwinLifecycleError(
            'FIELD_SET_MISMATCH',
            'A compiled field has no persisted mapping.',
          );
        }
        const approved = mapping.status === 'certified';
        await tx.templateTwinSemanticMapping.update({
          where: { id: persisted.mapping.id },
          data: {
            clinicalConcept: mapping.clinicalConcept,
            expectedDataType: mapping.expectedDataType,
            polarityBehavior: mapping.polarityBehavior,
            temporality: mapping.temporality,
            laterality: mapping.laterality,
            unitPolicy: mapping.unitPolicy,
            approvedSynonyms: asJson(mapping.approvedSynonyms),
            required: mapping.required,
            blankPolicy: mapping.blankPolicy,
            unknownPolicy: mapping.unknownPolicy,
            practiceDefault: mapping.practiceDefault,
            mappingStatus: dbStatus(mapping.status),
            approvedById: approved ? input.actor.userId : null,
            approvedAt: approved ? new Date() : null,
          },
        });
      }

      // A mapping change invalidates the prior synthetic proof. The immutable
      // output object remains private; no deletion is attempted from this path.
      await tx.templateTwinCompiledVersion.update({
        where: { id: compiled.id },
        data: {
          certificationStatus:
            compiled.blockingUnsupportedCount > 0
              ? 'UNSUPPORTED'
              : 'NEEDS_CONFIRMATION',
          latestSyntheticTestManifest: Prisma.DbNull,
          latestTestMappingsSha256: null,
          latestTestOutputObjectKey: null,
          latestTestOutputVersionId: null,
          latestTestOutputEtag: null,
          latestTestOutputSha256: null,
          latestTestStaticContentSha256: null,
          latestTestRoundTrip: Prisma.DbNull,
          latestTestVerifiedAt: null,
        },
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:mapping-updated:${compiled.id}:${afterHash}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: 'TEMPLATE_TWIN_MAPPING_UPDATED',
        targetType: 'TemplateTwinCompiledVersion',
        targetId: compiled.id,
        metadata: {
          templateVersion: template.version,
          mappingCount: parsed.length,
          certifiedMappingCount: parsed.filter(
            (mapping) => mapping.status === 'certified',
          ).length,
          mappingsSha256: afterHash,
        },
      });
    },
    { isolationLevel: 'Serializable' },
  );

  const workspace = await refreshedWorkspace(input.noteTemplateId, input.actor);
  return workspace;
}

export async function certifyAndActivateTemplateTwin(input: {
  noteTemplateId: string;
  actor: TemplateTwinActor;
  expectedMappingsSha256: string;
  /** Required by runtime callers. Omitting it fails closed for a certifiable
   * proof, preserving safe behavior for older direct service callers. */
  expectedSyntheticTestProvenanceSha256?: string;
  optionalFieldWaivers?: readonly { fieldId: string; reason: string }[];
}): Promise<TemplateTwinWorkspace> {
  await prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      const { template, compiled } = await loadOwnedCompilation(
        tx,
        input.noteTemplateId,
        input.actor,
      );
      if (compiled.certification) {
        if (compiled.certificationStatus === 'CERTIFIED') return;
        throw new TemplateTwinLifecycleError(
          'IMMUTABLE',
          'This certification record is immutable.',
        );
      }

      if (
        compiled.sourceArtifact.validationStatus !== 'accepted' ||
        !compiled.sourceArtifact.objectVersionId?.trim() ||
        !compiled.sourceArtifact.objectEtag?.trim()
      ) {
        throw new TemplateTwinLifecycleError(
          'CERTIFICATION_BLOCKED',
          TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_MESSAGE,
        );
      }
      let sourcePrivacyScanEvidenceSha256: string;
      try {
        sourcePrivacyScanEvidenceSha256 = assertTemplateTwinSourceProvenance({
          privacyScanEvidence: compiled.sourceArtifact.privacyScanEvidence,
          requireBinding: true,
          boundEvidenceSha256:
            templateTwinSyntheticProofSourceEvidenceSha256(
              compiled.latestTestRoundTrip,
            ),
        }).evidenceSha256;
      } catch {
        throw new TemplateTwinLifecycleError(
          'CERTIFICATION_BLOCKED',
          TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_MESSAGE,
        );
      }

      const mappings = currentMappings(compiled);
      const mappingHash = templateTwinMappingsSha256(mappings);
      if (mappingHash !== input.expectedMappingsSha256) {
        throw new TemplateTwinLifecycleError(
          'CONFLICT',
          'Mappings changed after the page loaded. Reload before certifying.',
        );
      }
      const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
      const syntheticManifest = TemplateTwinFillManifestSchema.safeParse(
        compiled.latestSyntheticTestManifest,
      );
      const syntheticResolutions = syntheticManifest.success
        ? new Map(
            syntheticManifest.data.fields.map((field) => [
              field.fieldId,
              field,
            ]),
          )
        : new Map();
      const mappingById = new Map(mappings.map((mapping) => [mapping.fieldId, mapping]));
      if (
        mappings.some(
          (mapping) =>
            mapping.clinicalConcept !== null &&
            !isSupportedTemplateTwinConcept(mapping.clinicalConcept),
        )
      ) {
        throw new TemplateTwinLifecycleError(
          'UNSUPPORTED_CLINICAL_CONCEPT',
          `${TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE}: ${TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_REASON}`,
        );
      }
      const fieldsReady = ir.fields.every((field) => {
        const mapping = mappingById.get(field.fieldId);
        return Boolean(
          mapping &&
            mapping.status === 'certified' &&
            mapping.clinicalConcept &&
            isMappingTypeCompatible(field, mapping) &&
            validPracticeDefault(field, mapping),
        );
      });
      const waiverTimestamp = new Date();
      const requestedWaivers = input.optionalFieldWaivers ?? [];
      const waiverEvidence = requestedWaivers.map((waiver) => ({
        fieldId: waiver.fieldId,
        mappingsSha256: mappingHash,
        waivedById: input.actor.userId,
        reason: waiver.reason.trim(),
        waivedAt: waiverTimestamp,
      }));
      const coverage = syntheticManifest.success
        ? evaluateTemplateTwinCertificationCoverage({
            fields: ir.fields,
            mappings,
            manifest: syntheticManifest.data,
            waivers: waiverEvidence,
            currentMappingsSha256: mappingHash,
            actorUserId: input.actor.userId,
          })
        : null;
      const proofReady = Boolean(
        syntheticManifest.success &&
        compiled.latestTestOutputSha256 &&
          compiled.latestTestStaticContentSha256 &&
          isVerifiedSyntheticProof({
            roundTrip: compiled.latestTestRoundTrip,
            sourceSha256: compiled.sourceArtifact.sha256,
            outputSha256: compiled.latestTestOutputSha256,
            staticContentSha256: compiled.latestTestStaticContentSha256,
            expectedStaticContentSha256: ir.staticContentSha256,
            expectedFields: ir.fields.map((field) => ({
              fieldId: field.fieldId,
              partName: field.rendererBinding.partName,
              bindingPath: field.rendererBinding.path,
              valueSha256: canonicalSha256({
                fieldId: field.fieldId,
                value: syntheticResolutions.get(field.fieldId)?.value,
              }),
              occurrences:
                field.rowPrototype &&
                Array.isArray(syntheticResolutions.get(field.fieldId)?.value)
                  ? (
                      syntheticResolutions.get(field.fieldId)!.value as unknown[]
                    ).length
                  : 1,
            })),
          }),
      );
      const outputArtifact = compiled.latestTestOutputObjectKey
        ? parseTemplateTwinArtifactKey(compiled.latestTestOutputObjectKey)
        : null;
      const testReady = Boolean(
        compiled.latestSyntheticTestManifest &&
          compiled.latestTestOutputObjectKey &&
          compiled.latestTestOutputVersionId &&
          compiled.latestTestOutputEtag &&
          compiled.latestTestOutputSha256 &&
          compiled.latestTestStaticContentSha256 &&
          compiled.latestTestVerifiedAt &&
          compiled.latestTestMappingsSha256 === mappingHash &&
          outputArtifact?.practiceId === input.actor.practiceId &&
          outputArtifact.kind === 'output' &&
          outputArtifact.sha256 === compiled.latestTestOutputSha256 &&
          isVerifiedSyntheticManifest({
            manifest: compiled.latestSyntheticTestManifest,
            outputObjectKey: compiled.latestTestOutputObjectKey,
            compiledVersionId: compiled.id,
            noteTemplateId: template.id,
            noteTemplateVersion: template.version,
            ir,
            mappings,
          }) &&
          proofReady,
      );
      if (
        !fieldsReady ||
        compiled.fields.length !== ir.fields.length ||
        compiled.blockingUnsupportedCount > 0 ||
        ir.unsupported.some((item) => item.blocksCertification) ||
        !coverage?.ready ||
        !testReady
      ) {
        const coverageIssue = coverage?.issues[0];
        throw new TemplateTwinLifecycleError(
          'CERTIFICATION_BLOCKED',
          coverageIssue
            ? `${coverageIssue.code}: ${coverageIssue.message}`
            : 'Confirm every field, clear blocking structure, and verify a synthetic DOCX using the current mappings.',
        );
      }

      const syntheticTestProvenanceSha256 =
        templateTwinSyntheticTestProvenanceSha256({
          compiledVersionId: compiled.id,
          latestSyntheticTestManifest: compiled.latestSyntheticTestManifest,
          latestTestMappingsSha256: compiled.latestTestMappingsSha256,
          latestTestOutputObjectKey: compiled.latestTestOutputObjectKey,
          latestTestOutputVersionId: compiled.latestTestOutputVersionId,
          latestTestOutputEtag: compiled.latestTestOutputEtag,
          latestTestOutputSha256: compiled.latestTestOutputSha256,
          latestTestStaticContentSha256:
            compiled.latestTestStaticContentSha256,
          latestTestRoundTrip: compiled.latestTestRoundTrip,
          latestTestVerifiedAt: compiled.latestTestVerifiedAt,
        });
      if (
        !syntheticTestProvenanceSha256 ||
        syntheticTestProvenanceSha256 !==
          input.expectedSyntheticTestProvenanceSha256
      ) {
        throw new TemplateTwinLifecycleError(
          'CONFLICT',
          'The synthetic test changed after it was reviewed. Review the latest test output and acknowledge it again before certifying.',
        );
      }

      const persistedFieldById = new Map(
        compiled.fields.map((field) => [field.fieldId, field]),
      );
      if (waiverEvidence.length > 0) {
        await tx.templateTwinFieldTestWaiver.createMany({
          data: waiverEvidence.map((waiver) => ({
            compiledVersionId: compiled.id,
            fieldDefinitionId: persistedFieldById.get(waiver.fieldId)!.id,
            fieldId: waiver.fieldId,
            mappingsSha256: waiver.mappingsSha256,
            waivedById: waiver.waivedById,
            reason: waiver.reason,
            waivedAt: waiverTimestamp,
          })),
        });
      }
      // All mutable rows are finalized before the append-only certification is
      // inserted; database triggers reject any subsequent changes.
      await tx.templateTwinFieldDefinition.updateMany({
        where: { compiledVersionId: compiled.id },
        data: { detectionStatus: 'CERTIFIED' },
      });
      await tx.templateTwinCompiledVersion.update({
        where: { id: compiled.id },
        data: { certificationStatus: 'CERTIFIED' },
      });
      await tx.noteTemplate.updateMany({
        where: {
          doctorId: input.actor.userId,
          encounterType: template.encounterType,
          status: 'active',
          NOT: { id: template.id },
        },
        data: { status: 'inactive' },
      });
      await tx.noteTemplate.update({
        where: { id: template.id },
        data: { status: 'active' },
      });
      await tx.templateTwinCertification.create({
        data: {
          compiledVersionId: compiled.id,
          certifiedById: input.actor.userId,
          compiledStructureSha256: ir.structureSha256,
          approvedMappingsSha256: mappingHash,
          sourcePrivacyScanEvidenceSha256,
          syntheticTestManifest:
            compiled.latestSyntheticTestManifest as Prisma.InputJsonValue,
          testOutputObjectKey: compiled.latestTestOutputObjectKey!,
          testOutputVersionId: compiled.latestTestOutputVersionId!,
          testOutputEtag: compiled.latestTestOutputEtag!,
          testOutputSha256: compiled.latestTestOutputSha256!,
        },
      });

      for (const waiver of waiverEvidence) {
        await enqueueTemplateTwinAudit(tx, {
          eventKey: `template-twin:field-test-waived:${compiled.id}:${waiver.fieldId}:${mappingHash}`,
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          actorEmailSnapshot: input.actor.userEmail,
          action: 'TEMPLATE_TWIN_FIELD_TEST_WAIVED',
          targetType: 'TemplateTwinFieldDefinition',
          targetId: persistedFieldById.get(waiver.fieldId)!.id,
          metadata: {
            compiledVersionId: compiled.id,
            fieldId: waiver.fieldId,
            mappingsSha256: mappingHash,
            templateVersion: template.version,
          },
        });
      }

      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:certified:${compiled.id}:${mappingHash}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: 'TEMPLATE_TWIN_CERTIFIED',
        targetType: 'TemplateTwinCompiledVersion',
        targetId: compiled.id,
        metadata: {
          templateVersion: template.version,
          compilerVersion: ir.compilerVersion,
          fieldCount: ir.fields.length,
          optionalFieldWaiverCount: waiverEvidence.length,
          sourcePrivacyScanEvidenceSha256,
          mappingsSha256: mappingHash,
          syntheticTestProvenanceSha256,
        },
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:activated:${template.id}:v${template.version}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: 'TEMPLATE_TWIN_ACTIVATED',
        targetType: 'NoteTemplate',
        targetId: template.id,
        metadata: {
          templateVersion: template.version,
          compiledVersionId: compiled.id,
          mappingsSha256: mappingHash,
        },
      });
    },
    { isolationLevel: 'Serializable' },
  );

  const workspace = await refreshedWorkspace(input.noteTemplateId, input.actor);
  return workspace;
}
