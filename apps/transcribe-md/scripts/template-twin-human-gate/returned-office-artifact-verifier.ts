import { createHash } from "node:crypto";

import { getDocumentProxy } from "unpdf";

import {
  buildOfficeVisibleStaticManifestFromDocxBytes,
  compareOfficeVisibleStaticManifests,
  inspectOfficeDocxSecurityQa,
} from "../../src/lib/note-template-docx/office-roundtrip-qa";
import {
  readOfficeSavedDocxFieldsQa,
  validActualManifest,
  validExpectedManifest,
  type OfficeExpectedValueManifest,
} from "../../src/lib/note-template-docx/office-docx-byte-readback";
import type {
  ReturnedOfficeArtifactVerification,
  ReturnedOfficeArtifactVerifierInput,
} from "../../src/lib/template-twin/human-release-gate/evidence-validator";

const PDF_PARSE_TIMEOUT_MS = 15_000;

function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function parseExpectedManifest(
  input: ReturnedOfficeArtifactVerifierInput,
): OfficeExpectedValueManifest | null {
  try {
    if (
      input.expectedManifestBytes.byteLength !==
        input.expectedManifestSizeBytes ||
      sha256(input.expectedManifestBytes) !== input.expectedManifestSha256
    ) {
      return null;
    }
    const parsed = JSON.parse(
      Buffer.from(input.expectedManifestBytes)
        .toString("utf8")
        .replace(/^\uFEFF/u, ""),
    ) as OfficeExpectedValueManifest;
    if (!validExpectedManifest(parsed)) return null;
    const identityMatches =
      input.documentRole === "source"
        ? parsed.sourceDocxSha256 === input.expectedDocumentSha256
        : parsed.rendererOutputDocxSha256 === input.expectedDocumentSha256 &&
          parsed.rendererOutputSizeBytes === input.expectedDocumentSizeBytes;
    return identityMatches ? parsed : null;
  } catch {
    return null;
  }
}

async function validWordExportedPdf(
  bytes: Uint8Array,
  expectedPageCount: number,
): Promise<boolean> {
  if (
    !Buffer.from(bytes).subarray(0, 5).equals(Buffer.from("%PDF-")) ||
    /\/(?:AA|EmbeddedFile|JavaScript|JS|Launch|OpenAction)\b/u.test(
      Buffer.from(bytes).toString("latin1"),
    )
  ) {
    return false;
  }
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const pdf = await Promise.race([
      getDocumentProxy(new Uint8Array(bytes)),
      new Promise<never>((_, reject) => {
        timer = setTimeout(
          () => reject(new Error("PDF parse timed out.")),
          PDF_PARSE_TIMEOUT_MS,
        );
      }),
    ]);
    const valid = pdf.numPages === expectedPageCount;
    await pdf.destroy();
    return valid;
  } catch {
    return false;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

/**
 * Script-only deterministic inspection for bytes returned from desktop Word.
 * Keeping this outside `src/` preserves the production/QA import boundary:
 * Office QA helpers can never be traced into signing, download, or workers.
 */
export async function verifyReturnedOfficeArtifacts(
  input: ReturnedOfficeArtifactVerifierInput,
): Promise<ReturnedOfficeArtifactVerification> {
  const expected = parseExpectedManifest(input);
  const workCopyIdentityValid = Boolean(
    input.workCopyBytes.byteLength === input.expectedDocumentSizeBytes &&
      sha256(input.workCopyBytes) === input.expectedDocumentSha256,
  );
  const security = inspectOfficeDocxSecurityQa(input.reopenedDocxBytes);
  const reopenedPackageValid = Boolean(
    workCopyIdentityValid &&
      security.status === "passed" &&
      security.inspectedDocxSha256 === sha256(input.reopenedDocxBytes) &&
      security.inspectedSizeBytes === input.reopenedDocxBytes.byteLength,
  );

  let staticAndOccurrenceValid = false;
  let semanticReadbackValid = false;
  if (expected && reopenedPackageValid) {
    try {
      const before = buildOfficeVisibleStaticManifestFromDocxBytes({
        syntheticOnly: true,
        docxBytes: input.workCopyBytes,
        expected,
      });
      const after = buildOfficeVisibleStaticManifestFromDocxBytes({
        syntheticOnly: true,
        docxBytes: input.reopenedDocxBytes,
        expected,
      });
      staticAndOccurrenceValid =
        compareOfficeVisibleStaticManifests(before.manifest, after.manifest)
          .aggregateVisibleContentMatches;

      if (input.documentRole === "source") {
        semanticReadbackValid = staticAndOccurrenceValid;
      } else {
        const actual = readOfficeSavedDocxFieldsQa({
          syntheticOnly: true,
          officeSavedDocxBytes: input.reopenedDocxBytes,
          expected,
        });
        const expectedFields = new Map(
          expected.fields.map((field) => [field.fieldId, field]),
        );
        semanticReadbackValid = Boolean(
          validActualManifest(actual, expected) &&
            actual.unexpectedBindingCount === 0 &&
            actual.ambiguousBindingCount === 0 &&
            actual.fields.length === expected.fields.length &&
            actual.fields.every((field) => {
              const expectedField = expectedFields.get(field.fieldId);
              return Boolean(
                expectedField &&
                  field.actualOccurrences === 1 &&
                  field.actualValueSha256 ===
                    expectedField.expectedValueSha256 &&
                  field.actualControlStateSha256 ===
                    expectedField.expectedControlStateSha256,
              );
            }),
        );
      }
    } catch {
      staticAndOccurrenceValid = false;
      semanticReadbackValid = false;
    }
  }

  return {
    contractVersion:
      "template-twin-returned-office-artifact-verifier/1.0.0",
    verificationManifestValid: expected !== null,
    reopenedPackageValid,
    staticAndOccurrenceValid,
    semanticReadbackValid,
    exportedPdfValid: await validWordExportedPdf(
      input.exportedPdfBytes,
      input.expectedPageCount,
    ),
  };
}
