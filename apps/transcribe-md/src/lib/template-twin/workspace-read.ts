import prisma from '@meddoc/db';

import {
  SemanticMappingSchema,
  TemplateDocIRSchema,
  TemplateTwinFillManifestSchema,
  type SemanticMapping,
} from './ir';
import { deriveCustomConceptId } from './custom-concepts';
import {
  fieldRequiresExplicitIntent,
  parsePersistedFieldIntent,
  templateTwinFieldIntentsSha256,
  unresolvedFieldIntent,
  type PersistedTemplateTwinFieldIntent,
  type TemplateTwinFieldIntentView,
} from './field-intent';
import type {
  TemplateTwinWorkspace,
  TemplateTwinWorkspaceField,
} from './client-types';
import { templateTwinMappingsSha256 } from './mapping-hash';
import { templateTwinSyntheticTestProvenanceSha256 } from './synthetic-test-provenance';
import { readTemplateTwinCustomExampleCoverage } from './custom-example-service';

interface WorkspaceMappingRow {
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

interface WorkspaceFieldRow {
  id: string;
  fieldId: string;
  mapping: WorkspaceMappingRow | null;
  intentDecisions: Array<{
    id: string;
    version: number;
    intentKind: string;
    supportedConcept: string | null;
    customConceptId: string | null;
    customSpec: unknown;
    customSpecSha256: string | null;
    reason: string | null;
    decidedById: string;
    decidedAt: Date;
  }>;
}

function derivedNativeIntent(mapping: SemanticMapping): TemplateTwinFieldIntentView {
  return mapping.clinicalConcept === null
    ? unresolvedFieldIntent()
    : {
        intentKind: 'supported_concept',
        decisionId: null,
        version: null,
        supportedConcept: mapping.clinicalConcept,
        customConceptId: null,
        customSpec: null,
        reason: null,
        decidedAtIso: null,
        lockedInVersion: false,
      };
}

function lowerStatus(value: string): TemplateTwinWorkspace['template']['certificationStatus'] {
  return value.toLowerCase() as TemplateTwinWorkspace['template']['certificationStatus'];
}

function parseMapping(row: WorkspaceMappingRow, fieldId: string): SemanticMapping {
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

/** Doctor + practice scoped read model. Object keys and document text never
 * cross this boundary into the client. */
export async function readTemplateTwinWorkspace(input: {
  noteTemplateId: string;
  doctorId: string;
  practiceId: string;
}): Promise<TemplateTwinWorkspace | null> {
  const row = await prisma.noteTemplate.findFirst({
    where: {
      id: input.noteTemplateId,
      doctorId: input.doctorId,
      templateKind: 'template_twin_docx',
    },
    select: {
      id: true,
      lineageId: true,
      version: true,
      name: true,
      encounterType: true,
      status: true,
      templateTwinCompiledVersion: {
        select: {
          id: true,
          compilerVersion: true,
          compiledAt: true,
          compiledDocumentIr: true,
          certificationStatus: true,
          latestTestMappingsSha256: true,
          latestTestFieldIntentsSha256: true,
          latestSyntheticTestManifest: true,
          latestTestOutputObjectKey: true,
          latestTestOutputVersionId: true,
          latestTestOutputEtag: true,
          latestTestOutputSha256: true,
          latestTestStaticContentSha256: true,
          latestTestVerifiedAt: true,
          latestTestRoundTrip: true,
          sourceArtifact: {
            select: {
              practiceId: true,
              sha256: true,
              sizeBytes: true,
              mimeType: true,
            },
          },
          fields: {
            select: {
              id: true,
              fieldId: true,
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
  if (!row || !compiled || compiled.sourceArtifact.practiceId !== input.practiceId) {
    return null;
  }

  const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
  const persistedRows = compiled.fields as WorkspaceFieldRow[];
  const persisted = new Map<string, WorkspaceFieldRow>(
    persistedRows.map((field) => [field.fieldId, field]),
  );
  const fields: TemplateTwinWorkspaceField[] = ir.fields.map((field) => {
    const dbField = persisted.get(field.fieldId);
    if (!dbField?.mapping) {
      throw new Error('Template Twin mapping set is incomplete');
    }
    const mapping = parseMapping(dbField.mapping, field.fieldId);
    const explicitIntent = fieldRequiresExplicitIntent(field);
    // Prisma always materializes this selected relation as an array. A few
    // in-memory callers (and older serialized test doubles) can omit a
    // relation that did not exist when they were created. Treating that
    // omission as no decision is fail-closed for intent-bearing fields: they
    // remain unresolved and cannot certify. Fields that do not require an
    // explicit intent continue to derive their existing supported mapping.
    const persistedIntent = dbField.intentDecisions?.[0];
    const intent = explicitIntent
      ? persistedIntent
        ? parsePersistedFieldIntent({
            ...persistedIntent,
            fieldDefinitionId: dbField.id,
            fieldId: field.fieldId,
          } satisfies PersistedTemplateTwinFieldIntent)
        : unresolvedFieldIntent()
      : derivedNativeIntent(mapping);
    return {
      definitionId: dbField.id,
      field,
      mapping,
      intent,
      customConceptScaffold: explicitIntent
        ? {
            templateLineageId: row.lineageId,
            compiledVersionId: compiled.id,
            fieldId: field.fieldId,
            conceptId: deriveCustomConceptId({
              templateLineageId: row.lineageId,
              compiledVersionId: compiled.id,
              fieldId: field.fieldId,
            }),
          }
        : null,
    };
  });
  if (fields.length !== persistedRows.length) {
    throw new Error('Template Twin IR and persisted field definitions disagree');
  }

  const mappings = fields.map((field) => field.mapping);
  const mappingsSha256 = templateTwinMappingsSha256(mappings);
  const explicitIntentFields = fields
    .filter((item) => fieldRequiresExplicitIntent(item.field))
    .map((item) => ({ fieldId: item.field.fieldId, intent: item.intent }));
  const fieldIntentsSha256 = templateTwinFieldIntentsSha256(
    explicitIntentFields,
  );
  const roundTrip = compiled.latestTestRoundTrip as
    | { verified?: boolean; warningCodes?: unknown }
    | null;
  const layoutWarningCodes = Array.isArray(roundTrip?.warningCodes)
    ? roundTrip.warningCodes.filter(
        (code): code is string =>
          code === 'LAYOUT_OVERFLOW_REVIEW_RECOMMENDED' ||
          code === 'REPEATING_TABLE_LAYOUT_REVIEW_RECOMMENDED',
      )
    : [];
  const hasTest = Boolean(
    compiled.latestTestVerifiedAt &&
      compiled.latestTestOutputVersionId &&
      compiled.latestTestOutputEtag &&
      compiled.latestTestOutputSha256 &&
      compiled.latestTestMappingsSha256,
  );
  const syntheticTestProvenanceSha256 =
    templateTwinSyntheticTestProvenanceSha256({
      compiledVersionId: compiled.id,
      latestSyntheticTestManifest: compiled.latestSyntheticTestManifest,
      latestTestMappingsSha256: compiled.latestTestMappingsSha256,
      latestTestFieldIntentsSha256: compiled.latestTestFieldIntentsSha256,
      latestTestOutputObjectKey: compiled.latestTestOutputObjectKey,
      latestTestOutputVersionId: compiled.latestTestOutputVersionId,
      latestTestOutputEtag: compiled.latestTestOutputEtag,
      latestTestOutputSha256: compiled.latestTestOutputSha256,
      latestTestStaticContentSha256: compiled.latestTestStaticContentSha256,
      latestTestRoundTrip: compiled.latestTestRoundTrip,
      latestTestVerifiedAt: compiled.latestTestVerifiedAt,
    });
  const syntheticManifest = TemplateTwinFillManifestSchema.safeParse(
    compiled.latestSyntheticTestManifest,
  );
  const staticFieldIds = new Set(
    explicitIntentFields.flatMap((entry) =>
      entry.intent.intentKind === 'static' ? [entry.fieldId] : [],
    ),
  );
  const fieldCoverage = syntheticManifest.success
    ? syntheticManifest.data.fields.map((resolution) => ({
        fieldId: resolution.fieldId,
        exercised:
          staticFieldIds.has(resolution.fieldId) ||
          (resolution.value !== null &&
            (resolution.status === 'supported' ||
              resolution.status === 'explicitly_denied' ||
              resolution.status === 'approved_practice_default')),
        status: resolution.status,
      }))
    : [];
  const customExampleCoverage = await readTemplateTwinCustomExampleCoverage({
    noteTemplateId: row.id,
    doctorId: input.doctorId,
    practiceId: input.practiceId,
  });

  return {
    template: {
      id: row.id,
      lineageId: row.lineageId,
      version: row.version,
      name: row.name,
      encounterType: row.encounterType,
      status: row.status as 'draft' | 'active' | 'inactive',
      certificationStatus: lowerStatus(compiled.certificationStatus),
    },
    source: {
      sha256: compiled.sourceArtifact.sha256,
      sizeBytes: compiled.sourceArtifact.sizeBytes,
      mimeType: compiled.sourceArtifact.mimeType,
      compiledAtIso: compiled.compiledAt.toISOString(),
      compilerVersion: compiled.compilerVersion,
    },
    stats: ir.stats,
    fields,
    unsupported: ir.unsupported,
    mappingsSha256,
    fieldIntentsSha256,
    customExampleCoverage,
    latestSyntheticTest: hasTest && syntheticTestProvenanceSha256
      ? {
          provenanceSha256: syntheticTestProvenanceSha256,
          verifiedAtIso: compiled.latestTestVerifiedAt!.toISOString(),
          outputSha256: compiled.latestTestOutputSha256!,
          mappingsSha256: compiled.latestTestMappingsSha256!,
          roundTripVerified: roundTrip?.verified === true,
          layoutWarningCodes,
          fieldCoverage,
          downloadUrl: `/api/note-templates/template-twin/${encodeURIComponent(row.id)}/test-output`,
        }
      : null,
    canEdit: compiled.certificationStatus !== 'CERTIFIED',
  };
}
