import { createHash } from "node:crypto";

import { canonicalSha256 } from "../template-twin/canonical";

export const OFFICE_SCHEMA_REVIEW_REGISTRY_VERSION =
  "template-twin-libreoffice-schema-review/2.0.0" as const;

export const POST_LIBREOFFICE_SCHEMA_CONTRACT_VERSION =
  "template-twin-post-libreoffice-openxml-evidence/2.0.0" as const;

export const POST_LIBREOFFICE_OBSERVATION_SOURCE_COMMIT =
  "f16e7b48944d48d24fa768efefbc6a26159e1f09" as const;

export const POST_LIBREOFFICE_EXPECTED_PHYSICAL_FINDINGS = 32 as const;
export const POST_LIBREOFFICE_EXPECTED_TARGET_OBSERVATIONS = 64 as const;

export const POST_LIBREOFFICE_TARGETS = Object.freeze([
  "Office2013",
  "Microsoft365",
] as const);

export const POST_LIBREOFFICE_ARTIFACTS = Object.freeze([
  Object.freeze({
    caseId: "legacy-controls",
    filename: "legacy-controls.libreoffice-saved.docx",
    sha256: "029cc7c7bba667503658ed3a64b6ce9d9be323f8a8d3133be73c6880c6d650de",
    sizeBytes: 8_671,
  }),
  Object.freeze({
    caseId: "maximum-text",
    filename: "maximum-text.libreoffice-saved.docx",
    sha256: "c1f31f527774e182c26f127164561be6f41f2f79a579ca88b0d8448ebdbc6df1",
    sizeBytes: 8_541,
  }),
  Object.freeze({
    caseId: "modern-controls",
    filename: "modern-controls.libreoffice-saved.docx",
    sha256: "c71aef15eaf43eb6cbfb8c9fb6ae4a622f42bfbb270e55475d09326f9723b30d",
    sizeBytes: 9_133,
  }),
  Object.freeze({
    caseId: "ordinary-placeholder-token",
    filename: "ordinary-placeholder-token.libreoffice-saved.docx",
    sha256: "31435079f272b291aed1ae27151ca7d046cc2c367679ca7baca8b45403e974a1",
    sizeBytes: 8_356,
  }),
  Object.freeze({
    caseId: "tab-only-table-cell",
    filename: "tab-only-table-cell.libreoffice-saved.docx",
    sha256: "16c433dc73d4c6fbc3a0c99c840c1e91966d007d385188bb9185742f8754643f",
    sizeBytes: 8_991,
  }),
] as const);

export type ReviewedLibreOfficeFamilyCode =
  | "FONT_CHARACTER_SET_EXTENSION"
  | "LOGICAL_ALIGNMENT_ENUM"
  | "TABLE_ROW_ON_OFF_LEXICAL_VALUE"
  | "LIBREOFFICE_DOCGRID_CHARSPACE_UINT32_OVERFLOW";

export interface ReviewedLibreOfficeFindingSignature {
  readonly familyCode: ReviewedLibreOfficeFamilyCode;
  readonly validatorErrorId: "Sch_AttributeValueDataTypeDetailed";
  readonly errorType: "Schema";
  readonly description: string;
  readonly descriptionSha256: string;
  readonly classificationRationale: string;
  readonly classificationRationaleSha256: string;
  readonly partName: string;
  readonly path: string;
  readonly pathSha256: string;
  readonly elementQName: string;
  readonly attributeQName: string;
  readonly observedValue: string;
}

export interface ReviewedLibreOfficePhysicalFinding extends ReviewedLibreOfficeFindingSignature {
  readonly caseId: string;
  readonly artifactFilename: string;
  readonly findingId: string;
}

function sha256Text(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

const DESCRIPTIONS = Object.freeze({
  docGrid:
    "The attribute 'http://schemas.openxmlformats.org/wordprocessingml/2006/main:charSpace' has invalid value '4294963199'. The string '4294963199' is not a valid 'Int32' value.",
  utf8: "The attribute 'http://schemas.openxmlformats.org/wordprocessingml/2006/main:characterSet' has invalid value 'utf-8'. The Enumeration constraint failed.",
  windows1252:
    "The attribute 'http://schemas.openxmlformats.org/wordprocessingml/2006/main:characterSet' has invalid value 'windows-1252'. The Enumeration constraint failed.",
  start:
    "The attribute 'http://schemas.openxmlformats.org/wordprocessingml/2006/main:val' has invalid value 'start'. The Enumeration constraint failed.",
  trueValue:
    "The attribute 'http://schemas.openxmlformats.org/wordprocessingml/2006/main:val' has invalid value 'true'. The Enumeration constraint failed.",
});

const RATIONALES = Object.freeze({
  FONT_CHARACTER_SET_EXTENSION:
    "Pinned LibreOffice 25.8.7.3 emitted this exact font character-set extension after save. It remains schema-invalid, desktop-Word-pending, and ineligible for signing or reimport.",
  LOGICAL_ALIGNMENT_ENUM:
    "Pinned LibreOffice 25.8.7.3 emitted this exact logical-alignment value after save. It remains schema-invalid, desktop-Word-pending, and ineligible for signing or reimport.",
  TABLE_ROW_ON_OFF_LEXICAL_VALUE:
    "Pinned LibreOffice 25.8.7.3 emitted this exact table-row on/off lexical value after save. It remains schema-invalid, desktop-Word-pending, and ineligible for signing or reimport.",
  LIBREOFFICE_DOCGRID_CHARSPACE_UINT32_OVERFLOW:
    "Pinned LibreOffice 25.8.7.3 emitted this exact docGrid Int32-overflow serialization after save. It remains schema-invalid, desktop-Word-pending, and ineligible for signing or reimport.",
});

function signature(input: {
  readonly familyCode: ReviewedLibreOfficeFamilyCode;
  readonly description: string;
  readonly partName: string;
  readonly path: string;
  readonly elementQName: string;
  readonly attributeQName: string;
  readonly observedValue: string;
}): ReviewedLibreOfficeFindingSignature {
  const classificationRationale = RATIONALES[input.familyCode];
  return Object.freeze({
    familyCode: input.familyCode,
    validatorErrorId: "Sch_AttributeValueDataTypeDetailed" as const,
    errorType: "Schema" as const,
    description: input.description,
    descriptionSha256: sha256Text(input.description),
    classificationRationale,
    classificationRationaleSha256: sha256Text(classificationRationale),
    partName: input.partName,
    path: input.path,
    pathSha256: sha256Text(input.path),
    elementQName: input.elementQName,
    attributeQName: input.attributeQName,
    observedValue: input.observedValue,
  });
}

const DOC_GRID = signature({
  familyCode: "LIBREOFFICE_DOCGRID_CHARSPACE_UINT32_OVERFLOW",
  description: DESCRIPTIONS.docGrid,
  partName: "/word/document.xml",
  path: "/w:document[1]/w:body[1]/w:sectPr[1]/w:docGrid[1]",
  elementQName: "w:docGrid",
  attributeQName: "w:charSpace",
  observedValue: "4294963199",
});

const LOGICAL_ALIGNMENT = signature({
  familyCode: "LOGICAL_ALIGNMENT_ENUM",
  description: DESCRIPTIONS.start,
  partName: "/word/document.xml",
  path: "/w:document[1]/w:body[1]/w:tbl[1]/w:tblPr[1]/w:jc[1]",
  elementQName: "w:jc",
  attributeQName: "w:val",
  observedValue: "start",
});

const TABLE_ROW_ON_OFF = signature({
  familyCode: "TABLE_ROW_ON_OFF_LEXICAL_VALUE",
  description: DESCRIPTIONS.trueValue,
  partName: "/word/document.xml",
  path: "/w:document[1]/w:body[1]/w:tbl[1]/w:tr[1]/w:trPr[1]/w:cantSplit[1]",
  elementQName: "w:cantSplit",
  attributeQName: "w:val",
  observedValue: "true",
});

const FONT_CHARACTER_SETS = Object.freeze(
  [
    { index: 1, value: "windows-1252", description: DESCRIPTIONS.windows1252 },
    { index: 3, value: "windows-1252", description: DESCRIPTIONS.windows1252 },
    { index: 4, value: "utf-8", description: DESCRIPTIONS.utf8 },
    { index: 5, value: "utf-8", description: DESCRIPTIONS.utf8 },
    { index: 6, value: "utf-8", description: DESCRIPTIONS.utf8 },
  ].map(({ index, value, description }) =>
    signature({
      familyCode: "FONT_CHARACTER_SET_EXTENSION",
      description,
      partName: "/word/fontTable.xml",
      path: `/w:fonts[1]/w:font[${index}]/w:charset[1]`,
      elementQName: "w:charset",
      attributeQName: "w:characterSet",
      observedValue: value,
    }),
  ),
);

function findingsForArtifact(
  caseId: string,
): readonly ReviewedLibreOfficeFindingSignature[] {
  return Object.freeze([
    ...(caseId === "tab-only-table-cell" ? [] : [DOC_GRID]),
    ...(caseId === "modern-controls" || caseId === "tab-only-table-cell"
      ? [LOGICAL_ALIGNMENT]
      : []),
    ...(caseId === "tab-only-table-cell" ? [TABLE_ROW_ON_OFF] : []),
    ...FONT_CHARACTER_SETS,
  ]);
}

export const POST_LIBREOFFICE_REVIEWED_FINDINGS = Object.freeze(
  POST_LIBREOFFICE_ARTIFACTS.flatMap((artifact) =>
    findingsForArtifact(artifact.caseId).map((finding, index) =>
      Object.freeze({
        ...finding,
        caseId: artifact.caseId,
        artifactFilename: artifact.filename,
        findingId: `QMD-OFFICE-SCHEMA-${String(
          POST_LIBREOFFICE_ARTIFACTS.slice(
            0,
            POST_LIBREOFFICE_ARTIFACTS.indexOf(artifact),
          ).reduce(
            (count, previous) =>
              count + findingsForArtifact(previous.caseId).length,
            0,
          ) +
            index +
            1,
        ).padStart(3, "0")}`,
      }),
    ),
  ),
);

if (
  POST_LIBREOFFICE_REVIEWED_FINDINGS.length !==
  POST_LIBREOFFICE_EXPECTED_PHYSICAL_FINDINGS
) {
  throw new Error("POST_LIBREOFFICE_REVIEWED_FINDING_COUNT_DRIFT");
}

export const POST_LIBREOFFICE_OBSERVATION_PROVENANCE = Object.freeze({
  contractVersion: "template-twin-office-schema-observation/1.0.0" as const,
  observedSourceCommit: POST_LIBREOFFICE_OBSERVATION_SOURCE_COMMIT,
  evidenceOrigin:
    "fresh_pinned_openxml_rerun_over_exact_pinned_libreoffice_saved_bytes",
  approvalEffect: "none" as const,
  independentReviewStatus: "PENDING" as const,
  acceptedIndependentReviewRecordSha256: null,
  compatibilityEngineeringStatus:
    "PENDING_INDEPENDENT_EXACT_HEAD_REVIEW" as const,
  compatibilityEngineeringEligible: false as const,
  syntheticReviewerPackageGenerationEligible: true as const,
  desktopWordStatus: "PENDING" as const,
  physicalFindingCount: POST_LIBREOFFICE_EXPECTED_PHYSICAL_FINDINGS,
  targetObservationCount: POST_LIBREOFFICE_EXPECTED_TARGET_OBSERVATIONS,
});

export const POST_LIBREOFFICE_OBSERVATION_PROVENANCE_SHA256 = canonicalSha256(
  POST_LIBREOFFICE_OBSERVATION_PROVENANCE,
);

export const POST_LIBREOFFICE_OBSERVATION_REGISTRY = Object.freeze({
  contractVersion:
    "template-twin-office-schema-observation-registry/1.0.0" as const,
  registryVersion: OFFICE_SCHEMA_REVIEW_REGISTRY_VERSION,
  artifacts: POST_LIBREOFFICE_ARTIFACTS,
  findings: POST_LIBREOFFICE_REVIEWED_FINDINGS,
  provenance: POST_LIBREOFFICE_OBSERVATION_PROVENANCE,
});

export const POST_LIBREOFFICE_OBSERVATION_REGISTRY_SHA256 = canonicalSha256(
  POST_LIBREOFFICE_OBSERVATION_REGISTRY,
);

export function reviewedLibreOfficeSignatureKey(finding: {
  readonly validatorErrorId: string;
  readonly errorType: string;
  readonly description: string;
  readonly partName: string;
  readonly path: string;
}): string {
  return canonicalSha256({
    validatorErrorId: finding.validatorErrorId,
    errorType: finding.errorType,
    description: finding.description,
    partName: finding.partName,
    path: finding.path,
  });
}

export function findReviewedLibreOfficeSignature(input: {
  readonly validatorErrorId: string;
  readonly errorType?: string | null;
  readonly descriptionSha256: string;
  readonly classificationRationaleSha256: string | null;
  readonly partName: string | null;
  readonly pathSha256: string | null;
  readonly elementQName: string | null;
  readonly attributeQName: string | null;
  readonly observedValue: string | null;
  readonly familyCode: string | null;
}): ReviewedLibreOfficeFindingSignature | null {
  return (
    POST_LIBREOFFICE_REVIEWED_FINDINGS.find(
      (candidate) =>
        input.validatorErrorId === candidate.validatorErrorId &&
        (input.errorType === undefined ||
          input.errorType === null ||
          input.errorType === candidate.errorType) &&
        input.descriptionSha256 === candidate.descriptionSha256 &&
        input.classificationRationaleSha256 ===
          candidate.classificationRationaleSha256 &&
        input.partName === candidate.partName &&
        input.pathSha256 === candidate.pathSha256 &&
        input.elementQName === candidate.elementQName &&
        input.attributeQName === candidate.attributeQName &&
        input.observedValue === candidate.observedValue &&
        input.familyCode === candidate.familyCode,
    ) ?? null
  );
}

export function reviewedFindingsForArtifact(
  artifactFilename: string,
): readonly ReviewedLibreOfficePhysicalFinding[] {
  return POST_LIBREOFFICE_REVIEWED_FINDINGS.filter(
    (finding) => finding.artifactFilename === artifactFilename,
  );
}
