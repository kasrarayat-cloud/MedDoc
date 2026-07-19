import JSZip from "jszip";
import { describe, expect, it } from "vitest";

import {
  FieldResolutionSchema,
  type FieldResolution,
  type TemplateField,
  type TemplateTwinValidationResult,
} from "../../template-twin/ir";
import { compileTemplateDocx } from "../compiler";
import { readbackTemplateDocxOutput } from "../output-readback";
import { renderTemplateDocx } from "../renderer";
import { buildSyntheticDocx, syntheticOpc } from "./synthetic-docx";

const FACT_ID = `ttfact_${"e".repeat(24)}`;
const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: "2026-07-16T00:00:00.000Z",
  validatorVersion: "template-field-validator/1.0.0",
};

function textControl(input: {
  id: string;
  alias: string;
  tag?: string;
  value?: string;
}): string {
  const tag = input.tag ? `<w:tag w:val="${input.tag}"/>` : "";
  return `<w:p><w:sdt><w:sdtPr><w:id w:val="${input.id}"/><w:alias w:val="${input.alias}"/>${tag}<w:text/></w:sdtPr><w:sdtContent><w:r><w:t>${input.value ?? "Synthetic placeholder"}</w:t></w:r></w:sdtContent></w:sdt></w:p>`;
}

function textControlWithIds(input: {
  ids: readonly string[];
  alias: string;
}): string {
  return `<w:p><w:sdt><w:sdtPr>${input.ids
    .map((id) => `<w:id w:val="${id}"/>`)
    .join("")}<w:alias w:val="${input.alias}"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Synthetic placeholder</w:t></w:r></w:sdtContent></w:sdt></w:p>`;
}

function legacyTextField(name: string): string {
  return `<w:p><w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="${name}"/><w:textInput><w:default w:val="Synthetic default"/></w:textInput></w:ffData></w:fldChar></w:r><w:r><w:instrText> FORMTEXT </w:instrText></w:r><w:r><w:t>Synthetic default</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>`;
}

function insertBeforeSection(fragment: string): string {
  return syntheticOpc.documentXml.replace(
    "<w:sectPr>",
    `${fragment}<w:sectPr>`,
  );
}

function headerWith(fragment: string): string {
  return `<?xml version="1.0" encoding="UTF-8"?><w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">${fragment}</w:hdr>`;
}

function buildSyntheticDocxWithFootnote(fragment = "") {
  return buildSyntheticDocx({
    contentTypes: syntheticOpc.contentTypes.replace(
      "</Types>",
      '  <Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>\n</Types>',
    ),
    documentRelationships: syntheticOpc.documentRelationships.replace(
      "</Relationships>",
      '  <Relationship Id="rIdFootnotes" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>\n</Relationships>',
    ),
    documentXml: syntheticOpc.documentXml.replace(
      "<w:sectPr>",
      '<w:p><w:r><w:footnoteReference w:id="2"/></w:r></w:p><w:sectPr>',
    ),
    extraEntries: {
      "word/footnotes.xml": `<?xml version="1.0" encoding="UTF-8"?><w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote><w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote><w:footnote w:id="2"><w:p><w:r><w:t>Synthetic footnote anchor</w:t></w:r></w:p>${fragment}</w:footnote></w:footnotes>`,
    },
  });
}

function duplicateBlockers(
  compiled: ReturnType<typeof compileTemplateDocx>,
  code: string,
) {
  return compiled.unsupported.filter((item) => item.code === code);
}

function resolutionFor(field: TemplateField): FieldResolution {
  if (field.rowPrototype || field.detectionStatus === "unsupported") {
    return FieldResolutionSchema.parse({
      fieldId: field.fieldId,
      status: "not_mentioned",
      value: null,
      sourceFactIds: [],
      evidenceAnchorIds: [],
      selectedOptionOrdinal: null,
      reasonCode: "synthetic_not_mentioned",
      clinicianReviewed: false,
    });
  }
  let value: FieldResolution["value"];
  let selectedOptionOrdinal: number | null = null;
  switch (field.kind) {
    case "single_select":
      value = field.allowedOptions[0]!.value;
      selectedOptionOrdinal = field.allowedOptions[0]!.ordinal;
      break;
    case "multi_select":
      value = [field.allowedOptions[0]!.value];
      break;
    case "checkbox":
      value = true;
      break;
    case "date":
      value = "2026-07-16";
      break;
    case "number":
      value = 1;
      break;
    case "measurement":
      value = "1 synthetic-unit";
      break;
    case "narrative_text":
      value = "Synthetic QA value";
      break;
  }
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status: "supported",
    value,
    sourceFactIds: [FACT_ID],
    evidenceAnchorIds: ["synthetic-duplicate-identity-anchor"],
    selectedOptionOrdinal,
    reasonCode: "synthetic_duplicate_identity_test",
    clinicianReviewed: false,
  });
}

async function duplicateControlInOutput(
  output: Uint8Array,
  marker: string,
): Promise<Buffer> {
  const zip = await JSZip.loadAsync(output);
  const documentEntry = zip.file("word/document.xml");
  if (!documentEntry)
    throw new Error("Synthetic main document part is missing.");
  const documentXml = await documentEntry.async("string");
  const markerIndex = documentXml.indexOf(marker);
  const start = documentXml.lastIndexOf("<w:sdt>", markerIndex);
  const end = documentXml.indexOf("</w:sdt>", markerIndex);
  if (markerIndex < 0 || start < 0 || end < 0) {
    throw new Error("Synthetic content control is missing.");
  }
  const control = documentXml.slice(start, end + "</w:sdt>".length);
  zip.file(
    "word/document.xml",
    documentXml.replace("<w:sectPr>", `<w:p>${control}</w:p><w:sectPr>`),
  );
  return zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" });
}

describe("native Word identity admission", () => {
  it("certification-blocks duplicate SDT IDs in the same part", async () => {
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: insertBeforeSection(
          textControl({
            id: "102",
            alias: "Synthetic duplicate control",
          }),
        ),
      }),
    );

    const blockers = duplicateBlockers(compiled, "DUPLICATE_SDT_ID");
    expect(blockers).toHaveLength(2);
    expect(blockers.every((item) => item.blocksCertification)).toBe(true);
    expect(blockers.every((item) => item.clinicallyMaterial)).toBe(true);
    expect(new Set(blockers.map((item) => item.partName))).toEqual(
      new Set(["word/document.xml"]),
    );
    const affected = compiled.fields.filter(
      (field) => field.rendererBinding.sdtId === "102",
    );
    expect(affected).toHaveLength(2);
    expect(
      affected.every((field) => field.detectionStatus === "unsupported"),
    ).toBe(true);
  });

  it("treats SDT IDs as package-wide across body and header parts", async () => {
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: insertBeforeSection(
          textControl({ id: "201", alias: "Synthetic body control" }),
        ),
      }),
    );

    const blockers = duplicateBlockers(compiled, "DUPLICATE_SDT_ID");
    expect(blockers).toHaveLength(2);
    expect(new Set(blockers.map((item) => item.partName))).toEqual(
      new Set(["word/document.xml", "word/header1.xml"]),
    );
    expect(
      compiled.fields
        .filter((field) => field.rendererBinding.sdtId === "201")
        .every((field) => field.detectionStatus === "unsupported"),
    ).toBe(true);
  });

  it("compares SDT IDs by their decimal value rather than lexical padding", async () => {
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: insertBeforeSection(
          textControl({
            id: "000102",
            alias: "Synthetic padded duplicate control",
          }),
        ),
      }),
    );

    const blockers = duplicateBlockers(compiled, "DUPLICATE_SDT_ID");
    expect(blockers).toHaveLength(2);
    expect(
      compiled.fields
        .filter((field) =>
          ["102", "000102"].includes(field.rendererBinding.sdtId ?? ""),
        )
        .every((field) => field.detectionStatus === "unsupported"),
    ).toBe(true);
  });

  it("normalizes equivalent signed and unsigned Word 32-bit SDT IDs", async () => {
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: insertBeforeSection(
          `${textControl({ id: "-1", alias: "Synthetic signed control" })}${textControl({ id: "4294967295", alias: "Synthetic unsigned control" })}`,
        ),
      }),
    );

    const blockers = duplicateBlockers(compiled, "DUPLICATE_SDT_ID");
    expect(blockers).toHaveLength(2);
    expect(
      compiled.fields
        .filter((field) =>
          ["-1", "4294967295"].includes(field.rendererBinding.sdtId ?? ""),
        )
        .every((field) => field.detectionStatus === "unsupported"),
    ).toBe(true);
  });

  it("detects duplicate IDs carried by unsupported container controls", async () => {
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: insertBeforeSection(
          textControl({
            id: "106",
            alias: "Synthetic duplicate of repeating container",
          }),
        ),
      }),
    );

    const blockers = duplicateBlockers(compiled, "DUPLICATE_SDT_ID");
    expect(blockers).toHaveLength(2);
    expect(
      compiled.fields.find(
        (field) =>
          field.originalLabel === "Synthetic duplicate of repeating container",
      )?.detectionStatus,
    ).toBe("unsupported");
  });

  it("certification-blocks duplicate legacy names within one Word story part", async () => {
    const duplicateName = "SyntheticDuplicateLegacy";
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: insertBeforeSection(
          `${legacyTextField(duplicateName)}${legacyTextField(duplicateName)}`,
        ),
      }),
    );

    const blockers = duplicateBlockers(
      compiled,
      "DUPLICATE_LEGACY_FORM_FIELD_NAME",
    );
    expect(blockers).toHaveLength(2);
    expect(new Set(blockers.map((item) => item.partName))).toEqual(
      new Set(["word/document.xml"]),
    );
    expect(
      compiled.fields
        .filter((field) => field.rendererBinding.legacyName === duplicateName)
        .every((field) => field.detectionStatus === "unsupported"),
    ).toBe(true);
  });

  it("blocks legacy names outside the main story and package-wide duplicates", async () => {
    const sharedName = "SyntheticStoryScopedLegacy";
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: insertBeforeSection(legacyTextField(sharedName)),
        extraEntries: {
          "word/header1.xml": headerWith(legacyTextField(sharedName)),
        },
      }),
    );

    expect(
      duplicateBlockers(compiled, "DUPLICATE_LEGACY_FORM_FIELD_NAME"),
    ).toHaveLength(2);
    expect(
      duplicateBlockers(compiled, "UNSUPPORTED_LEGACY_FORM_FIELD_STORY"),
    ).toEqual([
      expect.objectContaining({
        partName: "word/header1.xml",
        blocksCertification: true,
      }),
    ]);
    const fields = compiled.fields.filter(
      (field) => field.rendererBinding.legacyName === sharedName,
    );
    expect(fields).toHaveLength(2);
    expect(
      new Set(fields.map((field) => field.rendererBinding.partName)),
    ).toEqual(new Set(["word/document.xml", "word/header1.xml"]));
    expect(fields.every((field) => field.detectionStatus === "unsupported")).toBe(
      true,
    );
  });

  it("blocks missing SDT IDs even when aliases differ", async () => {
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: insertBeforeSection(
          `${textControlWithIds({ ids: [], alias: "Missing one" })}${textControlWithIds({ ids: [], alias: "Missing two" })}`,
        ),
      }),
    );

    const blockers = duplicateBlockers(compiled, "MISSING_SDT_ID");
    expect(blockers).toHaveLength(2);
    const affected = compiled.fields.filter((field) =>
      ["Missing one", "Missing two"].includes(field.originalLabel),
    );
    expect(affected).toHaveLength(2);
    expect(
      affected.every((field) => field.detectionStatus === "unsupported"),
    ).toBe(true);
  });

  it.each(["not-a-decimal", "", "4294967296", "-2147483649"])(
    "blocks invalid SDT identity %j",
    async (id) => {
      const compiled = compileTemplateDocx(
        await buildSyntheticDocx({
          documentXml: insertBeforeSection(
            textControlWithIds({ ids: [id], alias: "Invalid ID" }),
          ),
        }),
      );
      expect(duplicateBlockers(compiled, "INVALID_SDT_ID")).toEqual([
        expect.objectContaining({
          label: "Invalid ID",
          blocksCertification: true,
        }),
      ]);
      expect(
        compiled.fields.find((field) => field.originalLabel === "Invalid ID")
          ?.detectionStatus,
      ).toBe("unsupported");
    },
  );

  it("blocks multiple SDT ID elements even when values are equal", async () => {
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: insertBeforeSection(
          textControlWithIds({
            ids: ["940", "940"],
            alias: "Multiple IDs",
          }),
        ),
      }),
    );
    expect(duplicateBlockers(compiled, "MULTIPLE_SDT_ID")).toEqual([
      expect.objectContaining({
        label: "Multiple IDs",
        blocksCertification: true,
      }),
    ]);
  });

  it("censuses auxiliary Word stories and blocks their controls", async () => {
    const compiled = compileTemplateDocx(
      await buildSyntheticDocxWithFootnote(
        textControl({ id: "102", alias: "Footnote duplicate" }),
      ),
    );
    expect(duplicateBlockers(compiled, "DUPLICATE_SDT_ID")).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ partName: "word/document.xml" }),
        expect.objectContaining({ partName: "word/footnotes.xml" }),
      ]),
    );
    expect(
      duplicateBlockers(
        compiled,
        "UNSUPPORTED_AUXILIARY_STORY_CONTENT_CONTROL",
      ),
    ).toEqual([
      expect.objectContaining({
        partName: "word/footnotes.xml",
        blocksCertification: true,
      }),
    ]);
    expect(
      compiled.fields.filter((field) => field.rendererBinding.sdtId === "102"),
    ).toEqual([
      expect.objectContaining({ detectionStatus: "unsupported" }),
    ]);
  });

  it("allows repeated physician labels when native identities and paths differ", async () => {
    const label = "Repeated synthetic label";
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: insertBeforeSection(
          `${textControl({ id: "920", alias: label, tag: "first_repeated_field" })}${textControl({ id: "921", alias: label, tag: "second_repeated_field" })}`,
        ),
      }),
    );

    const fields = compiled.fields.filter(
      (field) => field.originalLabel === label,
    );
    expect(fields).toHaveLength(2);
    expect(new Set(fields.map((field) => field.fieldId)).size).toBe(2);
    expect(
      new Set(fields.map((field) => field.rendererBinding.path)).size,
    ).toBe(2);
    expect(
      fields.every((field) => field.detectionStatus !== "unsupported"),
    ).toBe(true);
  });

  it("allows repeated tags and aliases when each SDT ID is unique", async () => {
    const alias = "Repeated legal alias";
    const tag = "repeated_legal_tag";
    const compiled = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: insertBeforeSection(
          `${textControl({ id: "930", alias, tag })}${textControl({ id: "931", alias, tag })}`,
        ),
      }),
    );

    expect(duplicateBlockers(compiled, "DUPLICATE_SDT_ID")).toHaveLength(0);
    const fields = compiled.fields.filter(
      (field) =>
        field.rendererBinding.alias === alias &&
        field.rendererBinding.tag === tag,
    );
    expect(fields).toHaveLength(2);
    expect(
      new Set(fields.map((field) => field.rendererBinding.sdtId)).size,
    ).toBe(2);
    expect(
      fields.every((field) => field.detectionStatus !== "unsupported"),
    ).toBe(true);
  });

  it("retains output readback defense against post-certification duplication", async () => {
    const source = await buildSyntheticDocx();
    const ir = compileTemplateDocx(source);
    const resolutions = ir.fields.map(resolutionFor);
    const rendered = await renderTemplateDocx({
      source,
      ir,
      resolutions,
      validation: VALIDATION,
    });
    const tampered = await duplicateControlInOutput(
      rendered.document,
      'w:id w:val="102"',
    );

    expect(() =>
      readbackTemplateDocxOutput({
        source,
        output: tampered,
        ir,
        resolutions,
      }),
    ).toThrowError(
      expect.objectContaining({ code: "ROUNDTRIP_FIELD_MISMATCH" }),
    );
  });

  it("censuses post-render identity tampering in auxiliary Word stories", async () => {
    const source = await buildSyntheticDocxWithFootnote();
    const ir = compileTemplateDocx(source);
    const resolutions = ir.fields.map(resolutionFor);
    const rendered = await renderTemplateDocx({
      source,
      ir,
      resolutions,
      validation: VALIDATION,
    });
    const zip = await JSZip.loadAsync(rendered.document);
    const entry = zip.file("word/footnotes.xml");
    if (!entry) throw new Error("Synthetic footnote part is missing.");
    const before = await entry.async("string");
    const after = before.replace(
      "<w:p><w:r><w:t>Synthetic footnote anchor</w:t></w:r></w:p>",
      `<w:p><w:r><w:t>Synthetic footnote anchor</w:t></w:r></w:p>${textControl({ id: "102", alias: "Post-render footnote duplicate" })}`,
    );
    expect(after).not.toBe(before);
    zip.file("word/footnotes.xml", after);
    const tampered = await zip.generateAsync({
      type: "nodebuffer",
      compression: "DEFLATE",
    });

    expect(() =>
      readbackTemplateDocxOutput({ source, output: tampered, ir, resolutions }),
    ).toThrowError(
      expect.objectContaining({ code: "ROUNDTRIP_FIELD_MISMATCH" }),
    );
  });

  it("accepts normal Word controls without duplicate-identity blockers", async () => {
    const compiled = compileTemplateDocx(await buildSyntheticDocx());
    expect(duplicateBlockers(compiled, "DUPLICATE_SDT_ID")).toHaveLength(0);
    expect(
      duplicateBlockers(compiled, "DUPLICATE_LEGACY_FORM_FIELD_NAME"),
    ).toHaveLength(0);
  });
});
