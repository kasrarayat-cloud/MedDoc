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

const MISPLACED_WORD_CONTROL_CASES = [
  ["native bibliography", "<w:bibliography/>", "XML_INVALID"],
  ["native citation", "<w:citation/>", "XML_INVALID"],
  ["native combo box", "<w:comboBox/>", "XML_INVALID"],
  ["native date", "<w:date/>", "XML_INVALID"],
  ["native building-block gallery", "<w:docPartList/>", "XML_INVALID"],
  ["native document part", "<w:docPartObj/>", "XML_INVALID"],
  ["native dropdown", "<w:dropDownList/>", "XML_INVALID"],
  ["native equation", "<w:equation/>", "XML_INVALID"],
  ["native group", "<w:group/>", "XML_INVALID"],
  ["native picture", "<w:picture/>", "XML_INVALID"],
  ["native rich text", "<w:richText/>", "XML_INVALID"],
  ["native text", "<w:text/>", "XML_INVALID"],
  ["modern checkbox", "<w14:checkbox/>", "XML_INVALID"],
  ["modern entity picker", "<w14:entityPicker/>", "XML_INVALID"],
  ["repeating section", "<w15:repeatingSection/>", "XML_INVALID"],
  ["repeating section item", "<w15:repeatingSectionItem/>", "XML_INVALID"],
  ["content-control properties", "<w:sdtPr/>", "XML_INVALID"],
  ["content-control body", "<w:sdtContent/>", "XML_INVALID"],
  ["content-control alias", '<w:alias w:val="Orphan"/>', "XML_INVALID"],
  [
    "content-control data binding",
    '<w:dataBinding w:xpath="/root/value"/>',
    "XML_INVALID",
  ],
  ["content-control id", '<w:id w:val="901"/>', "XML_INVALID"],
  ["content-control lock", '<w:lock w:val="sdtLocked"/>', "XML_INVALID"],
  ["content-control placeholder", "<w:placeholder/>", "XML_INVALID"],
  ["content-control placeholder state", "<w:showingPlcHdr/>", "XML_INVALID"],
  ["content-control tag", '<w:tag w:val="orphan"/>', "XML_INVALID"],
  ["temporary content control", "<w:temporary/>", "XML_INVALID"],
  [
    "document-part category",
    '<w:docPartCategory w:val="Synthetic"/>',
    "XML_INVALID",
  ],
  [
    "document-part gallery",
    '<w:docPartGallery w:val="Synthetic"/>',
    "XML_INVALID",
  ],
  ["document-part unique marker", "<w:docPartUnique/>", "XML_INVALID"],
  [
    "native list item",
    '<w:listItem w:displayText="Left" w:value="L"/>',
    "XML_INVALID",
  ],
  ["native combo last value", '<w:lastValue w:val="L"/>', "XML_INVALID"],
  ["date calendar", '<w:calendar w:val="gregorian"/>', "XML_INVALID"],
  ["date format", '<w:dateFormat w:val="yyyy-MM-dd"/>', "XML_INVALID"],
  ["date language", '<w:lid w:val="en-US"/>', "XML_INVALID"],
  [
    "date storage behavior",
    '<w:storeMappedDataAs w:val="dateTime"/>',
    "XML_INVALID",
  ],
  ["modern checkbox state", '<w14:checked w14:val="0"/>', "XML_INVALID"],
  ["modern checked glyph", '<w14:checkedState w14:val="2612"/>', "XML_INVALID"],
  [
    "modern unchecked glyph",
    '<w14:uncheckedState w14:val="2610"/>',
    "XML_INVALID",
  ],
  ["legacy checkbox", "<w:checkBox/>", "XML_INVALID"],
  ["legacy dropdown", "<w:ddList/>", "XML_INVALID"],
  ["legacy text input", "<w:textInput/>", "XML_INVALID"],
  ["legacy form data", "<w:ffData/>", "XML_INVALID"],
  ["legacy calculate-on-exit", "<w:calcOnExit/>", "XML_INVALID"],
  ["legacy enabled behavior", "<w:enabled/>", "XML_INVALID"],
  ["legacy help text", "<w:helpText/>", "XML_INVALID"],
  ["legacy numeric label", '<w:label w:val="1"/>', "XML_INVALID"],
  ["legacy status text", "<w:statusText/>", "XML_INVALID"],
  ["legacy tab index", '<w:tabIndex w:val="1"/>', "XML_INVALID"],
  ["legacy checkbox state", '<w:checked w:val="1"/>', "XML_INVALID"],
  ["legacy checkbox size", '<w:size w:val="20"/>', "XML_INVALID"],
  ["legacy automatic checkbox size", "<w:sizeAuto/>", "XML_INVALID"],
  ["legacy list entry", '<w:listEntry w:val="Mild"/>', "XML_INVALID"],
  ["legacy list result", '<w:result w:val="0"/>', "XML_INVALID"],
  ["legacy text format", '<w:format w:val="Uppercase"/>', "XML_INVALID"],
  ["legacy text maximum length", '<w:maxLength w:val="8"/>', "XML_INVALID"],
  ["legacy text type", '<w:type w:val="regular"/>', "XML_INVALID"],
  ["legacy default", '<w:default w:val="0"/>', "XML_INVALID"],
  ["table grid", "<w:tblGrid/>", "XML_INVALID"],
  ["table grid column", '<w:gridCol w:w="1200"/>', "XML_INVALID"],
  ["table cell grid span", '<w:gridSpan w:val="2"/>', "XML_INVALID"],
  ["table cell horizontal merge", '<w:hMerge w:val="restart"/>', "XML_INVALID"],
  ["table cell vertical merge", '<w:vMerge w:val="restart"/>', "XML_INVALID"],
  ["table cell properties", "<w:tcPr/>", "XML_INVALID"],
  ["field instruction", "<w:instrText> PAGE </w:instrText>", "XML_INVALID"],
  ["field character", '<w:fldChar w:fldCharType="begin"/>', "XML_INVALID"],
  ["simple field", '<w:fldSimple w:instr="PAGE"/>', "XML_INVALID"],
  [
    "legacy entry macro",
    '<w:entryMacro w:val="Synthetic"/>',
    "ACTIVE_CONTENT_REJECTED",
  ],
  [
    "legacy exit macro",
    '<w:exitMacro w:val="Synthetic"/>',
    "ACTIVE_CONTENT_REJECTED",
  ],
] as const;

function sdtWithProperties(properties: string): string {
  return `<w:sdt><w:sdtPr>${properties}</w:sdtPr><w:sdtContent><w:r><w:t>Wrong parent</w:t></w:r></w:sdtContent></w:sdt>`;
}

function legacyFieldWithFormData(formData: string): string {
  return `<w:p><w:r><w:fldChar w:fldCharType="begin"><w:ffData>${formData}</w:ffData></w:fldChar></w:r><w:r><w:instrText> FORMTEXT </w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>`;
}

const WRONG_PARENT_WORD_CONTROL_CASES = [
  ...[
    "bibliography",
    "citation",
    "comboBox",
    "date",
    "docPartList",
    "docPartObj",
    "dropDownList",
    "equation",
    "group",
    "picture",
    "richText",
    "text",
  ].map(
    (name) =>
      [
        `native ${name} nested below content-control metadata`,
        sdtWithProperties(`<w:placeholder><w:${name}/></w:placeholder>`),
      ] as const,
  ),
  ...["checkbox", "entityPicker"].map(
    (name) =>
      [
        `modern ${name} nested below content-control metadata`,
        sdtWithProperties(`<w:placeholder><w14:${name}/></w:placeholder>`),
      ] as const,
  ),
  ...["repeatingSection", "repeatingSectionItem"].map(
    (name) =>
      [
        `${name} nested below content-control metadata`,
        sdtWithProperties(`<w:placeholder><w15:${name}/></w:placeholder>`),
      ] as const,
  ),
  ...[
    '<w:alias w:val="Nested"/>',
    '<w:dataBinding w:xpath="/root/value"/>',
    '<w:id w:val="999"/>',
    '<w:lock w:val="sdtLocked"/>',
    "<w:placeholder/>",
    "<w:showingPlcHdr/>",
    '<w:tag w:val="nested"/>',
    "<w:temporary/>",
  ].map(
    (child) =>
      [
        `content-control metadata ${child} nested below placeholder`,
        sdtWithProperties(`<w:placeholder>${child}</w:placeholder><w:text/>`),
      ] as const,
  ),
  [
    "native list item nested below a paragraph",
    sdtWithProperties(
      '<w:dropDownList><w:p><w:listItem w:displayText="Left" w:value="L"/></w:p></w:dropDownList>',
    ),
  ],
  [
    "native combo last value nested below a paragraph",
    sdtWithProperties(
      '<w:comboBox><w:p><w:lastValue w:val="L"/></w:p></w:comboBox>',
    ),
  ],
  ...[
    '<w:docPartCategory w:val="Synthetic"/>',
    '<w:docPartGallery w:val="Synthetic"/>',
    "<w:docPartUnique/>",
  ].map(
    (child) =>
      [
        `document-part behavior ${child} nested below a paragraph`,
        sdtWithProperties(`<w:docPartList><w:p>${child}</w:p></w:docPartList>`),
      ] as const,
  ),
  ...[
    '<w:calendar w:val="gregorian"/>',
    '<w:dateFormat w:val="yyyy-MM-dd"/>',
    '<w:lid w:val="en-US"/>',
    '<w:storeMappedDataAs w:val="dateTime"/>',
  ].map(
    (child) =>
      [
        `date behavior ${child} nested below a paragraph`,
        sdtWithProperties(`<w:date><w:p>${child}</w:p></w:date>`),
      ] as const,
  ),
  ...[
    '<w14:checked w14:val="0"/>',
    '<w14:checkedState w14:val="2612"/>',
    '<w14:uncheckedState w14:val="2610"/>',
  ].map(
    (child) =>
      [
        `modern checkbox behavior ${child} nested below a paragraph`,
        sdtWithProperties(`<w14:checkbox><w:p>${child}</w:p></w14:checkbox>`),
      ] as const,
  ),
  ...["checkBox", "ddList", "textInput"].map(
    (name) =>
      [
        `legacy ${name} nested below form-field metadata`,
        legacyFieldWithFormData(`<w:helpText><w:${name}/></w:helpText>`),
      ] as const,
  ),
  [
    "legacy form data nested below field data",
    '<w:p><w:r><w:fldChar w:fldCharType="begin"><w:fldData><w:ffData><w:textInput/></w:ffData></w:fldData></w:fldChar></w:r></w:p>',
  ],
  [
    "legacy form data attached to a non-begin field character",
    '<w:p><w:r><w:fldChar w:fldCharType="separate"><w:ffData><w:textInput/></w:ffData></w:fldChar></w:r></w:p>',
  ],
  ...[
    "<w:calcOnExit/>",
    "<w:enabled/>",
    "<w:helpText/>",
    '<w:label w:val="1"/>',
    '<w:name w:val="Nested"/>',
    "<w:statusText/>",
    '<w:tabIndex w:val="1"/>',
  ].map(
    (child) =>
      [
        `legacy form metadata ${child} nested below text input`,
        legacyFieldWithFormData(`<w:textInput>${child}</w:textInput>`),
      ] as const,
  ),
  ...[
    '<w:checked w:val="1"/>',
    '<w:default w:val="0"/>',
    '<w:size w:val="20"/>',
    "<w:sizeAuto/>",
  ].map(
    (child) =>
      [
        `legacy checkbox behavior ${child} nested below a paragraph`,
        legacyFieldWithFormData(`<w:checkBox><w:p>${child}</w:p></w:checkBox>`),
      ] as const,
  ),
  ...[
    '<w:default w:val="0"/>',
    '<w:listEntry w:val="Mild"/>',
    '<w:result w:val="0"/>',
  ].map(
    (child) =>
      [
        `legacy dropdown behavior ${child} nested below a paragraph`,
        legacyFieldWithFormData(`<w:ddList><w:p>${child}</w:p></w:ddList>`),
      ] as const,
  ),
  ...[
    '<w:default w:val="Synthetic"/>',
    '<w:format w:val="Uppercase"/>',
    '<w:maxLength w:val="8"/>',
    '<w:type w:val="regular"/>',
  ].map(
    (child) =>
      [
        `legacy text behavior ${child} nested below a paragraph`,
        legacyFieldWithFormData(
          `<w:textInput><w:p>${child}</w:p></w:textInput>`,
        ),
      ] as const,
  ),
  [
    "table grid nested below table properties",
    "<w:tbl><w:tblPr><w:tblGrid/></w:tblPr><w:tr><w:tc><w:p/></w:tc></w:tr></w:tbl>",
  ],
  [
    "table grid column nested below table properties",
    '<w:tbl><w:tblPr><w:gridCol w:w="1200"/></w:tblPr><w:tr><w:tc><w:p/></w:tc></w:tr></w:tbl>',
  ],
  ...[
    '<w:gridSpan w:val="2"/>',
    '<w:hMerge w:val="restart"/>',
    '<w:vMerge w:val="restart"/>',
  ].map(
    (child) =>
      [
        `table cell behavior ${child} nested below cell content`,
        `<w:tbl><w:tr><w:tc><w:p>${child}</w:p></w:tc></w:tr></w:tbl>`,
      ] as const,
  ),
  [
    "table cell properties nested below a paragraph",
    "<w:tbl><w:tr><w:tc><w:p><w:tcPr/></w:p></w:tc></w:tr></w:tbl>",
  ],
  [
    "field instruction nested below paragraph properties",
    "<w:p><w:pPr><w:instrText> PAGE </w:instrText></w:pPr></w:p>",
  ],
  [
    "field character nested below paragraph properties",
    '<w:p><w:pPr><w:fldChar w:fldCharType="begin"/></w:pPr></w:p>',
  ],
  [
    "simple field nested below paragraph properties",
    '<w:p><w:pPr><w:fldSimple w:instr="PAGE"/></w:pPr></w:p>',
  ],
] as const;

const DUPLICATE_WORD_SINGLETON_CASES = [
  ...[
    ['<w:alias w:val="One"/>', '<w:alias w:val="Two"/>'],
    ['<w:dataBinding w:xpath="/one"/>', '<w:dataBinding w:xpath="/two"/>'],
    ['<w:id w:val="970"/>', '<w:id w:val="971"/>'],
    ['<w:lock w:val="sdtLocked"/>', '<w:lock w:val="contentLocked"/>'],
    ["<w:placeholder/>", "<w:placeholder/>"],
    ["<w:showingPlcHdr/>", "<w:showingPlcHdr/>"],
    ['<w:tag w:val="one"/>', '<w:tag w:val="two"/>'],
    ["<w:temporary/>", "<w:temporary/>"],
  ].map(
    ([left, right]) =>
      [
        `duplicate content-control singleton ${left}`,
        sdtWithProperties(`${left}${right}<w:text/>`),
      ] as const,
  ),
  [
    "duplicate content-control type",
    sdtWithProperties("<w:text/><w:richText/>"),
  ],
  [
    "duplicate content-control properties",
    "<w:sdt><w:sdtPr><w:text/></w:sdtPr><w:sdtPr><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Duplicate</w:t></w:r></w:sdtContent></w:sdt>",
  ],
  [
    "duplicate content-control bodies",
    "<w:sdt><w:sdtPr><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>One</w:t></w:r></w:sdtContent><w:sdtContent><w:r><w:t>Two</w:t></w:r></w:sdtContent></w:sdt>",
  ],
  ...["docPartCategory", "docPartGallery", "docPartUnique"].map(
    (name) =>
      [
        `duplicate document-part singleton ${name}`,
        sdtWithProperties(
          `<w:docPartList><w:${name}/><w:${name}/></w:docPartList>`,
        ),
      ] as const,
  ),
  [
    "duplicate combo-box last value",
    sdtWithProperties(
      '<w:comboBox><w:lastValue w:val="one"/><w:lastValue w:val="two"/><w:listItem w:displayText="One" w:value="one"/></w:comboBox>',
    ),
  ],
  ...["checked", "checkedState", "uncheckedState"].map(
    (name) =>
      [
        `duplicate modern checkbox singleton ${name}`,
        sdtWithProperties(
          `<w14:checkbox><w14:${name} w14:val="0"/><w14:${name} w14:val="1"/></w14:checkbox>`,
        ),
      ] as const,
  ),
  ...["dateFormat", "lid", "calendar", "storeMappedDataAs"].map(
    (name) =>
      [
        `duplicate date singleton ${name}`,
        sdtWithProperties(
          `<w:date><w:${name} w:val="one"/><w:${name} w:val="two"/></w:date>`,
        ),
      ] as const,
  ),
  ...[
    "calcOnExit",
    "enabled",
    "helpText",
    "label",
    "name",
    "statusText",
    "tabIndex",
  ].map(
    (name) =>
      [
        `duplicate legacy form singleton ${name}`,
        legacyFieldWithFormData(`<w:${name}/><w:${name}/><w:textInput/>`),
      ] as const,
  ),
  [
    "duplicate legacy field controls",
    legacyFieldWithFormData("<w:textInput/><w:ddList/>"),
  ],
  ...["default", "format", "maxLength", "type"].map(
    (name) =>
      [
        `duplicate legacy text singleton ${name}`,
        legacyFieldWithFormData(
          `<w:textInput><w:${name}/><w:${name}/></w:textInput>`,
        ),
      ] as const,
  ),
  ...["default", "result"].map(
    (name) =>
      [
        `duplicate legacy dropdown singleton ${name}`,
        legacyFieldWithFormData(
          `<w:ddList><w:${name}/><w:${name}/><w:listEntry w:val="One"/></w:ddList>`,
        ),
      ] as const,
  ),
  ...["checked", "default", "size", "sizeAuto"].map(
    (name) =>
      [
        `duplicate legacy checkbox singleton ${name}`,
        legacyFieldWithFormData(
          `<w:checkBox><w:${name}/><w:${name}/></w:checkBox>`,
        ),
      ] as const,
  ),
  [
    "mutually exclusive fixed and automatic legacy checkbox sizes",
    legacyFieldWithFormData(
      '<w:checkBox><w:size w:val="20"/><w:sizeAuto/></w:checkBox>',
    ),
  ],
  ...["gridSpan", "hMerge", "vMerge"].map(
    (name) =>
      [
        `duplicate table-cell singleton ${name}`,
        `<w:tbl><w:tr><w:tc><w:tcPr><w:${name}/><w:${name}/></w:tcPr><w:p/></w:tc></w:tr></w:tbl>`,
      ] as const,
  ),
  [
    "duplicate table grid",
    "<w:tbl><w:tblGrid/><w:tblGrid/><w:tr><w:tc><w:p/></w:tc></w:tr></w:tbl>",
  ],
  [
    "duplicate table-cell properties",
    "<w:tbl><w:tr><w:tc><w:tcPr/><w:tcPr/><w:p/></w:tc></w:tr></w:tbl>",
  ],
] as const;

function minimalBoundaryDocument(
  extraXml = "",
  includeHeaderAndFooter = false,
): string {
  const storyReferences = includeHeaderAndFooter
    ? '<w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/>'
    : "";
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
  xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p><w:sdt><w:sdtPr><w:id w:val="900"/><w:alias w:val="Baseline field"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter value</w:t></w:r></w:sdtContent></w:sdt></w:p>
    ${extraXml}
    <w:sectPr>${storyReferences}</w:sectPr>
  </w:body>
</w:document>`;
}

const SUPPORTED_CONTROL_FRAGMENTS = `
<w:p><w:sdt><w:sdtPr><w:id w:val="901"/><w:alias w:val="Native dropdown"/><w:dropDownList><w:listItem w:displayText="Left" w:value="L"/><w:listItem w:displayText="Right" w:value="R"/></w:dropDownList></w:sdtPr><w:sdtContent><w:r><w:t>Left</w:t></w:r></w:sdtContent></w:sdt></w:p>
<w:p><w:sdt><w:sdtPr><w:id w:val="902"/><w:alias w:val="Native combo"/><w:comboBox><w:lastValue w:val="initial"/><w:listItem w:displayText="Initial" w:value="initial"/><w:listItem w:displayText="Follow-up" w:value="follow_up"/></w:comboBox></w:sdtPr><w:sdtContent><w:r><w:t>Initial</w:t></w:r></w:sdtContent></w:sdt></w:p>
<w:p><w:sdt><w:sdtPr><w:id w:val="903"/><w:alias w:val="Native date"/><w:date w:fullDate="2026-07-19T00:00:00Z"><w:dateFormat w:val="yyyy-MM-dd"/><w:lid w:val="en-US"/><w:calendar w:val="gregorian"/><w:storeMappedDataAs w:val="dateTime"/></w:date></w:sdtPr><w:sdtContent><w:r><w:t>2026-07-19</w:t></w:r></w:sdtContent></w:sdt></w:p>
<w:p><w:sdt><w:sdtPr><w:id w:val="904"/><w:alias w:val="Native checkbox"/><w14:checkbox><w14:checked w14:val="0"/><w14:checkedState w14:val="2612"/><w14:uncheckedState w14:val="2610"/></w14:checkbox></w:sdtPr><w:sdtContent><w:r><w:t>☐</w:t></w:r></w:sdtContent></w:sdt></w:p>
<w:p><w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Legacy checkbox"/><w:enabled/><w:calcOnExit w:val="0"/><w:helpText w:type="text" w:val="Synthetic help"/><w:label w:val="1"/><w:statusText w:type="text" w:val="Synthetic status"/><w:tabIndex w:val="1"/><w:checkBox><w:sizeAuto/><w:default w:val="0"/><w:checked w:val="1"/></w:checkBox></w:ffData></w:fldChar></w:r><w:r><w:instrText> FORMCHECKBOX </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>☒</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>
<w:p><w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Legacy dropdown"/><w:ddList><w:default w:val="0"/><w:result w:val="1"/><w:listEntry w:val="Mild"/><w:listEntry w:val="Severe"/></w:ddList></w:ffData></w:fldChar></w:r><w:r><w:instrText> FORMDROPDOWN </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>Severe</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>
<w:p><w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Legacy text"/><w:textInput><w:type w:val="regular"/><w:default w:val="Synthetic default"/><w:maxLength w:val="64"/></w:textInput></w:ffData></w:fldChar></w:r><w:r><w:instrText> FORMTEXT </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>Synthetic default</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>`;

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
  it("admits the minimal synthetic placement-control baseline", async () => {
    const ir = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: minimalBoundaryDocument(),
      }),
    );
    expect(ir.fields).toHaveLength(1);
    expect(ir.fields[0]).toMatchObject({
      originalLabel: "Baseline field",
      detectionStatus: "recognized",
    });
    expect(ir.unsupported.filter((item) => item.blocksCertification)).toEqual(
      [],
    );
  });

  it("admits every supported native and legacy control in its exact parent shape", async () => {
    const ir = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: minimalBoundaryDocument(SUPPORTED_CONTROL_FRAGMENTS, true),
      }),
    );
    expect(ir.fields.map((field) => field.originalLabel)).toEqual([
      "Baseline field",
      "Native dropdown",
      "Native combo",
      "Native date",
      "Native checkbox",
      "Legacy checkbox",
      "Legacy dropdown",
      "Legacy text",
      "Practice display name",
    ]);
    expect(ir.unsupported.filter((item) => item.blocksCertification)).toEqual(
      [],
    );
  });

  it("preserves valid section, ruby, and table-style placement contexts", async () => {
    const layoutXml =
      '<w:p><w:pPr><w:sectPr><w:type w:val="nextPage"/></w:sectPr></w:pPr><w:r><w:ruby><w:rubyPr><w:lid w:val="ja-JP"/></w:rubyPr><w:rt><w:r><w:t>ご</w:t></w:r></w:rt><w:rubyBase><w:r><w:t>語</w:t></w:r></w:rubyBase></w:ruby></w:r></w:p>';
    const source = await buildSyntheticDocx({
      documentXml: minimalBoundaryDocument(layoutXml),
      extraEntries: {
        "word/styles.xml":
          '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="table" w:styleId="SyntheticTable"><w:name w:val="Synthetic table"/><w:tcPr><w:tcFitText/></w:tcPr><w:tblStylePr w:type="firstRow"><w:tcPr><w:shd w:fill="E2E8F0"/></w:tcPr></w:tblStylePr></w:style></w:styles>',
      },
    });
    const ir = compileTemplateDocx(source);
    expect(ir.fields).toHaveLength(1);
    expect(ir.unsupported.filter((item) => item.blocksCertification)).toEqual(
      [],
    );
  });

  it("certification-blocks well-placed unsupported SDT types", async () => {
    const richText = `<w:p>${sdtWithProperties(
      '<w:id w:val="960"/><w:alias w:val="Synthetic rich narrative"/><w:richText/>',
    )}</w:p>`;
    const unsupportedTypes =
      '<w:p><w:sdt><w:sdtPr><w:id w:val="961"/><w:alias w:val="Synthetic gallery"/><w:docPartList><w:docPartGallery w:val="Synthetic"/></w:docPartList></w:sdtPr><w:sdtContent><w:r><w:t>Gallery</w:t></w:r></w:sdtContent></w:sdt></w:p><w:p><w:sdt><w:sdtPr><w:id w:val="962"/><w:alias w:val="Synthetic entity"/><w14:entityPicker/></w:sdtPr><w:sdtContent><w:r><w:t>Entity</w:t></w:r></w:sdtContent></w:sdt></w:p>';
    const ir = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: minimalBoundaryDocument(richText + unsupportedTypes),
      }),
    );
    expect(ir.unsupported).toContainEqual(
      expect.objectContaining({
        code: "RICH_TEXT_CONTENT_CONTROL_UNSUPPORTED_SAFE_ALPHA",
        label: "Synthetic rich narrative",
        blocksCertification: true,
      }),
    );
    expect(
      ir.unsupported.filter(
        (item) => item.code === "UNSUPPORTED_CONTENT_CONTROL",
      ),
    ).toEqual([
      expect.objectContaining({ label: "Synthetic gallery" }),
      expect.objectContaining({ label: "Synthetic entity" }),
    ]);
  });

  it("rejects mail-merge field maps before overloaded control children are interpreted", async () => {
    await expectCompileFailure(
      minimalBoundaryDocument(
        '<w:mailMerge><w:odso><w:fieldMapData><w:type w:val="dbColumn"/><w:lid w:val="en-US"/></w:fieldMapData></w:odso></w:mailMerge>',
      ),
      "ACTIVE_CONTENT_REJECTED",
    );
  });

  it("admits a well-placed repeating section but keeps certification blocked", async () => {
    const repeating =
      '<w:sdt><w:sdtPr><w:id w:val="950"/><w:alias w:val="Synthetic repeated findings"/><w15:repeatingSection/></w:sdtPr><w:sdtContent><w:tbl><w:tblGrid><w:gridCol w:w="2400"/></w:tblGrid><w:sdt><w:sdtPr><w:id w:val="951"/><w15:repeatingSectionItem/></w:sdtPr><w:sdtContent><w:tr><w:tc><w:p><w:r><w:t>Synthetic finding</w:t></w:r></w:p></w:tc></w:tr></w:sdtContent></w:sdt></w:tbl></w:sdtContent></w:sdt>';
    const ir = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: minimalBoundaryDocument(repeating),
      }),
    );
    expect(ir.unsupported).toContainEqual(
      expect.objectContaining({
        code: "REPEATING_STRUCTURE_UNSUPPORTED_SAFE_ALPHA",
        blocksCertification: true,
      }),
    );
  });

  it.each(MISPLACED_WORD_CONTROL_CASES)(
    "rejects misplaced %s with %s",
    async (_name, fragment, code) => {
      await expectCompileFailure(minimalBoundaryDocument(fragment), code);
    },
  );

  it.each(WRONG_PARENT_WORD_CONTROL_CASES)(
    "rejects %s",
    async (_name, fragment) => {
      await expectCompileFailure(
        minimalBoundaryDocument(fragment),
        "XML_INVALID",
      );
    },
  );

  it.each(DUPLICATE_WORD_SINGLETON_CASES)(
    "rejects %s",
    async (_name, fragment) => {
      await expectCompileFailure(
        minimalBoundaryDocument(fragment),
        "XML_INVALID",
      );
    },
  );

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

    const legacyCheckedShadow = minimalBoundaryDocument(
      legacyFieldWithFormData(
        '<w:name w:val="Legacy checked shadow"/><w:checkBox><w:checked evil:val="1" w:val="0"/></w:checkBox>',
      ),
    ).replace(
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"',
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:evil="urn:synthetic:evil"',
    );
    await expectCompileFailure(legacyCheckedShadow, "ACTIVE_CONTENT_REJECTED");
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
