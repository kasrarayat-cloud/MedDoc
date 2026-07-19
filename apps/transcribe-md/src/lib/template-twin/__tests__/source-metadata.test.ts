import JSZip from "jszip";
import { describe, expect, it } from "vitest";

import { inspectDocxPackage } from "@/lib/note-template-docx";
import {
  buildSyntheticDocx,
  syntheticOpc,
} from "@/lib/note-template-docx/__tests__/synthetic-docx";

import {
  isTemplateTwinMetadataEvidenceValid,
  minimizeTemplateTwinSourceMetadata,
  TEMPLATE_TWIN_METADATA_PROFILE,
} from "../source-metadata";

const CORE = `<?xml version="1.0" encoding="UTF-8"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Synthetic patient-like title</dc:title><dc:creator>Synthetic Identifying Author</dc:creator><cp:lastModifiedBy>Another Synthetic Author</cp:lastModifiedBy></cp:coreProperties>`;
const APP = `<?xml version="1.0" encoding="UTF-8"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Manager>Synthetic Manager</Manager><Company>Synthetic Practice Identity</Company><Application>Microsoft Office Word</Application></Properties>`;
const CUSTOM = `<?xml version="1.0" encoding="UTF-8"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><property fmtid="{00000000-0000-0000-0000-000000000000}" pid="2" name="SyntheticIdentity"><vt:lpwstr>synthetic.patient@example.test</vt:lpwstr></property></Properties>`;

async function sourceWithMetadata(): Promise<Buffer> {
  const contentTypes = syntheticOpc.contentTypes.replace(
    "</Types>",
    [
      '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
      '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
      '<Override PartName="/docProps/custom.xml" ContentType="application/vnd.openxmlformats-officedocument.custom-properties+xml"/>',
      "</Types>",
    ].join(""),
  );
  const rootRelationships = syntheticOpc.rootRelationships.replace(
    "</Relationships>",
    [
      '<Relationship Id="rIdCore" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>',
      '<Relationship Id="rIdApp" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>',
      '<Relationship Id="rIdCustom" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties" Target="docProps/custom.xml"/>',
      "</Relationships>",
    ].join(""),
  );
  return buildSyntheticDocx({
    contentTypes,
    rootRelationships,
    extraEntries: {
      "docProps/core.xml": CORE,
      "docProps/app.xml": APP,
      "docProps/custom.xml": CUSTOM,
    },
  });
}

describe("Template Twin DOCX metadata minimization", () => {
  it("replaces identifying properties without changing layout XML", async () => {
    const source = await sourceWithMetadata();
    const before = inspectDocxPackage(source);

    const minimized = await minimizeTemplateTwinSourceMetadata(source);
    const after = inspectDocxPackage(minimized.document);
    const zip = await JSZip.loadAsync(minimized.document);

    expect(minimized.evidence).toMatchObject({
      profileVersion: TEMPLATE_TWIN_METADATA_PROFILE,
      originalSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
      minimizedSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
      replacedParts: [
        "docProps/app.xml",
        "docProps/core.xml",
        "docProps/custom.xml",
      ],
      zipEntryTimestampsNormalized: true,
    });
    expect(minimized.evidence.originalSha256).not.toBe(
      minimized.evidence.minimizedSha256,
    );
    expect(after.zip.entries.get("word/document.xml")?.bytes).toEqual(
      before.zip.entries.get("word/document.xml")?.bytes,
    );
    expect(after.zip.entries.get("word/header1.xml")?.bytes).toEqual(
      before.zip.entries.get("word/header1.xml")?.bytes,
    );

    const serializedProperties = (
      await Promise.all(
        ["docProps/core.xml", "docProps/app.xml", "docProps/custom.xml"].map(
          (partName) => zip.file(partName)!.async("string"),
        ),
      )
    ).join("\n");
    expect(serializedProperties).not.toContain("Synthetic Identifying Author");
    expect(serializedProperties).not.toContain("Synthetic Practice Identity");
    expect(serializedProperties).not.toContain("synthetic.patient@example.test");
    expect(serializedProperties).toContain("QuillMD");
    expect(
      isTemplateTwinMetadataEvidenceValid({
        evidence: minimized.evidence,
        originalSha256: minimized.evidence.originalSha256,
        minimizedSha256: minimized.evidence.minimizedSha256,
      }),
    ).toBe(true);
    expect(
      isTemplateTwinMetadataEvidenceValid({
        evidence: {
          ...minimized.evidence,
          replacedParts: [
            ...minimized.evidence.replacedParts,
            "word/document.xml",
          ],
        },
        originalSha256: minimized.evidence.originalSha256,
        minimizedSha256: minimized.evidence.minimizedSha256,
      }),
    ).toBe(false);
  });

  it("is byte-deterministic for an identical source", async () => {
    const source = await sourceWithMetadata();
    const first = await minimizeTemplateTwinSourceMetadata(source);
    const second = await minimizeTemplateTwinSourceMetadata(source);

    expect(second.document).toEqual(first.document);
    expect(second.evidence).toEqual(first.evidence);
  });
});
