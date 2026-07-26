// ============================================================================
// Template Twin — physician CERTIFICATION lifecycle (Phase 2b). Mapping update +
// the ONE-TIME certify/activate. Binds the synthetic-test proof to the immutable
// compiled version and requires the saved mapping hash to still match (no
// test-then-edit activation). Authorization is supplied by the caller
// (TemplateTwinActor value-object); uses the prisma singleton + logTwinAudit only.
// ============================================================================
import { Prisma } from '@prisma/client';
import prisma from '@meddoc/db';

import { logTwinAudit as logAudit } from './twin-audit';

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

/** Minimum filled fields a synthetic proof must produce before a template may
 *  certify. Set from what the WM_IOV encounter legitimately supports; raise it
 *  as encounters get richer, never lower it to make a fixture pass. */
const MIN_CERTIFIED_FILLED_FIELDS = 10;

export class TemplateTwinLifecycleError extends Error {
  readonly code:
    | 'NOT_FOUND'
    | 'IMMUTABLE'
    | 'CONFLICT'
    | 'FIELD_SET_MISMATCH'
    | 'MAPPING_INVALID'
    | 'CERTIFICATION_BLOCKED';

  /** Per-condition detail for CERTIFICATION_BLOCKED. Field IDs and sha
   *  prefixes only — never option values or filled content. */
  readonly blockers: readonly string[];

  constructor(
    code: TemplateTwinLifecycleError['code'],
    message: string,
    detail?: { blockers?: readonly string[] },
  ) {
    super(message);
    this.name = 'TemplateTwinLifecycleError';
    this.code = code;
    this.blockers = detail?.blockers ?? [];
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
          latestTestOutputSha256: true,
          latestTestStaticContentSha256: true,
          latestTestRoundTrip: true,
          latestTestVerifiedAt: true,
          certification: { select: { id: true } },
          sourceArtifact: { select: { practiceId: true, sha256: true } },
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
      const { compiled } = await loadOwnedCompilation(
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
          mapping.status === 'unsupported' ||
          !isMappingTypeCompatible(field, mapping) ||
          !validPracticeDefault(field, mapping) ||
          // A MANUAL field carries no clinical concept because there is no
          // evidence to cite — it is a per-visit human value that renders
          // BLANK. Confirming its CLASSIFICATION is what the doctor is
          // approving, not a concept. Same carve-out as fieldsReady, and it can
          // never produce a value, so no evidence rule is relaxed.
          (mapping.status === 'certified' &&
            !mapping.clinicalConcept &&
            mapping.sourceType !== 'manual')
        ) {
          throw new TemplateTwinLifecycleError(
            'MAPPING_INVALID',
            `The approved mapping for field ${field.displayOrder + 1} is incomplete or incompatible.`,
          );
        }
      }

      // ── PRACTICE-DEFAULT LAW ─────────────────────────────────────────────
      // A practice default is a standing clinical assertion: at visit time
      // withApprovedPracticeDefaultFacts injects it as an EncounterFact with
      // quality.evidence 'direct', and a VALID one then renders as an ordinary
      // populated value. Validation is rigorous about its PROVENANCE
      // (PRACTICE_DEFAULT_INVALID checks fact id, anchor, exact value, null
      // offsets) but nothing routes it to a flagged / set-aside lane — so it
      // can put content the clinician never said into a signed note,
      // distinguishable only by sourceType inside the manifest.
      //
      // Until that flagged-review lane exists, nothing may set one. This is a
      // hard refusal rather than a silent coercion to null: quietly dropping
      // the value would leave the caller believing a default was stored, which
      // is the same class of silence the rest of this system just retired.
      //
      // Lifting this: build the lane (default-sourced resolutions ride the
      // existing set-aside / adopt-before-sign surface), THEN delete this
      // block. Do not delete it to make a fixture certify.
      const withDefaults = parsed.filter((mapping) => mapping.practiceDefault !== null);
      if (withDefaults.length > 0) {
        const ids = withDefaults.map((mapping) => mapping.fieldId);
        console.warn(
          `[template-twin:mappings] REFUSED practice default on ${ids.length} field(s): ${ids.slice(0, 10).join(',')}`,
        );
        throw new TemplateTwinLifecycleError(
          'MAPPING_INVALID',
          'Practice defaults are not available yet: a standing default would put content the clinician never said into a signed note, and the flagged-review lane for that is not built. Leave the field blank or confirm it per visit.',
        );
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
          latestTestOutputSha256: null,
          latestTestStaticContentSha256: null,
          latestTestRoundTrip: Prisma.DbNull,
          latestTestVerifiedAt: null,
        },
      });
    },
    { isolationLevel: 'Serializable' },
  );

  const workspace = await refreshedWorkspace(input.noteTemplateId, input.actor);
  await logAudit({
    action: 'TEMPLATE_TWIN_MAPPING_UPDATED',
    targetType: 'TemplateTwinCompiledVersion',
    targetId: input.noteTemplateId,
    userId: input.actor.userId,
    userEmail: input.actor.userEmail,
    practiceId: input.actor.practiceId,
    metadata: {
      templateVersion: workspace.template.version,
      mappingCount: workspace.fields.length,
      certifiedMappingCount: workspace.fields.filter(
        (field) => field.mapping.status === 'certified',
      ).length,
      mappingsSha256: workspace.mappingsSha256,
    },
  });
  return workspace;
}

export async function certifyAndActivateTemplateTwin(input: {
  noteTemplateId: string;
  actor: TemplateTwinActor;
  expectedMappingsSha256: string;
}): Promise<TemplateTwinWorkspace> {
  let compiledId = '';
  await prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      const { template, compiled } = await loadOwnedCompilation(
        tx,
        input.noteTemplateId,
        input.actor,
      );
      compiledId = compiled.id;
      if (compiled.certification) {
        if (compiled.certificationStatus === 'CERTIFIED') return;
        throw new TemplateTwinLifecycleError(
          'IMMUTABLE',
          'This certification record is immutable.',
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
      const fieldsReady = ir.fields.every((field) => {
        const mapping = mappingById.get(field.fieldId);
        if (!mapping) return false;
        // A MANUAL field is a per-visit human value nobody can know — the
        // technologist on shift. It carries no clinical concept because there
        // is no evidence to cite, and it renders BLANK. Requiring a concept
        // there would block certification on a field that is behaving
        // correctly, so it is attested instead: the same mechanism
        // needs-clinician-input already uses, applied narrowly by CLASS.
        // Nothing about it can produce a value, so no evidence rule is relaxed.
        if (mapping.sourceType === 'manual') {
          return mapping.status === 'certified' && isMappingTypeCompatible(field, mapping);
        }
        return Boolean(
          mapping.status === 'certified' &&
            mapping.clinicalConcept &&
            isMappingTypeCompatible(field, mapping) &&
            validPracticeDefault(field, mapping),
        );
      });
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
      // ── Gate transparency ────────────────────────────────────────────────
      // This gate refused certification without saying which of its five
      // conditions failed, and `testReady` alone is a nine-clause conjunction.
      // Debugging it meant re-deriving the whole thing by hand against the
      // database. A safety gate is allowed to say no; it is not allowed to say
      // no anonymously — that is the last silent thing in this system.
      //
      // Reasons name field IDs and sha prefixes only. No option values, no
      // filled content, no encounter text: a certification blocker must be
      // diagnosable from logs without those logs becoming a PHI surface.
      const unreadyFieldIds = ir.fields
        .filter((field) => {
          const mapping = mappingById.get(field.fieldId);
          if (!mapping) return true;
          if (mapping.sourceType === 'manual') {
            return !(mapping.status === 'certified' && isMappingTypeCompatible(field, mapping));
          }
          return !(
            mapping.status === 'certified' &&
            mapping.clinicalConcept &&
            isMappingTypeCompatible(field, mapping) &&
            validPracticeDefault(field, mapping)
          );
        })
        .map((field) => field.fieldId);

      const blockers: string[] = [];
      if (!fieldsReady) {
        blockers.push(
          `fieldsReady=false (${unreadyFieldIds.length}/${ir.fields.length} unready: ` +
            `${unreadyFieldIds.slice(0, 10).join(',')}${unreadyFieldIds.length > 10 ? ',…' : ''})`,
        );
      }
      if (compiled.fields.length !== ir.fields.length) {
        blockers.push(`fieldCount storedjson=${compiled.fields.length} ir=${ir.fields.length}`);
      }
      if (compiled.blockingUnsupportedCount > 0) {
        blockers.push(`blockingUnsupportedCount=${compiled.blockingUnsupportedCount}`);
      }
      const blockingIr = ir.unsupported.filter((item) => item.blocksCertification);
      if (blockingIr.length > 0) {
        blockers.push(`irBlockingUnsupported=${blockingIr.length}`);
      }
      if (!testReady) {
        // Each clause of testReady, individually, so the nine-way conjunction
        // never has to be re-derived by hand again.
        const t: Record<string, boolean> = {
          manifest: Boolean(compiled.latestSyntheticTestManifest),
          outputKey: Boolean(compiled.latestTestOutputObjectKey),
          outputSha: Boolean(compiled.latestTestOutputSha256),
          staticSha: Boolean(compiled.latestTestStaticContentSha256),
          verifiedAt: Boolean(compiled.latestTestVerifiedAt),
          mappingsShaMatch: compiled.latestTestMappingsSha256 === mappingHash,
          artifactPractice: outputArtifact?.practiceId === input.actor.practiceId,
          artifactKind: outputArtifact?.kind === 'output',
          artifactShaMatch: outputArtifact?.sha256 === compiled.latestTestOutputSha256,
          proofReady,
        };
        const failed = Object.entries(t)
          .filter(([, ok]) => !ok)
          .map(([name]) => name);
        blockers.push(
          `testReady=false (failed: ${failed.join(',') || 'verifiedManifest'}; ` +
            `testMappingsSha=${String(compiled.latestTestMappingsSha256).slice(0, 12)} ` +
            `currentMappingsSha=${mappingHash.slice(0, 12)})`,
        );
      }

      // ── BLANK-VERIFICATION INVARIANT ─────────────────────────────────────
      // At least one field must be proven BLANK. The synthetic encounter
      // deliberately leaves fields unmentioned, so a run with zero blank
      // entries means blank behaviour was never exercised — and a certificate
      // that only ever attests fills would let the honest-blank path rot
      // unnoticed. This ADDS a requirement; nothing is relaxed.
      const roundTripFields = isRecord(compiled.latestTestRoundTrip)
        ? (compiled.latestTestRoundTrip.fields as unknown[]) ?? []
        : [];
      const blankProofCount = roundTripFields.filter(
        (entry) => isRecord(entry) && entry.kind === 'blank',
      ).length;
      // ── FILL-COVERAGE INVARIANT ──────────────────────────────────────────
      // A template must not certify with a dead fill path. WM_IOV certified
      // cleanly while the visit-time fill produced filledCount=0 — the
      // certificate attested a template whose measurements never landed,
      // because the synthetic proof exercised almost nothing.
      //
      // So: the synthetic encounter must produce a REALISTIC fill — enough
      // filled fields, and at least one measurement CELL, which is the path
      // that was silently broken. Both counts come from what the WM_IOV
      // encounter legitimately supports; neither relaxes anything.
      const filledResolutions = [...syntheticResolutions.values()].filter(
        (r) => r != null && r.value !== null,
      );
      const cellFieldIds = new Set(
        ir.fields.filter((f) => f.rendererBinding.bindingType === 'table_cell').map((f) => f.fieldId),
      );
      const filledCellCount = [...syntheticResolutions.entries()].filter(
        ([fieldId, r]) => cellFieldIds.has(fieldId) && r != null && r.value !== null,
      ).length;
      if (testReady && filledResolutions.length < MIN_CERTIFIED_FILLED_FIELDS) {
        blockers.push(
          `fillCoverage=false (${filledResolutions.length} filled, need >= ${MIN_CERTIFIED_FILLED_FIELDS} — ` +
            'the synthetic encounter must exercise a realistic fill, or the certificate ' +
            'attests a template whose fill path is dead)',
        );
      }
      if (testReady && cellFieldIds.size > 0 && filledCellCount === 0) {
        blockers.push(
          'fillCoverage=false (no measurement CELL was filled — that is the path ' +
            'that silently produced empty documents; a template with table cells must ' +
            'prove at least one)',
        );
      }

      if (testReady && blankProofCount === 0) {
        blockers.push(
          'blankVerification=false (no field was proven blank — the synthetic ' +
            'encounter must leave something unmentioned so blank behaviour is verified)',
        );
      }

      if (blockers.length > 0) {
        console.warn(
          `[template-twin:certify] BLOCKED compiled=${compiled.id} template=${template.id}: ${blockers.join(' | ')}`,
        );
        throw new TemplateTwinLifecycleError(
          'CERTIFICATION_BLOCKED',
          'Confirm every field, clear blocking structure, and verify a synthetic DOCX using the current mappings.',
          // Machine-readable detail for the workspace UI and for callers; the
          // human-facing message above is unchanged.
          { blockers },
        );
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
          syntheticTestManifest:
            compiled.latestSyntheticTestManifest as Prisma.InputJsonValue,
          testOutputObjectKey: compiled.latestTestOutputObjectKey!,
          testOutputSha256: compiled.latestTestOutputSha256!,
        },
      });
    },
    { isolationLevel: 'Serializable' },
  );

  const workspace = await refreshedWorkspace(input.noteTemplateId, input.actor);
  await Promise.all([
    logAudit({
      action: 'TEMPLATE_TWIN_CERTIFIED',
      targetType: 'TemplateTwinCompiledVersion',
      targetId: compiledId,
      userId: input.actor.userId,
      userEmail: input.actor.userEmail,
      practiceId: input.actor.practiceId,
      metadata: {
        templateVersion: workspace.template.version,
        compilerVersion: workspace.source.compilerVersion,
        fieldCount: workspace.stats.totalFields,
        mappingsSha256: workspace.mappingsSha256,
      },
    }),
    logAudit({
      action: 'TEMPLATE_TWIN_ACTIVATED',
      targetType: 'NoteTemplate',
      targetId: input.noteTemplateId,
      userId: input.actor.userId,
      userEmail: input.actor.userEmail,
      practiceId: input.actor.practiceId,
      metadata: {
        templateVersion: workspace.template.version,
        encounterType: workspace.template.encounterType,
      },
    }),
  ]);
  return workspace;
}
