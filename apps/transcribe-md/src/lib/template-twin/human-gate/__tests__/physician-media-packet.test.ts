import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { compileTemplateDocx } from '../../../note-template-docx/compiler';
import {
  MEDIA_REVIEW_EVIDENCE_JSON_SCHEMA,
  PHYSICIAN_INTENT_DECISION_JSON_SCHEMA,
  buildWmIovPhysicianIntentManifest,
  createMediaReviewEvidenceFile,
  createPhysicianIntentDecisionFile,
  MediaReviewEvidencePayloadSchema,
  PhysicianIntentDecisionFileSchema,
  renderMediaReviewWorksheetHtml,
  renderPhysicianIntentWorksheetHtml,
  validateMediaReviewEvidenceFile,
  validatePhysicianIntentDecisionFile,
  type PhysicianIntentManifest,
  type PhysicianPlaceholderDecision,
} from '..';

const SOURCE_COMMIT = '0'.repeat(40);
const SYNTHETIC_SHA = 'a'.repeat(64);
const GENERATED_AT = '2026-07-16T22:00:00.000Z';

const WM_IOV_FIXTURE = resolve(
  process.cwd(),
  process.cwd().endsWith('/apps/transcribe-md')
    ? '../../WM IOV Template.docx'
    : 'WM IOV Template.docx',
);

let cachedManifest: PhysicianIntentManifest | undefined;
function fixtureManifest(): PhysicianIntentManifest {
  if (cachedManifest) return cachedManifest;
  const source = readFileSync(WM_IOV_FIXTURE);
  const ir = compileTemplateDocx(source);
  cachedManifest = buildWmIovPhysicianIntentManifest({
    ir,
    sourceCommit: SOURCE_COMMIT,
    sourceDocumentSha256: ir.source.sha256,
    generatedAtIso: GENERATED_AT,
  });
  return cachedManifest;
}

function staticDecisions(
  manifest: PhysicianIntentManifest,
): PhysicianPlaceholderDecision[] {
  return manifest.fields.map((field) => ({
    fieldId: field.fieldId,
    referenceNumber: field.referenceNumber,
    intent: 'intentionally_static' as const,
    reason: `Synthetic test-only static decision for ${field.referenceNumber}.`,
    signingConsequenceAcknowledged: true as const,
  }));
}

function physicianDecisionFile(
  manifest: PhysicianIntentManifest,
  decisions: PhysicianPlaceholderDecision[] = staticDecisions(manifest),
) {
  return createPhysicianIntentDecisionFile({
    contractVersion: 'template-twin-physician-intent-decision/1.0.0',
    sourceCommit: manifest.sourceCommit,
    sourceDocumentSha256: manifest.sourceDocumentSha256,
    manifestSha256: manifest.manifestSha256,
    reviewer: {
      name: 'Synthetic Physician',
      professionalRole: 'licensed_physician',
      jurisdiction: 'Synthetic Test Jurisdiction',
      licenseOrRegistrationReference: 'SYNTHETIC-TEST-ONLY',
    },
    reviewedAtIso: GENERATED_AT,
    attestation: {
      IAmTheLicensedPhysicianNamedAbove: true,
      IUsedSyntheticExamplesOnly: true,
      IReviewedEveryPlaceholderWithoutDelegatingClinicalJudgment: true,
      IUnderstandThisWorksheetDoesNotCertifyOrActivateTheTemplate: true,
      IUnderstandFormalAuthenticatedReviewIsStillRequired: true,
    },
    decisions,
  });
}

function mediaPayload() {
  return {
    contractVersion: 'template-twin-media-review-worksheet/1.0.0' as const,
    sourceCommit: SOURCE_COMMIT,
    authorizationEffect: 'none_authenticated_quillmd_workflow_required' as const,
    reviewer: {
      name: 'Synthetic Practice Administrator',
      professionalRole: 'authorized_practice_administrator' as const,
      practiceId: 'practice_synthetic_test',
      jurisdiction: 'Synthetic Test Jurisdiction',
    },
    reviewedAtIso: GENERATED_AT,
    assetMetadata: {
      practiceScopedSha256: SYNTHETIC_SHA,
      mimeType: 'image/png' as const,
      width: 32,
      height: 32,
      byteCount: 256,
      scannerVersion: 'synthetic-scanner/test-only',
      ocrEngineVersion: 'synthetic-ocr/test-only',
      ocrEvidenceSha256: 'b'.repeat(64),
      metadataEvidenceSha256: 'c'.repeat(64),
      privacyEvidenceSha256: 'd'.repeat(64),
      privacyScanResult: 'clear' as const,
    },
    retentionAndVersion: {
      currentAuthenticatedState: 'pending_review' as const,
      decisionVersion: 1,
      retentionPolicyStatus: 'confirmed' as const,
      retentionPolicyReference: 'SYNTHETIC-RETENTION-POLICY-TEST-ONLY',
    },
    checklist: {
      reusablePracticeLogoOrStaticAsset: true,
      containsPatientInformation: false,
      containsPatientOrPersonNamesOrIdentifiers: false,
      containsAuthorizedOrganizationOrPracticeName: true,
      containsPersonPhotographs: false,
      containsBarcodesOrMachineReadableIdentifiers: false,
      containsHiddenOrUnreviewedMetadata: false,
      organizationOwnsOrMayUseAsset: true,
    },
    recommendation: 'recommend_authenticated_approval' as const,
    reason: 'Synthetic test-only asset may proceed to authenticated review.',
    attestation: {
      IAmAuthorizedForThisPractice: true,
      IReviewedOnlyThroughTheApprovedLocalOrAuthenticatedWorkflow: true,
      IDidNotUploadTheAssetToGitHubOrCI: true,
      IUnderstandFounderApprovalIsNotClinicalOrPrivacyApproval: true,
      IUnderstandApprovalIsPracticeScoped: true,
      IUnderstandAnyByteChangeRequiresNewApproval: true,
      IConfirmedRetentionAndVersionStatusFromAuthenticatedWorkflow: true,
      IUnderstandRevocationBlocksNewCertificationButDoesNotAlterSignedDocuments: true,
      IUnderstandThisWorksheetCannotApproveTheAsset: true,
    },
  };
}

describe('Template Twin physician intent human-gate packet', () => {
  it('binds exactly the seven fixture placeholders without disclosing source text', () => {
    const source = readFileSync(WM_IOV_FIXTURE);
    const ir = compileTemplateDocx(source);
    const manifest = fixtureManifest();
    const placeholders = ir.fields
      .filter((field) => field.rendererBinding.bindingType === 'ordinary_placeholder')
      .sort(
        (left, right) =>
          left.displayOrder - right.displayOrder || left.fieldId.localeCompare(right.fieldId),
      );

    expect(manifest.fields).toHaveLength(7);
    expect(manifest.fields.map((field) => field.fieldId)).toEqual(
      placeholders.map((field) => field.fieldId),
    );
    expect(manifest.fields.map((field) => field.referenceNumber)).toEqual([
      'P-01',
      'P-02',
      'P-03',
      'P-04',
      'P-05',
      'P-06',
      'P-07',
    ]);
    const serialized = JSON.stringify(manifest);
    expect(serialized).not.toContain('originalLabel');
    expect(serialized).not.toContain('canonicalPath');
    expect(serialized).not.toContain('tokenText"');
    expect(
      placeholders.every((field) => !serialized.includes(field.originalLabel)),
    ).toBe(true);
    expect(
      manifest.fields.every(
        (field) =>
          field.sourceTextDisclosure === 'withheld_from_offline_packet' &&
          field.unansweredDecision.intent === null &&
          field.unansweredDecision.dataType === null,
      ),
    ).toBe(true);
  }, 60_000);

  it('is deterministic for the same immutable IR and source date', () => {
    const first = fixtureManifest();
    const second = buildWmIovPhysicianIntentManifest({
      ir: compileTemplateDocx(readFileSync(WM_IOV_FIXTURE)),
      sourceCommit: SOURCE_COMMIT,
      sourceDocumentSha256: first.sourceDocumentSha256,
      generatedAtIso: GENERATED_AT,
    });
    expect(second).toEqual(first);
  }, 60_000);

  it('validates complete physician evidence and separates unresolved readiness', () => {
    const manifest = fixtureManifest();
    expect(
      validatePhysicianIntentDecisionFile({
        manifest,
        decisionFile: physicianDecisionFile(manifest),
      }),
    ).toMatchObject({ status: 'PASS', blockerCodes: [] });

    const decisions = staticDecisions(manifest);
    decisions[3] = {
      fieldId: manifest.fields[3]!.fieldId,
      referenceNumber: manifest.fields[3]!.referenceNumber,
      intent: 'unresolved',
      reason: 'Synthetic test-only unresolved physician intent.',
      signingConsequenceAcknowledged: true,
    };
    expect(
      validatePhysicianIntentDecisionFile({
        manifest,
        decisionFile: physicianDecisionFile(manifest, decisions),
      }),
    ).toMatchObject({
      status: 'BLOCKED',
      blockerCodes: ['TT_HUMAN_GATE_UNRESOLVED'],
    });
  });

  it('rejects tampering, stale sources, duplicate fields, and founder-only review', () => {
    const manifest = fixtureManifest();
    const valid = physicianDecisionFile(manifest);
    const tampered = structuredClone(valid);
    tampered.payload.decisions[0] = {
      ...tampered.payload.decisions[0]!,
      reason: 'Synthetic test-only altered reason after hashing.',
    } as PhysicianPlaceholderDecision;
    expect(() =>
      validatePhysicianIntentDecisionFile({ manifest, decisionFile: tampered }),
    ).toThrow(/DECISION_HASH_MISMATCH/u);

    const stale = physicianDecisionFile(manifest);
    stale.payload.sourceCommit = '1'.repeat(40);
    const staleRehashed = createPhysicianIntentDecisionFile(stale.payload);
    expect(() =>
      validatePhysicianIntentDecisionFile({ manifest, decisionFile: staleRehashed }),
    ).toThrow(/SOURCE_MISMATCH/u);

    const duplicatedPayload = structuredClone(valid.payload);
    duplicatedPayload.decisions[1] = duplicatedPayload.decisions[0]!;
    expect(() =>
      validatePhysicianIntentDecisionFile({
        manifest,
        decisionFile: createPhysicianIntentDecisionFile(duplicatedPayload),
      }),
    ).toThrow(/DUPLICATE_DECISION/u);

    expect(() =>
      PhysicianIntentDecisionFileSchema.parse({
        ...valid,
        payload: {
          ...valid.payload,
          reviewer: { ...valid.payload.reviewer, professionalRole: 'founder' },
        },
      }),
    ).toThrow();
  });

  it('renders an offline worksheet with no preselected clinical decision', () => {
    const manifest = fixtureManifest();
    const html = renderPhysicianIntentWorksheetHtml(manifest);
    expect(html).toContain("connect-src 'none'");
    expect(html).toContain('Only a licensed physician');
    expect(html).toContain('does not certify or activate');
    expect(html).toContain('localStorage');
    expect(html).toContain("crypto.subtle.digest('SHA-256'");
    expect(html).toContain('window.print()');
    expect(html).not.toMatch(/<option[^>]*\sselected(?:\s|=|>)/iu);
    expect(html).not.toMatch(/<script[^>]+src=/iu);
    expect(html).not.toMatch(/\b(?:fetch|XMLHttpRequest|WebSocket|sendBeacon)\s*\(/u);
    const script = html.match(/<script>([\s\S]*)<\/script>/u)?.[1];
    expect(script).toBeDefined();
    expect(() => new Function(script!)).not.toThrow();
    const placeholders = compileTemplateDocx(readFileSync(WM_IOV_FIXTURE)).fields.filter(
      (field) => field.rendererBinding.bindingType === 'ordinary_placeholder',
    );
    expect(placeholders.every((field) => !html.includes(field.originalLabel))).toBe(true);
  }, 60_000);

  it('exports a strict Draft 2020-12 decision schema', () => {
    const schema = PHYSICIAN_INTENT_DECISION_JSON_SCHEMA as Record<string, unknown>;
    expect(schema.$schema).toBe('https://json-schema.org/draft/2020-12/schema');
    expect(JSON.stringify(schema)).toContain('additionalProperties');
    expect(JSON.stringify(schema)).toContain('licensed_physician');
    expect(JSON.stringify(schema)).toContain('minItems');
    expect(JSON.stringify(schema)).toContain('maxItems');
  });
});

describe('Template Twin practice media human-gate packet', () => {
  it('validates a practice-scoped worksheet but grants no approval effect', () => {
    const evidence = createMediaReviewEvidenceFile(mediaPayload());
    expect(
      validateMediaReviewEvidenceFile({
        expectedSourceCommit: SOURCE_COMMIT,
        evidenceFile: evidence,
      }),
    ).toEqual(evidence);
    expect(evidence.payload.authorizationEffect).toBe(
      'none_authenticated_quillmd_workflow_required',
    );
  });

  it('rejects unsafe approval recommendations, founder review, tampering, and stale commits', () => {
    const unsafe = mediaPayload();
    unsafe.checklist.containsPatientInformation = true;
    expect(() => MediaReviewEvidencePayloadSchema.parse(unsafe)).toThrow();

    expect(() =>
      MediaReviewEvidencePayloadSchema.parse({
        ...mediaPayload(),
        reviewer: { ...mediaPayload().reviewer, professionalRole: 'founder' },
      }),
    ).toThrow();

    const evidence = createMediaReviewEvidenceFile(mediaPayload());
    const tampered = structuredClone(evidence);
    tampered.payload.reason = 'Synthetic test-only reason changed after hashing.';
    expect(() =>
      validateMediaReviewEvidenceFile({
        expectedSourceCommit: SOURCE_COMMIT,
        evidenceFile: tampered,
      }),
    ).toThrow(/MEDIA_HASH_MISMATCH/u);
    expect(() =>
      validateMediaReviewEvidenceFile({
        expectedSourceCommit: '1'.repeat(40),
        evidenceFile: evidence,
      }),
    ).toThrow(/MEDIA_SOURCE_MISMATCH/u);
  });

  it('renders a no-network checklist with no image, upload, or approval authority', () => {
    const html = renderMediaReviewWorksheetHtml({ sourceCommit: SOURCE_COMMIT });
    expect(html).toContain("connect-src 'none'");
    expect(html).toContain("img-src 'none'");
    expect(html).toContain('This worksheet cannot approve media');
    expect(html).toContain('Founder approval alone is not clinical or privacy approval');
    expect(html).toContain('any byte change requires new review');
    expect(html).toContain('retention policy status');
    expect(html).toContain('authorized organization or practice name');
    expect(html).not.toMatch(/<input[^>]+type=["']file["']/iu);
    expect(html).not.toMatch(/<img\b/iu);
    expect(html).not.toMatch(/<script[^>]+src=/iu);
    expect(html).not.toMatch(/\b(?:fetch|XMLHttpRequest|WebSocket|sendBeacon)\s*\(/u);
    const script = html.match(/<script>([\s\S]*)<\/script>/u)?.[1];
    expect(script).toBeDefined();
    expect(() => new Function(script!)).not.toThrow();
  });

  it('exports a strict Draft 2020-12 evidence schema', () => {
    const schema = MEDIA_REVIEW_EVIDENCE_JSON_SCHEMA as Record<string, unknown>;
    expect(schema.$schema).toBe('https://json-schema.org/draft/2020-12/schema');
    expect(JSON.stringify(schema)).toContain('additionalProperties');
    expect(JSON.stringify(schema)).toContain('authorized_practice_administrator');
    expect(JSON.stringify(schema)).toContain(
      'none_authenticated_quillmd_workflow_required',
    );
  });
});
