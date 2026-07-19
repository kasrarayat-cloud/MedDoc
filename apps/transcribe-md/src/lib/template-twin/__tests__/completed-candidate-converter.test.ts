import { createHash } from "node:crypto";

import JSZip from "jszip";
import { describe, expect, it } from "vitest";

import {
  compileTemplateDocx,
  inspectDocxPackage,
} from "@/lib/note-template-docx";

import {
  COMPLETED_CANDIDATE_SYNTHETIC_SENTINEL,
  CompletedCandidateConversionError,
  convertCompletedDocumentsToCandidate,
} from "../completed-candidate-converter";
import { canonicalSha256 } from "../canonical";
import {
  CompletedCandidatePrivacyEvidenceSchema,
  CompletedCandidateReviewProjectionSchema,
} from "../completed-candidate-contract";

const CONTENT_TYPES = `<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>`;
const ROOT_RELS = `<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>`;

function documentXml(input: {
  finding: string;
  plan: string;
  extraParagraph?: string;
  extraRow?: string;
  findingRunProperties?: string;
  findingRunsXml?: string;
  findingCellProperties?: string;
}): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
  <w:p><w:r><w:t>${COMPLETED_CANDIDATE_SYNTHETIC_SENTINEL}</w:t></w:r></w:p>
  ${input.extraParagraph ? `<w:p><w:r><w:t>${input.extraParagraph}</w:t></w:r></w:p>` : ""}
  <w:tbl><w:tblGrid><w:gridCol w:w="2400"/><w:gridCol w:w="4800"/></w:tblGrid>
    <w:tr><w:tc><w:p><w:r><w:t>Finding</w:t></w:r></w:p></w:tc><w:tc>${input.findingCellProperties ?? ""}<w:p><w:pPr><w:spacing w:after="0"/></w:pPr>${input.findingRunsXml ?? `<w:r>${input.findingRunProperties ?? ""}<w:t>${input.finding}</w:t></w:r>`}</w:p></w:tc></w:tr>
    <w:tr><w:tc><w:p><w:r><w:t>Plan</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>${input.plan}</w:t></w:r></w:p></w:tc></w:tr>
    ${input.extraRow ?? ""}
  </w:tbl><w:sectPr/>
</w:body></w:document>`;
}

async function example(input: Parameters<typeof documentXml>[0]) {
  const zip = new JSZip();
  zip.file("[Content_Types].xml", CONTENT_TYPES);
  zip.file("_rels/.rels", ROOT_RELS);
  zip.file("word/document.xml", documentXml(input));
  const document = await zip.generateAsync({
    type: "nodebuffer",
    compression: "DEFLATE",
    compressionOptions: { level: 6 },
  });
  return {
    document,
    minimizedSha256: createHash("sha256").update(document).digest("hex"),
  };
}

describe("completed document to blank candidate conversion", () => {
  it("creates a new blank DOCX with stable bindings and never copies example values", async () => {
    const first = await example({
      finding: "Synthetic mild finding",
      plan: "Synthetic brace plan",
    });
    const second = await example({
      finding: "Synthetic moderate finding",
      plan: "Synthetic exercise plan",
    });

    const result = await convertCompletedDocumentsToCandidate([first, second]);
    expect(result.regions).toHaveLength(2);
    expect(result.regions.map((region) => region.label)).toEqual([
      "Finding",
      "Plan",
    ]);
    expect(result.comparison).toMatchObject({
      exampleCount: 2,
      identicalStructure: true,
      candidateFieldCount: 2,
    });
    expect(result.privacyEvidence.providerEgress).toBe(false);
    expect(result.privacyEvidence).toMatchObject({
      profileVersion: "completed-candidate-local-synthetic-privacy/1.1.0",
      sourceBinding: "minimized-package-structure-visible-text-digests",
    });
    expect(result.privacyEvidence.exampleEvidenceSha256s).toHaveLength(2);
    expect(new Set(result.privacyEvidence.exampleEvidenceSha256s).size).toBe(2);
    expect(
      CompletedCandidatePrivacyEvidenceSchema.safeParse(result.privacyEvidence)
        .success,
    ).toBe(true);
    const { evidenceSha256, ...privacyReceipt } = result.privacyEvidence;
    expect(evidenceSha256).toBe(canonicalSha256(privacyReceipt));
    expect(
      CompletedCandidateReviewProjectionSchema.safeParse(
        result.reviewProjection,
      ).success,
    ).toBe(true);
    expect(result.reviewProjectionSha256).toBe(
      canonicalSha256(result.reviewProjection),
    );
    expect(result.reviewProjection.candidateStructureSha256).toBe(
      result.candidateStructureSha256,
    );
    const serializedProjection = JSON.stringify(result.reviewProjection);
    expect(serializedProjection).not.toContain(
      COMPLETED_CANDIDATE_SYNTHETIC_SENTINEL,
    );
    expect(serializedProjection).not.toContain("Synthetic mild finding");
    expect(serializedProjection).not.toContain("Synthetic brace plan");
    const projectedTable = result.reviewProjection.blocks.find(
      (block) => block.kind === "table",
    );
    expect(projectedTable).toMatchObject({
      kind: "table",
      gridColumnBasisPoints: [3334, 6666],
    });
    if (!projectedTable || projectedTable.kind !== "table") {
      throw new Error("Expected the synthetic table projection.");
    }
    expect(
      projectedTable.rows.flatMap((row) =>
        row.cells.filter((cell) => cell.role.kind === "candidate_region"),
      ),
    ).toHaveLength(2);
    expect(result.document.equals(first.document)).toBe(false);
    const candidateZip = await JSZip.loadAsync(result.document);
    const candidateXml = await candidateZip
      .file("word/document.xml")!
      .async("string");
    expect(candidateXml).not.toContain("Synthetic mild finding");
    expect(candidateXml).not.toContain("Synthetic brace plan");

    const ir = compileTemplateDocx(result.document);
    expect(ir.fields).toHaveLength(2);
    expect(ir.fields.every((field) => field.rendererBinding.sdtId)).toBe(true);
    expect(ir.fields.map((field) => field.rendererBinding.tag).sort()).toEqual(
      result.regions.map((region) => region.candidateTag).sort(),
    );
    expect(inspectDocxPackage(first.document).sourceSha256).toBe(
      first.minimizedSha256,
    );
  });

  it("is deterministic for identical example bytes", async () => {
    const inputs = [
      await example({
        finding: "Synthetic finding alpha",
        plan: "Synthetic plan alpha",
      }),
      await example({
        finding: "Synthetic finding beta",
        plan: "Synthetic plan beta",
      }),
    ];
    const first = await convertCompletedDocumentsToCandidate(inputs);
    const second = await convertCompletedDocumentsToCandidate(inputs);
    expect(second.candidateSha256).toBe(first.candidateSha256);
    expect(second.inventorySha256).toBe(first.inventorySha256);
    expect(second.reviewProjectionSha256).toBe(first.reviewProjectionSha256);
    expect(second.regions).toEqual(first.regions);
  });

  it("preserves the exact unambiguous source run formatting in the blank control", async () => {
    const runProperties = '<w:rPr><w:b/><w:sz w:val="56"/></w:rPr>';
    const result = await convertCompletedDocumentsToCandidate([
      await example({
        finding: "Synthetic finding alpha",
        plan: "Synthetic plan alpha",
        findingRunProperties: runProperties,
      }),
      await example({
        finding: "Synthetic finding beta",
        plan: "Synthetic plan beta",
        findingRunProperties: runProperties,
      }),
    ]);
    const zip = await JSZip.loadAsync(result.document);
    const xml = await zip.file("word/document.xml")!.async("string");

    expect(xml).toContain(`<w:r>${runProperties}<w:t></w:t></w:r>`);
    expect(xml).not.toContain("Synthetic finding alpha");
  });

  it("fails closed instead of merging differently formatted source runs", async () => {
    await expect(
      convertCompletedDocumentsToCandidate([
        await example({
          finding: "unused",
          plan: "Synthetic plan",
          findingRunsXml:
            "<w:r><w:rPr><w:b/></w:rPr><w:t>Synthetic finding </w:t></w:r><w:r><w:t>alpha</w:t></w:r>",
        }),
        await example({
          finding: "unused",
          plan: "Synthetic plan",
          findingRunsXml:
            "<w:r><w:rPr><w:b/></w:rPr><w:t>Synthetic finding </w:t></w:r><w:r><w:t>beta</w:t></w:r>",
        }),
      ]),
    ).rejects.toMatchObject({ code: "AMBIGUOUS_TABLE_CHANGE" });
  });

  it("fails closed when merged-cell topology cannot be reproduced exactly", async () => {
    await expect(
      convertCompletedDocumentsToCandidate([
        await example({
          finding: "Synthetic finding alpha",
          plan: "Synthetic plan alpha",
          findingCellProperties: '<w:tcPr><w:vMerge w:val="restart"/></w:tcPr>',
        }),
        await example({
          finding: "Synthetic finding beta",
          plan: "Synthetic plan beta",
          findingCellProperties: '<w:tcPr><w:vMerge w:val="restart"/></w:tcPr>',
        }),
      ]),
    ).rejects.toMatchObject({ code: "STRUCTURAL_PREVIEW_UNSUPPORTED" });
  });

  it("rejects arbitrary text injected into the strict projection contract", async () => {
    const result = await convertCompletedDocumentsToCandidate([
      await example({
        finding: "Synthetic finding alpha",
        plan: "Synthetic plan alpha",
      }),
      await example({
        finding: "Synthetic finding beta",
        plan: "Synthetic plan beta",
      }),
    ]);
    expect(
      CompletedCandidateReviewProjectionSchema.safeParse({
        ...result.reviewProjection,
        sourceText: "must never be exposed",
      }).success,
    ).toBe(false);
  });

  it("rejects duplicate or incomplete structural identities in the review projection", async () => {
    const result = await convertCompletedDocumentsToCandidate([
      await example({
        finding: "Synthetic finding alpha",
        plan: "Synthetic plan alpha",
      }),
      await example({
        finding: "Synthetic finding beta",
        plan: "Synthetic plan beta",
      }),
    ]);

    const duplicateSource = structuredClone(result.reviewProjection);
    duplicateSource.sourceExampleSha256s[1] =
      duplicateSource.sourceExampleSha256s[0]!;

    const duplicateBlockOrder = structuredClone(result.reviewProjection);
    duplicateBlockOrder.blocks.at(-1)!.displayOrder = 0;

    const duplicateCell = structuredClone(result.reviewProjection);
    const duplicateCellTable = duplicateCell.blocks.find(
      (block) => block.kind === "table",
    );
    if (!duplicateCellTable || duplicateCellTable.kind !== "table") {
      throw new Error("Expected the synthetic table projection.");
    }
    duplicateCellTable.rows[0]!.cells[1]!.cellKey =
      duplicateCellTable.rows[0]!.cells[0]!.cellKey;

    const duplicateTag = structuredClone(result.reviewProjection);
    const duplicateTagTable = duplicateTag.blocks.find(
      (block) => block.kind === "table",
    );
    if (!duplicateTagTable || duplicateTagTable.kind !== "table") {
      throw new Error("Expected the synthetic table projection.");
    }
    const candidateCells = duplicateTagTable.rows.flatMap((row) =>
      row.cells.filter((cell) => cell.role.kind === "candidate_region"),
    );
    if (
      candidateCells.length !== 2 ||
      candidateCells[0]!.role.kind !== "candidate_region" ||
      candidateCells[1]!.role.kind !== "candidate_region"
    ) {
      throw new Error("Expected two candidate cells.");
    }
    candidateCells[1]!.role.candidateTag = candidateCells[0]!.role.candidateTag;

    const missingLabel = structuredClone(result.reviewProjection);
    const missingLabelTable = missingLabel.blocks.find(
      (block) => block.kind === "table",
    );
    if (!missingLabelTable || missingLabelTable.kind !== "table") {
      throw new Error("Expected the synthetic table projection.");
    }
    const stableLabel = missingLabelTable.rows
      .flatMap((row) => row.cells)
      .find((cell) => cell.role.kind === "stable_label");
    if (!stableLabel) throw new Error("Expected a stable label cell.");
    stableLabel.role = { kind: "static_redacted" };

    for (const projection of [
      duplicateSource,
      duplicateBlockOrder,
      duplicateCell,
      duplicateTag,
      missingLabel,
    ]) {
      expect(
        CompletedCandidateReviewProjectionSchema.safeParse(projection).success,
      ).toBe(false);
    }
  });

  it.each([
    [
      "ordinary narrative changes",
      async () => [
        await example({
          finding: "Synthetic finding alpha",
          plan: "Synthetic plan",
          extraParagraph: "Synthetic narrative alpha",
        }),
        await example({
          finding: "Synthetic finding beta",
          plan: "Synthetic plan",
          extraParagraph: "Synthetic narrative beta",
        }),
      ],
      "AMBIGUOUS_NARRATIVE_CHANGE",
    ],
    [
      "row shape changes",
      async () => [
        await example({
          finding: "Synthetic finding alpha",
          plan: "Synthetic plan alpha",
        }),
        await example({
          finding: "Synthetic finding beta",
          plan: "Synthetic plan beta",
          extraRow:
            "<w:tr><w:tc><w:p><w:r><w:t>Extra</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Synthetic extra</w:t></w:r></w:p></w:tc></w:tr>",
        }),
      ],
      "REPEATING_STRUCTURE_UNSUPPORTED",
    ],
    [
      "a non-synthetic value",
      async () => [
        await example({
          finding: "Mild finding",
          plan: "Synthetic plan alpha",
        }),
        await example({
          finding: "Moderate finding",
          plan: "Synthetic plan beta",
        }),
      ],
      "SYNTHETIC_SENTINEL_REQUIRED",
    ],
    [
      "a structured identifier",
      async () => [
        await example({
          finding: "Synthetic MRN RFM-0098214",
          plan: "Synthetic plan alpha",
        }),
        await example({
          finding: "Synthetic MRN RFM-0098215",
          plan: "Synthetic plan beta",
        }),
      ],
      "POSSIBLE_IDENTIFYING_CONTENT",
    ],
  ])(
    "rejects %s without producing a candidate",
    async (_label, build, code) => {
      await expect(
        convertCompletedDocumentsToCandidate(await build()),
      ).rejects.toMatchObject({ code });
    },
  );

  it("routes documents with existing controls to the native template workflow", async () => {
    const first = await example({
      finding: "Synthetic finding alpha",
      plan: "Synthetic plan alpha",
    });
    const zip = await JSZip.loadAsync(first.document);
    const xml = await zip.file("word/document.xml")!.async("string");
    zip.file(
      "word/document.xml",
      xml.replace(
        "Synthetic plan alpha",
        '<w:sdt><w:sdtPr><w:id w:val="900"/><w:alias w:val="Plan"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Choose</w:t></w:r></w:sdtContent></w:sdt>',
      ),
    );
    const controlled = await zip.generateAsync({ type: "nodebuffer" });

    await expect(
      convertCompletedDocumentsToCandidate([
        {
          document: controlled,
          minimizedSha256: createHash("sha256")
            .update(controlled)
            .digest("hex"),
        },
        await example({
          finding: "Synthetic finding beta",
          plan: "Synthetic plan beta",
        }),
      ]),
    ).rejects.toBeInstanceOf(CompletedCandidateConversionError);
  });
});
