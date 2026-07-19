import { readdirSync, readFileSync, statSync } from "node:fs";
import { basename, join } from "node:path";

import { describe, expect, expectTypeOf, it } from "vitest";

import type { OfficeRoundTripQaResult } from "./office-roundtrip-qa";
import type { TemplateDocxRoundTripVerification } from "./roundtrip-verify";
import {
  assessTemplateTwinSigning,
  type TemplateTwinSigningContext,
} from "../template-twin/signing-gate";

const APP_ROOT = process.cwd();
const SRC_ROOT = join(APP_ROOT, "src");
const QA_MODULE_PATTERN =
  /(?:from\s*|import\s*\(|require\s*\()\s*["'][^"']*(?:note-template-docx\/)?office-(?:docx-byte-readback|roundtrip-qa|schema-evidence)["']/g;
const QA_SYMBOL_PATTERN =
  /\b(?:verifyOfficeRoundTripQa|readOfficeSavedDocxFieldsQa|deriveOfficeVisibleStaticFromDocxBytesQa|evaluateOfficeSchemaEvidence|OfficeRoundTripQaResult|OfficeActualFieldReadbackManifest|OfficeSchemaQaResult|OFFICE_QA_EVIDENCE_CLASS|OFFICE_ROUNDTRIP_QA_CONTRACT_VERSION|OFFICE_FIELD_READBACK_QA_CONTRACT_VERSION|OFFICE_SCHEMA_QA_CONTRACT_VERSION)\b/g;
const QA_DEFINITION_FILES = new Set([
  "office-docx-byte-readback.ts",
  "office-roundtrip-qa.ts",
  "office-schema-evidence.ts",
]);

function sourceFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((name) => {
    const absolute = join(directory, name);
    const stats = statSync(absolute);
    if (stats.isDirectory()) {
      if (name === "__tests__") return [];
      return sourceFiles(absolute);
    }
    if (!/\.[cm]?[jt]sx?$/.test(name)) return [];
    if (/\.(?:test|spec)\.[cm]?[jt]sx?$/.test(name)) return [];
    if (QA_DEFINITION_FILES.has(basename(name))) return [];
    return [absolute];
  });
}

describe("Office compatibility QA import boundary", () => {
  it("is structurally incompatible with production readback-v2 signing proof", () => {
    expectTypeOf<OfficeRoundTripQaResult>().not.toMatchTypeOf<TemplateDocxRoundTripVerification>();
    expectTypeOf<TemplateDocxRoundTripVerification>().not.toMatchTypeOf<OfficeRoundTripQaResult>();
  });

  it("is absent from every production source import graph", () => {
    const violations = sourceFiles(SRC_ROOT).flatMap((absolute) => {
      const source = readFileSync(absolute, "utf8");
      return [
        ...[...source.matchAll(QA_MODULE_PATTERN)].map((match) => ({
          file: absolute.slice(APP_ROOT.length + 1),
          violation: match[0],
        })),
        ...[...source.matchAll(QA_SYMBOL_PATTERN)].map((match) => ({
          file: absolute.slice(APP_ROOT.length + 1),
          violation: match[0],
        })),
      ];
    });

    expect(violations).toEqual([]);
  });

  it("contains explicit non-production capability flags in both QA results", () => {
    const roundTripSource = readFileSync(
      join(SRC_ROOT, "lib/note-template-docx/office-roundtrip-qa.ts"),
      "utf8",
    );
    const schemaSource = readFileSync(
      join(SRC_ROOT, "lib/note-template-docx/office-schema-evidence.ts"),
      "utf8",
    );

    expect(roundTripSource).toContain("readonly signingEligible: false");
    expect(roundTripSource).toContain(
      "readonly mayReplaceProductionReadbackV2: false",
    );
    expect(roundTripSource).toContain("readonly mayAuthorizeSigning: false");
    expect(roundTripSource).toContain(
      "readonly mayAuthorizeExportOrDownload: false",
    );
    expect(schemaSource).toContain("readonly signingEligible: false");
    expect(schemaSource).toContain(
      "readonly productionStateTransitionEligible: false",
    );
  });

  it("fails closed when QA-only JSON is cast into a production signing proof", () => {
    const qaOnlyJson = {
      evidenceClass: "QA_ONLY_OFFICE_COMPATIBILITY_EVIDENCE",
      contractVersion: "template-twin-office-roundtrip-qa/2.0.0",
      qaOnly: true,
      signingEligible: false,
      mayAuthorizeSigning: false,
      status: "passed",
    };
    const context = {
      visitId: "synthetic-visit",
      practiceId: "synthetic-practice",
      visitStatus: "READY",
      noteTemplateId: "synthetic-template",
      noteTemplateVersion: 1,
      noteTemplate: {
        id: "synthetic-template",
        version: 1,
        templateKind: "template_twin_docx",
      },
      templateTwinFill: {
        id: "synthetic-fill",
        practiceId: "synthetic-practice",
        compiledVersionId: "synthetic-compiled",
        noteTemplateId: "synthetic-template",
        noteTemplateVersion: 1,
        compilerVersion: "synthetic",
        resolverVersion: "synthetic",
        resolverModelVersion: "synthetic",
        rendererVersion: "synthetic",
        status: "VERIFIED",
        fillManifest: {},
        manifestVersion: "synthetic",
        manifestSha256: "0".repeat(64),
        factSetSha256: "0".repeat(64),
        validationResult: {},
        filledCount: 0,
        needsReviewCount: 0,
        notMentionedCount: 0,
        conflictCount: 0,
        criticalUnresolvedCount: 0,
        outputObjectKey: null,
        outputVersionId: null,
        outputEtag: null,
        outputSha256: null,
        outputMimeType: null,
        outputSizeBytes: null,
        staticContentSha256: null,
        roundTripVerified: true,
        roundTripVerification: qaOnlyJson,
        pinnedGlobalRolloutGeneration: BigInt(1),
        pinnedPracticeRolloutGeneration: BigInt(1),
        signedGlobalRolloutGeneration: null,
        signedPracticeRolloutGeneration: null,
        reviewedAt: new Date("2026-07-16T00:00:00.000Z"),
        reviewedById: "synthetic-doctor",
        reviewedManifestVersion: "synthetic",
        reviewedManifestSha256: "0".repeat(64),
        signedDecisionAt: null,
        updatedAt: new Date("2026-07-16T00:00:00.000Z"),
      },
    } as unknown as TemplateTwinSigningContext;

    const assessment = assessTemplateTwinSigning(context);
    expect(assessment.ready).toBe(false);
    expect(assessment.claim).toBeNull();
    expect(assessment.blockerCodes).toContain("ROUND_TRIP_UNVERIFIED");
  });
});
