import { describe, expect, it } from "vitest";

import {
  FieldResolutionSchema,
  type FieldResolution,
  type TemplateDocIR,
  type TemplateTwinValidationResult,
} from "../../template-twin/ir";
import { compileTemplateDocx } from "../compiler";
import { inspectDocxPackage } from "../package-security";
import { renderTemplateDocx } from "../renderer";
import { buildSyntheticDocx, syntheticOpc } from "./synthetic-docx";

const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: "2026-07-19T00:00:00.000Z",
  validatorVersion: "template-field-validator/1.0.0",
};

function resolutionsFor(
  ir: TemplateDocIR,
  values: ReadonlyMap<string, FieldResolution["value"]>,
): FieldResolution[] {
  return ir.fields.map((field) => {
    const value = values.get(field.originalLabel) ?? null;
    return FieldResolutionSchema.parse({
      fieldId: field.fieldId,
      status: value === null ? "not_mentioned" : "supported",
      value,
      sourceFactIds: value === null ? [] : [`ttfact_${"a".repeat(24)}`],
      evidenceAnchorIds: value === null ? [] : ["synthetic-anchor"],
      selectedOptionOrdinal: null,
      reasonCode: value === null ? "synthetic_missing" : "synthetic_evidence",
      clinicianReviewed: false,
    });
  });
}

describe("native DOCX compatibility boundary", () => {
  it("rejects namespace-shadowed exact-option attributes", async () => {
    const documentXml = syntheticOpc.documentXml
      .replace(
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"',
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:evil="urn:synthetic:evil"',
      )
      .replace(
        '<w:listItem w:displayText="Left" w:value="L"/>',
        '<w:listItem evil:displayText="Spoofed" w:displayText="Left" w:value="L"/>',
      );
    await expectCompileFailure(documentXml, "ACTIVE_CONTENT_REJECTED");
  });

  it("rejects foreign-namespace date and table semantic lookalikes", async () => {
    const calendarShadow = syntheticOpc.documentXml
      .replace(
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"',
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:evil="urn:synthetic:evil"',
      )
      .replace(
        '<w:dateFormat w:val="yyyy-MM-dd"/>',
        '<w:dateFormat w:val="yyyy-MM-dd"/><evil:calendar evil:val="gregorian"/><w:calendar w:val="hijri"/>',
      );
    await expectCompileFailure(calendarShadow, "ACTIVE_CONTENT_REJECTED");

    const gridSpanShadow = syntheticOpc.documentXml
      .replace(
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"',
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:evil="urn:synthetic:evil"',
      )
      .replace(
        '<w:gridSpan w:val="2"/>',
        '<evil:gridSpan evil:val="2"/><w:gridSpan w:val="999999999"/>',
      );
    await expectCompileFailure(gridSpanShadow, "ACTIVE_CONTENT_REJECTED");

    const duplicateWordGridSpan = syntheticOpc.documentXml.replace(
      '<w:gridSpan w:val="2"/>',
      '<w:gridSpan w:val="2"/><w:gridSpan w:val="999999999"/>',
    );
    await expectCompileFailure(duplicateWordGridSpan, "XML_INVALID");
  });

  it("rejects mutually exclusive native and legacy control definitions", async () => {
    const mixedNative = syntheticOpc.documentXml.replace(
      "</w:dropDownList></w:sdtPr>",
      '</w:dropDownList><w:date><w:dateFormat w:val="yyyy-MM-dd"/></w:date></w:sdtPr>',
    );
    await expectCompileFailure(mixedNative, "XML_INVALID");

    const mixedLegacy = syntheticOpc.documentXml.replace(
      "</w:ddList></w:ffData>",
      '</w:ddList><w:textInput><w:type w:val="regular"/></w:textInput></w:ffData>',
    );
    await expectCompileFailure(mixedLegacy, "XML_INVALID");
  });

  it("rejects nested competing native and legacy control definitions", async () => {
    const nestedNative = syntheticOpc.documentXml.replace(
      '<w:text w:multiLine="true"/>',
      '<w:text w:multiLine="true"/><w:placeholder><w14:checkbox><w14:checked w14:val="0"/></w14:checkbox></w:placeholder>',
    );
    await expectCompileFailure(nestedNative, "XML_INVALID");

    const nestedLegacy = syntheticOpc.documentXml.replace(
      "</w:ddList></w:ffData>",
      '</w:ddList><w:helpText><w:textInput><w:type w:val="regular"/></w:textInput></w:helpText></w:ffData>',
    );
    await expectCompileFailure(nestedLegacy, "XML_INVALID");
  });

  it("rejects legacy form-field macro hooks", async () => {
    for (const macroName of ["entryMacro", "exitMacro"]) {
      await expectCompileFailure(
        syntheticOpc.documentXml.replace(
          '<w:name w:val="Legacy severity"/>',
          `<w:name w:val="Legacy severity"/><w:${macroName} w:val="SyntheticMacro"/>`,
        ),
        "ACTIVE_CONTENT_REJECTED",
      );
    }
  });

  it("renders and independently verifies a bounded English Word date format", async () => {
    const documentXml = syntheticOpc.documentXml.replace(
      '<w:dateFormat w:val="yyyy-MM-dd"/>',
      '<w:dateFormat w:val="MMMM d, yyyy"/><w:lid w:val="en-US"/><w:calendar w:val="gregorian"/><w:storeMappedDataAs w:val="dateTime"/>',
    );
    const source = await buildSyntheticDocx({ documentXml });
    const ir = compileTemplateDocx(source);
    const rendered = await renderTemplateDocx({
      source,
      ir,
      resolutions: resolutionsFor(
        ir,
        new Map([["Encounter date", "2026-07-15"]]),
      ),
      validation: VALIDATION,
    });
    const xml = inspectDocxPackage(rendered.document)
      .zip.entries.get("word/document.xml")!
      .bytes.toString("utf8");
    expect(xml).toContain("<w:t>July 15, 2026</w:t>");
    expect(rendered.verification.verified).toBe(true);
  });

  it("certification-blocks unprofiled date locale and calendar semantics", async () => {
    const documentXml = syntheticOpc.documentXml.replace(
      '<w:dateFormat w:val="yyyy-MM-dd"/>',
      '<w:dateFormat w:val="MMMM d, yyyy"/><w:lid w:val="ar-SA"/><w:calendar w:val="hijri"/><w:storeMappedDataAs w:val="text"/>',
    );
    const ir = compileTemplateDocx(await buildSyntheticDocx({ documentXml }));
    expect(
      ir.fields.find((field) => field.originalLabel === "Encounter date")
        ?.detectionStatus,
    ).toBe("unsupported");
    expect(ir.unsupported).toContainEqual(
      expect.objectContaining({
        code: "DATE_CONTROL_PROFILE_UNSUPPORTED",
        blocksCertification: true,
      }),
    );
  });

  it("rejects duplicate date behavior children", async () => {
    await expectCompileFailure(
      syntheticOpc.documentXml.replace(
        '<w:dateFormat w:val="yyyy-MM-dd"/>',
        '<w:dateFormat w:val="yyyy-MM-dd"/><w:dateFormat w:val="MM/dd/yyyy"/>',
      ),
      "XML_INVALID",
    );
  });

  it("blocks mixed run formatting and requires explicit multiline text", async () => {
    const mixedRuns = syntheticOpc.documentXml.replace(
      "<w:r><w:t>Enter assessment</w:t></w:r>",
      '<w:r><w:t>Enter</w:t></w:r><w:r><w:rPr><w:b/><w:sz w:val="56"/></w:rPr><w:t> assessment</w:t></w:r>',
    );
    const mixedIr = compileTemplateDocx(
      await buildSyntheticDocx({ documentXml: mixedRuns }),
    );
    expect(
      mixedIr.fields.find(
        (field) => field.originalLabel === "Assessment narrative",
      )?.detectionStatus,
    ).toBe("unsupported");

    const scalarOnlyXml = syntheticOpc.documentXml.replace(
      '<w:text w:multiLine="true"/>',
      "<w:text/>",
    );
    const source = await buildSyntheticDocx({ documentXml: scalarOnlyXml });
    const ir = compileTemplateDocx(source);
    await expect(
      renderTemplateDocx({
        source,
        ir,
        resolutions: resolutionsFor(
          ir,
          new Map([["Assessment narrative", "Line one\nLine two"]]),
        ),
        validation: VALIDATION,
      }),
    ).rejects.toMatchObject({ code: "FIELD_VALUE_INVALID" });
  });

  it("preserves a styled blank-cell run as the visible formatting owner", async () => {
    const documentXml = syntheticOpc.documentXml.replace(
      "<w:tc><w:p/></w:tc></w:tr>",
      '<w:tc><w:p><w:r><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:r></w:p></w:tc></w:tr>',
    );
    const source = await buildSyntheticDocx({ documentXml });
    const ir = compileTemplateDocx(source);
    const field = ir.fields.find(
      (candidate) => candidate.originalLabel === "Additional finding",
    );
    expect(field?.detectionStatus).toBe("needs_confirmation");
    const rendered = await renderTemplateDocx({
      source,
      ir,
      resolutions: resolutionsFor(
        ir,
        new Map([["Additional finding", "Synthetic styled value"]]),
      ),
      validation: VALIDATION,
    });
    const xml = inspectDocxPackage(rendered.document)
      .zip.entries.get("word/document.xml")!
      .bytes.toString("utf8");
    expect(xml).toContain(
      '<w:r><w:rPr><w:b/><w:sz w:val="28"/></w:rPr><w:t>Synthetic styled value</w:t></w:r>',
    );
  });

  it("renders multiline styled blank-cell text as explicit Word breaks", async () => {
    const documentXml = syntheticOpc.documentXml.replace(
      "<w:tc><w:p/></w:tc></w:tr>",
      '<w:tc><w:p><w:r><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:r></w:p></w:tc></w:tr>',
    );
    const source = await buildSyntheticDocx({ documentXml });
    const ir = compileTemplateDocx(source);
    const field = ir.fields.find(
      (candidate) => candidate.originalLabel === "Additional finding",
    );
    expect(field?.rendererBinding.bindingType).toBe("table_cell");

    const rendered = await renderTemplateDocx({
      source,
      ir,
      resolutions: resolutionsFor(
        ir,
        new Map([["Additional finding", "Line one\nLine two"]]),
      ),
      validation: VALIDATION,
    });
    const xml = inspectDocxPackage(rendered.document)
      .zip.entries.get("word/document.xml")!
      .bytes.toString("utf8");
    expect(xml).toContain(
      '<w:r><w:rPr><w:b/><w:sz w:val="28"/></w:rPr><w:t>Line one</w:t><w:br/><w:t>Line two</w:t></w:r>',
    );
    expect(rendered.verification).toMatchObject({
      verified: true,
      packageCheck: "verified",
      fieldCheck: "verified",
      staticRegionCheck: "verified",
      fields: expect.arrayContaining([
        expect.objectContaining({
          fieldId: field?.fieldId,
          occurrences: 1,
          status: "verified",
          bindingEvidence: expect.objectContaining({ status: "verified" }),
        }),
      ]),
    });
  });

  it("blocks orphan repeat items and unbounded table topology", async () => {
    const orphanItem =
      '<w:sdt><w:sdtPr><w:id w:val="990"/><w15:repeatingSectionItem/></w:sdtPr><w:sdtContent><w:p><w:r><w:t>Synthetic orphan item</w:t></w:r></w:p></w:sdtContent></w:sdt>';
    const documentXml = syntheticOpc.documentXml
      .replace("<w:sectPr>", `${orphanItem}<w:sectPr>`)
      .replace('w:gridSpan w:val="2"', 'w:gridSpan w:val="999999999"');
    const ir = compileTemplateDocx(await buildSyntheticDocx({ documentXml }));
    expect(
      ir.unsupported.filter(
        (item) => item.code === "REPEATING_STRUCTURE_UNSUPPORTED_SAFE_ALPHA",
      ).length,
    ).toBeGreaterThanOrEqual(2);
    expect(ir.unsupported).toContainEqual(
      expect.objectContaining({
        code: "TABLE_TOPOLOGY_UNSUPPORTED",
        detail: expect.stringContaining("grid span"),
      }),
    );
  });

  it("rejects dangling story references and orphan header parts", async () => {
    await expectCompileFailure(
      syntheticOpc.documentXml.replace('r:id="rIdHeader"', 'r:id="rIdMissing"'),
      "OPC_RELATIONSHIP_INVALID",
    );

    const contentTypes = syntheticOpc.contentTypes.replace(
      "</Types>",
      '<Override PartName="/word/header2.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/></Types>',
    );
    await expect(
      buildSyntheticDocx({
        contentTypes,
        extraEntries: {
          "word/header2.xml":
            '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Synthetic orphan</w:t></w:r></w:p></w:hdr>',
        },
      }).then((source) => compileTemplateDocx(source)),
    ).rejects.toMatchObject({ code: "OPC_RELATIONSHIP_INVALID" });
  });

  it("rejects malformed section topology and duplicate story roles", async () => {
    const malformedLocation = syntheticOpc.documentXml.replace(
      '<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr>',
      '<w:p><w:r><w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr></w:r></w:p>',
    );
    await expectCompileFailure(malformedLocation, "OPC_RELATIONSHIP_INVALID");

    const duplicateDefault = syntheticOpc.documentXml.replace(
      '<w:headerReference w:type="default" r:id="rIdHeader"/>',
      '<w:headerReference w:type="default" r:id="rIdHeader"/><w:headerReference w:type="default" r:id="rIdHeader"/>',
    );
    await expectCompileFailure(duplicateDefault, "OPC_RELATIONSHIP_INVALID");
  });

  it("requires exact header relationship and content types", async () => {
    await expect(
      buildSyntheticDocx({
        documentRelationships: syntheticOpc.documentRelationships.replace(
          "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header",
          "urn:synthetic/header",
        ),
      }).then((source) => compileTemplateDocx(source)),
    ).rejects.toMatchObject({ code: "OPC_RELATIONSHIP_INVALID" });

    await expect(
      buildSyntheticDocx({
        contentTypes: syntheticOpc.contentTypes.replace(
          "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml",
          "application/x-synthetic.header+xml",
        ),
      }).then((source) => compileTemplateDocx(source)),
    ).rejects.toMatchObject({ code: "OPC_CONTENT_TYPE_INVALID" });

    await expect(
      buildSyntheticDocx({
        extraEntries: {
          "word/header1.xml":
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p/></w:body></w:document>',
        },
      }).then((source) => compileTemplateDocx(source)),
    ).rejects.toMatchObject({ code: "OPC_RELATIONSHIP_INVALID" });
  });

  it("rejects an orphan header-shaped part hidden behind application/xml", async () => {
    await expect(
      buildSyntheticDocx({
        extraEntries: {
          "word/header2.xml":
            '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Synthetic orphan</w:t></w:r></w:p></w:hdr>',
        },
      }).then((source) => compileTemplateDocx(source)),
    ).rejects.toMatchObject({ code: "OPC_RELATIONSHIP_INVALID" });
  });

  it("enforces legacy text maximum length at render time", async () => {
    const legacy =
      '<w:p><w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Legacy bounded note"/><w:textInput><w:type w:val="regular"/><w:maxLength w:val="1"/></w:textInput></w:ffData></w:fldChar></w:r><w:r><w:instrText> FORMTEXT </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t></w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>';
    const source = await buildSyntheticDocx({
      documentXml: syntheticOpc.documentXml.replace(
        "<w:sectPr>",
        `${legacy}<w:sectPr>`,
      ),
    });
    const ir = compileTemplateDocx(source);
    await expect(
      renderTemplateDocx({
        source,
        ir,
        resolutions: resolutionsFor(
          ir,
          new Map([["Legacy bounded note", "Too long"]]),
        ),
        validation: VALIDATION,
      }),
    ).rejects.toMatchObject({ code: "FIELD_VALUE_INVALID" });
  });
});

async function expectCompileFailure(
  documentXml: string,
  code: string,
): Promise<void> {
  await expect(
    buildSyntheticDocx({ documentXml }).then((source) =>
      compileTemplateDocx(source),
    ),
  ).rejects.toMatchObject({ code });
}
