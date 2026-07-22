import { beforeAll, describe, expect, it, vi } from 'vitest';

vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { canonicalSha256 } from '../canonical';
import { prepareTemplateTwinFill } from '../fill-engine';
import type {
  SemanticMapping,
  TemplateDocIR,
  TemplateTwinFillManifest,
} from '../ir';
import { templateTwinMappingsSha256 } from '../mapping-hash';
import {
  assessTemplateTwinSigning,
  type TemplateTwinSigningContext,
} from '../signing-gate';
import { DOCX_MIME_TYPE } from '../storage/keys';
import {
  buildTemplateTwinIntegrationFixture,
  factsForMode,
} from './integration-fixture';

const VALIDATION_NOW = '2026-07-15T12:00:00.000Z';

let baseContext: TemplateTwinSigningContext;

function persistedMapping(mapping: SemanticMapping) {
  return {
    clinicalConcept: mapping.clinicalConcept,
    expectedDataType: mapping.expectedDataType,
    polarityBehavior: mapping.polarityBehavior,
    temporality: mapping.temporality,
    laterality: mapping.laterality,
    unitPolicy: mapping.unitPolicy,
    approvedSynonyms: mapping.approvedSynonyms,
    required: mapping.required,
    blankPolicy: mapping.blankPolicy,
    unknownPolicy: mapping.unknownPolicy,
    practiceDefault: mapping.practiceDefault,
    mappingStatus: 'CERTIFIED',
    approvedById: 'doctor-1',
    approvedAt: new Date('2026-07-15T11:55:00.000Z'),
  };
}

beforeAll(async () => {
  const fixture = await buildTemplateTwinIntegrationFixture();
  const prepared = await prepareTemplateTwinFill({
    compiledVersionId: 'compiled-1',
    noteTemplateId: 'template-1',
    noteTemplateVersion: 1,
    ir: fixture.ir,
    mappings: fixture.mappings,
    facts: factsForMode('text'),
    certifiedFieldIds: fixture.ir.fields.map((field) => field.fieldId),
    source: fixture.source,
    resolverModelVersion: 'synthetic-model-v1',
    validationNow: VALIDATION_NOW,
  });
  if (!prepared.render) {
    throw new Error('Synthetic signing fixture did not produce a verified DOCX.');
  }

  const mappingsSha256 = templateTwinMappingsSha256(fixture.mappings);
  const outputSha256 = prepared.render.outputSha256;
  const outputObjectKey =
    `practices/practice-1/template-twin/outputs/visit-1/` +
    `${prepared.manifestSha256}/artifact-1/${outputSha256}.docx`;
  const certificationOutputObjectKey =
    `practices/practice-1/template-twin/outputs/synthetic-1/` +
    `${prepared.manifestSha256}/artifact-2/${outputSha256}.docx`;

  baseContext = {
    visitId: 'visit-1',
    practiceId: 'practice-1',
    visitStatus: 'READY',
    noteTemplateId: 'template-1',
    noteTemplateVersion: 1,
    noteTemplate: {
      id: 'template-1',
      version: 1,
      templateKind: 'template_twin_docx',
      templateTwinCompiledVersion: {
        id: 'compiled-1',
        noteTemplateId: 'template-1',
        compilerVersion: fixture.ir.compilerVersion,
        irSchemaVersion: fixture.ir.irSchemaVersion,
        compiledDocumentIr: fixture.ir,
        structureSha256: fixture.ir.structureSha256,
        staticContentSha256: fixture.ir.staticContentSha256,
        certificationStatus: 'CERTIFIED',
        sourceArtifact: {
          practiceId: 'practice-1',
          sha256: fixture.ir.source.sha256,
          mimeType: fixture.ir.source.mimeType,
          sizeBytes: fixture.ir.source.sizeBytes,
          validationStatus: 'accepted',
        },
        fields: fixture.ir.fields.map((field) => {
          const mapping = fixture.mappings.find(
            (candidate) => candidate.fieldId === field.fieldId,
          );
          if (!mapping) throw new Error('Synthetic mapping is missing.');
          return {
            fieldId: field.fieldId,
            detectionStatus: 'CERTIFIED',
            mapping: persistedMapping(mapping),
          };
        }),
        certification: {
          id: 'certification-1',
          compiledStructureSha256: fixture.ir.structureSha256,
          approvedMappingsSha256: mappingsSha256,
          testOutputObjectKey: certificationOutputObjectKey,
          testOutputSha256: outputSha256,
        },
      },
    },
    templateTwinFill: {
      id: 'fill-1',
      practiceId: 'practice-1',
      compiledVersionId: 'compiled-1',
      noteTemplateId: 'template-1',
      noteTemplateVersion: 1,
      compilerVersion: prepared.manifest.compilerVersion,
      resolverVersion: prepared.manifest.resolverVersion,
      resolverModelVersion: prepared.manifest.resolverModelVersion,
      rendererVersion: prepared.manifest.rendererVersion,
      status: 'VERIFIED',
      fillManifest: prepared.manifest,
      manifestVersion: prepared.manifest.manifestVersion,
      manifestSha256: prepared.manifestSha256,
      factSetSha256: prepared.factSetSha256,
      validationResult: prepared.manifest.validation,
      filledCount: prepared.manifest.counts.filled,
      needsReviewCount: prepared.manifest.counts.needsReview,
      notMentionedCount: prepared.manifest.counts.notMentioned,
      conflictCount: prepared.manifest.counts.conflicts,
      criticalUnresolvedCount: prepared.manifest.counts.criticalUnresolved,
      outputObjectKey,
      outputSha256,
      outputMimeType: DOCX_MIME_TYPE,
      outputSizeBytes: prepared.render.document.byteLength,
      staticContentSha256: fixture.ir.staticContentSha256,
      roundTripVerified: prepared.render.verification.verified,
      roundTripVerification: prepared.render.verification,
      signedDecisionAt: null,
      updatedAt: new Date('2026-07-15T12:04:00.000Z'),
    },
  };
});

function validContext(
  visitStatus: 'READY' | 'SIGNED' = 'READY',
): TemplateTwinSigningContext {
  const context = structuredClone(baseContext);
  context.visitStatus = visitStatus;
  context.templateTwinFill!.status =
    visitStatus === 'SIGNED' ? 'SIGNED' : 'VERIFIED';
  context.templateTwinFill!.signedDecisionAt =
    visitStatus === 'SIGNED'
      ? new Date('2026-07-15T12:05:00.000Z')
      : null;
  return context;
}

function manifestOf(context: TemplateTwinSigningContext) {
  return context.templateTwinFill!.fillManifest as TemplateTwinFillManifest;
}

function irOf(context: TemplateTwinSigningContext) {
  return context.noteTemplate!.templateTwinCompiledVersion!
    .compiledDocumentIr as TemplateDocIR;
}

describe('Template Twin server-side signing gate', () => {
  it('does not affect the existing structured-template path', () => {
    const result = assessTemplateTwinSigning({
      visitId: 'visit-1',
      practiceId: 'practice-1',
      visitStatus: 'READY',
      noteTemplateId: 'template-1',
      noteTemplateVersion: 3,
      noteTemplate: {
        id: 'template-1',
        version: 3,
        templateKind: 'structured',
      },
      templateTwinFill: null,
    });

    expect(result).toEqual({
      applies: false,
      ready: true,
      blockerCodes: [],
      compiledVersionId: null,
      fillManifestId: null,
      claim: null,
    });
  });

  it('authorizes a certified, independently reproduced, round-trip verified fill', () => {
    const result = assessTemplateTwinSigning(validContext());

    expect(result.applies).toBe(true);
    expect(result.ready).toBe(true);
    expect(result.blockerCodes).toEqual([]);
    expect(result.claim).toEqual({
      id: 'fill-1',
      manifestVersion: 1,
      manifestSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
      outputSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
      updatedAt: new Date('2026-07-15T12:04:00.000Z'),
    });
  });

  it('accepts an already-signed immutable manifest for re-delivery', () => {
    const result = assessTemplateTwinSigning(validContext('SIGNED'));

    expect(result.ready).toBe(true);
    expect(result.claim).not.toBeNull();
  });

  it('fails closed when certification or template provenance drifts', () => {
    const input = validContext();
    input.noteTemplate!.templateTwinCompiledVersion!.certificationStatus =
      'NEEDS_CONFIRMATION';
    input.noteTemplate!.version = 2;

    const result = assessTemplateTwinSigning(input);

    expect(result.ready).toBe(false);
    expect(result.blockerCodes).toEqual(
      expect.arrayContaining([
        'TEMPLATE_VERSION_MISMATCH',
        'TEMPLATE_NOT_CERTIFIED',
      ]),
    );
    expect(result.claim).toBeNull();
  });

  it.each(['mapping', 'structure', 'source', 'static', 'compiler'] as const)(
    'binds certification to the exact %s provenance',
    (drift) => {
      const input = validContext();
      const compiled = input.noteTemplate!.templateTwinCompiledVersion!;
      switch (drift) {
        case 'mapping':
          compiled.fields[0]!.mapping!.clinicalConcept = 'tampered.concept';
          break;
        case 'structure':
          compiled.structureSha256 = '0'.repeat(64);
          break;
        case 'source':
          compiled.sourceArtifact.sha256 = '0'.repeat(64);
          break;
        case 'static':
          compiled.staticContentSha256 = '0'.repeat(64);
          break;
        case 'compiler':
          compiled.compilerVersion = 'tampered-compiler/1.0.0';
          break;
      }

      const result = assessTemplateTwinSigning(input);

      expect(result.ready).toBe(false);
      expect(result.blockerCodes).toContain('CERTIFICATION_INTEGRITY_FAILED');
    },
  );

  it('rejects a self-attested valid result when independent validation fails', () => {
    const input = validContext();
    const manifest = manifestOf(input);
    const selectField = irOf(input).fields.find(
      (field) => field.kind === 'single_select',
    )!;
    const resolution = manifest.fields.find(
      (field) => field.fieldId === selectField.fieldId,
    )!;
    resolution.value = 'not-a-certified-native-option';
    resolution.selectedOptionOrdinal = 0;

    // Keep every formerly trusted JSON/hash column internally consistent. The
    // only authority that detects this is a fresh validator run over the
    // certified IR and mapping rows.
    manifest.validation = {
      valid: true,
      issues: [],
      checkedAt: VALIDATION_NOW,
      validatorVersion: manifest.validation.validatorVersion,
    };
    input.templateTwinFill!.validationResult = structuredClone(
      manifest.validation,
    );
    input.templateTwinFill!.manifestSha256 = canonicalSha256(manifest);
    input.templateTwinFill!.outputObjectKey =
      `practices/practice-1/template-twin/outputs/visit-1/` +
      `${input.templateTwinFill!.manifestSha256}/artifact-1/` +
      `${input.templateTwinFill!.outputSha256}.docx`;
    const proof = input.templateTwinFill!.roundTripVerification as {
      fields: Array<{ fieldId: string; valueSha256: string }>;
    };
    proof.fields.find((field) => field.fieldId === selectField.fieldId)!
      .valueSha256 = canonicalSha256({
      fieldId: selectField.fieldId,
      value: resolution.value,
    });

    const result = assessTemplateTwinSigning(input);

    expect(result.ready).toBe(false);
    expect(result.blockerCodes).toContain('VALIDATION_FAILED');
    expect(result.claim).toBeNull();
  });

  it.each(['empty', 'subset'] as const)(
    'rejects %s round-trip field proof cardinality',
    (proofShape) => {
      const input = validContext();
      const proof = input.templateTwinFill!.roundTripVerification as {
        fields: unknown[];
      };
      proof.fields = proofShape === 'empty' ? [] : proof.fields.slice(0, -1);

      const result = assessTemplateTwinSigning(input);

      expect(result.ready).toBe(false);
      expect(result.blockerCodes).toContain('ROUND_TRIP_UNVERIFIED');
    },
  );

  it('binds every round-trip proof to the certified part and renderer path', () => {
    const input = validContext();
    const proof = input.templateTwinFill!.roundTripVerification as {
      fields: Array<{ bindingPath: string }>;
    };
    proof.fields[0]!.bindingPath = '/tampered/path[1]';

    const result = assessTemplateTwinSigning(input);

    expect(result.ready).toBe(false);
    expect(result.blockerCodes).toContain('ROUND_TRIP_UNVERIFIED');
  });

  it('rejects stale JSON, blocking validation, and unresolved critical fields', () => {
    const input = validContext();
    input.templateTwinFill!.manifestSha256 = '0'.repeat(64);
    input.templateTwinFill!.validationResult = {
      valid: false,
      issues: [
        {
          fieldId: null,
          code: 'FIELD_CONFLICT',
          severity: 'blocking',
          message: 'A conflict must be reviewed.',
        },
      ],
      checkedAt: VALIDATION_NOW,
      validatorVersion: 'template-twin-validator-v1',
    };
    input.templateTwinFill!.criticalUnresolvedCount = 1;

    const result = assessTemplateTwinSigning(input);

    expect(result.ready).toBe(false);
    expect(result.blockerCodes).toEqual(
      expect.arrayContaining([
        'FILL_MANIFEST_VERSION_MISMATCH',
        'VALIDATION_FAILED',
        'CRITICAL_FIELDS_UNRESOLVED',
        'OUTPUT_INTEGRITY_METADATA_INVALID',
      ]),
    );
  });

  it('rejects an unverified or cross-tenant output before signing', () => {
    const input = validContext();
    input.templateTwinFill!.outputObjectKey =
      input.templateTwinFill!.outputObjectKey!.replace(
        'practices/practice-1/',
        'practices/practice-2/',
      );
    input.templateTwinFill!.roundTripVerified = false;

    const result = assessTemplateTwinSigning(input);

    expect(result.ready).toBe(false);
    expect(result.blockerCodes).toEqual(
      expect.arrayContaining([
        'OUTPUT_INTEGRITY_METADATA_INVALID',
        'ROUND_TRIP_UNVERIFIED',
      ]),
    );
  });
});
