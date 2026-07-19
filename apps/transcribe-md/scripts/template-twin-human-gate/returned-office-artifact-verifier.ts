import { createHash } from "node:crypto";

import { extractTextItems, getDocumentProxy } from "unpdf";

import {
  buildOfficeLayoutIntegrityManifestQa,
  buildOfficeVisibleStaticManifestFromDocxBytes,
  compareOfficeLayoutIntegrityManifestsQa,
  compareOfficeVisibleStaticManifests,
  deriveOfficePdfDocumentFactsQa,
  inspectOfficeDocxSecurityQa,
  normalizeOfficePdfWordTokens,
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
import { WordPdfExportBindingSchema } from "../../src/lib/template-twin/human-release-gate/contracts";

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

interface WordPdfInspection {
  readonly packageValid: boolean;
  readonly semanticLayoutValid: boolean;
}

function containsExpectedTokens(
  expected: readonly string[],
  actual: readonly string[],
): boolean {
  const remaining = new Map<string, number>();
  for (const token of actual)
    remaining.set(token, (remaining.get(token) ?? 0) + 1);
  for (const token of expected) {
    const count = remaining.get(token) ?? 0;
    if (count === 0) return false;
    remaining.set(token, count - 1);
  }
  return expected.length > 0;
}

async function inspectWordExportedPdf(
  bytes: Uint8Array,
  expectedPageCount: number,
  reopenedDocxBytes: Uint8Array,
): Promise<WordPdfInspection> {
  if (
    !Buffer.from(bytes).subarray(0, 5).equals(Buffer.from("%PDF-")) ||
    /\/(?:AA|EmbeddedFile|JavaScript|JS|Launch|OpenAction)\b/u.test(
      Buffer.from(bytes).toString("latin1"),
    )
  ) {
    return { packageValid: false, semanticLayoutValid: false };
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
    const packageValid = pdf.numPages === expectedPageCount;
    const documentFacts = deriveOfficePdfDocumentFactsQa({
      syntheticOnly: true,
      docxBytes: reopenedDocxBytes,
    });
    const extracted = await extractTextItems(pdf);
    const actualTokens = extracted.items.flatMap((page) =>
      page.flatMap((item) => normalizeOfficePdfWordTokens(item.str)),
    );
    let geometryValid =
      extracted.totalPages === expectedPageCount &&
      extracted.items.length === expectedPageCount &&
      extracted.items.some((page) => page.length > 0);
    for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
      const page = await pdf.getPage(pageNumber);
      const viewport = page.getViewport({ scale: 1 });
      const pageSizeMatches = documentFacts.pageSizesPoints.some(
        (size) =>
          Math.abs(size.width - viewport.width) <= 1.5 &&
          Math.abs(size.height - viewport.height) <= 1.5,
      );
      const items = extracted.items[pageNumber - 1] ?? [];
      if (
        !pageSizeMatches ||
        items.some(
          (item) =>
            ![item.x, item.y, item.width, item.height, item.fontSize].every(
              Number.isFinite,
            ) ||
            item.width < 0 ||
            item.height < 0 ||
            item.x < -5 ||
            item.x > viewport.width + 5 ||
            item.y < -5 ||
            item.y > viewport.height + 5,
        )
      ) {
        geometryValid = false;
      }
      page.cleanup();
    }
    const semanticLayoutValid = Boolean(
      packageValid &&
      geometryValid &&
      containsExpectedTokens(documentFacts.normalizedWordTokens, actualTokens),
    );
    await pdf.destroy();
    return { packageValid, semanticLayoutValid };
  } catch {
    return { packageValid: false, semanticLayoutValid: false };
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function validPdfExportBinding(
  input: ReturnedOfficeArtifactVerifierInput,
): boolean {
  try {
    const parsed = WordPdfExportBindingSchema.parse(
      JSON.parse(
        Buffer.from(input.pdfExportBindingBytes)
          .toString("utf8")
          .replace(/^\uFEFF/u, ""),
      ) as unknown,
    );
    return Boolean(
      parsed.sourceCommit === input.expectedSourceCommit &&
      parsed.caseId === input.caseId &&
      parsed.documentRole === input.documentRole &&
      parsed.reopenedDocxSha256 === sha256(input.reopenedDocxBytes) &&
      parsed.reopenedDocxSizeBytes === input.reopenedDocxBytes.byteLength &&
      parsed.exportedPdfSha256 === sha256(input.exportedPdfBytes) &&
      parsed.exportedPdfSizeBytes === input.exportedPdfBytes.byteLength &&
      parsed.wordPageCount === input.expectedPageCount,
    );
  } catch {
    return false;
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
  let layoutIntegrityValid = false;
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
      const staticComparison = compareOfficeVisibleStaticManifests(
        before.manifest,
        after.manifest,
      );
      staticAndOccurrenceValid = Boolean(
        staticComparison.aggregateVisibleContentMatches &&
        staticComparison.aggregateStructureMatches,
      );
      layoutIntegrityValid = compareOfficeLayoutIntegrityManifestsQa(
        buildOfficeLayoutIntegrityManifestQa({
          syntheticOnly: true,
          docxBytes: input.workCopyBytes,
        }),
        buildOfficeLayoutIntegrityManifestQa({
          syntheticOnly: true,
          docxBytes: input.reopenedDocxBytes,
        }),
      ).matches;

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
              field.actualValueSha256 === expectedField.expectedValueSha256 &&
              field.actualControlStateSha256 ===
                expectedField.expectedControlStateSha256,
            );
          }),
        );
      }
    } catch {
      staticAndOccurrenceValid = false;
      semanticReadbackValid = false;
      layoutIntegrityValid = false;
    }
  }

  const pdfInspection = await inspectWordExportedPdf(
    input.exportedPdfBytes,
    input.expectedPageCount,
    input.reopenedDocxBytes,
  );

  return {
    contractVersion: "template-twin-returned-office-artifact-verifier/2.0.0",
    verificationManifestValid: expected !== null,
    reopenedPackageValid,
    staticAndOccurrenceValid,
    semanticReadbackValid,
    layoutIntegrityValid,
    exportedPdfValid: pdfInspection.packageValid,
    pdfSemanticLayoutValid: pdfInspection.semanticLayoutValid,
    pdfExportBindingValid: validPdfExportBinding(input),
  };
}
