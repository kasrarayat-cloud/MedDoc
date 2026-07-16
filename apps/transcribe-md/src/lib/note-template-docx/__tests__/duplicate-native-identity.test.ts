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
    expect(
      compiled.fields
        .filter((field) => field.rendererBinding.sdtId === "102")
        .every((field) => field.detectionStatus === "unsupported"),
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

  it("allows the same legacy name in different Word story parts", async () => {
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
    ).toHaveLength(0);
    const fields = compiled.fields.filter(
      (field) => field.rendererBinding.legacyName === sharedName,
    );
    expect(fields).toHaveLength(2);
    expect(
      new Set(fields.map((field) => field.rendererBinding.partName)),
    ).toEqual(new Set(["word/document.xml", "word/header1.xml"]));
    expect(
      fields.every((field) => field.detectionStatus !== "unsupported"),
    ).toBe(true);
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

  it("accepts normal Word controls without duplicate-identity blockers", async () => {
    const compiled = compileTemplateDocx(await buildSyntheticDocx());
    expect(duplicateBlockers(compiled, "DUPLICATE_SDT_ID")).toHaveLength(0);
    expect(
      duplicateBlockers(compiled, "DUPLICATE_LEGACY_FORM_FIELD_NAME"),
    ).toHaveLength(0);
  });
});
