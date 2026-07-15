import prisma from '@meddoc/db';

import {
  SemanticMappingSchema,
  TemplateDocIRSchema,
  TemplateTwinFillManifestSchema,
  type SemanticMapping,
} from './ir';
import type {
  TemplateTwinWorkspace,
  TemplateTwinWorkspaceField,
} from './client-types';
import { templateTwinMappingsSha256 } from './mapping-hash';
import { templateTwinSyntheticTestProvenanceSha256 } from './synthetic-test-provenance';

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
    return {
      definitionId: dbField.id,
      field,
      mapping: parseMapping(dbField.mapping, field.fieldId),
    };
  });
  if (fields.length !== persistedRows.length) {
    throw new Error('Template Twin IR and persisted field definitions disagree');
  }

  const mappings = fields.map((field) => field.mapping);
  const mappingsSha256 = templateTwinMappingsSha256(mappings);
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
  const fieldCoverage = syntheticManifest.success
    ? syntheticManifest.data.fields.map((resolution) => ({
        fieldId: resolution.fieldId,
        exercised:
          resolution.value !== null &&
          (resolution.status === 'supported' ||
            resolution.status === 'explicitly_denied' ||
            resolution.status === 'approved_practice_default'),
        status: resolution.status,
      }))
    : [];

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
