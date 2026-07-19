import { describe, expect, it } from "vitest";

import type { TemplateDocIR, TemplateField } from "../../template-twin/ir";
import {
  TAB_ONLY_BLANK_TABLE_CELL_PROFILE,
  compileTemplateDocx,
} from "../compiler";
import { buildSyntheticDocx } from "./synthetic-docx";

const TAB_STOP_PROPERTIES = [
  "<w:pPr>",
  '<w:widowControl w:val="0"/>',
  '<w:tabs><w:tab w:val="left" w:pos="2520"/></w:tabs>',
  '<w:autoSpaceDE w:val="0"/>',
  '<w:autoSpaceDN w:val="0"/>',
  '<w:adjustRightInd w:val="0"/>',
  '<w:jc w:val="center"/>',
  "<w:rPr>",
  '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Times New Roman" w:cs="Times New Roman"/>',
  "<w:b/>",
  "<w:bCs/>",
  '<w:color w:val="000000"/>',
  '<w:kern w:val="0"/>',
  '<w:sz w:val="22"/>',
  '<w:szCs w:val="22"/>',
  '<w14:ligatures w14:val="none"/>',
  "</w:rPr>",
  "</w:pPr>",
].join("");

function targetCell(
  paragraphBody = TAB_STOP_PROPERTIES,
  cellProperties = "",
): string {
  return `<w:tc>${cellProperties}<w:p>${paragraphBody}</w:p></w:tc>`;
}

function documentXml(input: { target: string; extraRows?: string }): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
  xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
  xmlns:evil="https://synthetic.test/foreign-word-shadow"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:tbl>
      <w:tblGrid><w:gridCol w:w="2200"/><w:gridCol w:w="5000"/></w:tblGrid>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Plan item</w:t></w:r></w:p></w:tc>
        ${input.target}
      </w:tr>
      ${input.extraRows ?? ""}
    </w:tbl>
    <w:sectPr/>
  </w:body>
</w:document>`;
}

async function compileTarget(
  target: string,
  extraRows?: string,
): Promise<TemplateDocIR> {
  return compileTemplateDocx(
    await buildSyntheticDocx({
      documentXml: documentXml({ target, extraRows }),
    }),
  );
}

function tableCellFields(ir: TemplateDocIR): TemplateField[] {
  return ir.fields.filter(
    (field) => field.rendererBinding.bindingType === "table_cell",
  );
}

function complexCellBlockers(ir: TemplateDocIR) {
  return ir.unsupported.filter(
    (item) => item.code === "UNBOUND_COMPLEX_TABLE_CELL",
  );
}

describe(TAB_ONLY_BLANK_TABLE_CELL_PROFILE, () => {
  it("admits the exact paragraph tab-stop property as a physician-confirmed field", async () => {
    const ir = await compileTarget(targetCell());
    const fields = tableCellFields(ir);

    expect(complexCellBlockers(ir)).toEqual([]);
    expect(fields).toHaveLength(1);
    expect(fields[0]).toMatchObject({
      originalLabel: "Plan item",
      labelSource: "left_cell",
      detectionStatus: "needs_confirmation",
      clinicallyMaterial: true,
      rendererBinding: {
        bindingType: "table_cell",
        bindingProfile: TAB_ONLY_BLANK_TABLE_CELL_PROFILE,
        partName: "word/document.xml",
        tableIndex: 0,
        rowIndex: 0,
        cellIndex: 1,
      },
    });
  });

  it("admits Word's bounded paragraph-property revision identity", async () => {
    const ir = await compileTarget(
      targetCell().replace("<w:p>", '<w:p w:rsidRPr="00A1B2C3">'),
    );

    expect(complexCellBlockers(ir)).toEqual([]);
    expect(tableCellFields(ir)).toHaveLength(1);
    expect(tableCellFields(ir)[0]!.rendererBinding.bindingProfile).toBe(
      TAB_ONLY_BLANK_TABLE_CELL_PROFILE,
    );
  });

  it("blocks a malformed paragraph-property revision identity", async () => {
    const ir = await compileTarget(
      targetCell().replace("<w:p>", '<w:p w:rsidRPr="not-hex">'),
    );

    expect(tableCellFields(ir)).toEqual([]);
    expect(complexCellBlockers(ir)).toHaveLength(1);
  });

  it("accepts the predefined XML namespace binding when declared explicitly", async () => {
    const source = await buildSyntheticDocx({
      documentXml: documentXml({ target: targetCell() }).replace(
        "<w:document ",
        '<w:document xmlns:xml="http://www.w3.org/XML/1998/namespace" ',
      ),
    });
    const ir = compileTemplateDocx(source);

    expect(tableCellFields(ir)).toHaveLength(1);
    expect(complexCellBlockers(ir)).toEqual([]);
  });

  it("rejects an attempt to rebind the predefined XML namespace", async () => {
    const source = await buildSyntheticDocx({
      documentXml: documentXml({ target: targetCell() }).replace(
        "<w:document ",
        '<w:document xmlns:xml="https://synthetic.test/xml-shadow" ',
      ),
    });

    expect(() => compileTemplateDocx(source)).toThrowError(
      expect.objectContaining({ code: "XML_INVALID" }),
    );
  });

  it("binds the tab-stop structure into immutable identity independently of a plain blank cell", async () => {
    const tabStopIr = await compileTarget(targetCell());
    const plainIr = await compileTarget(targetCell(""));
    const changedTabStopIr = await compileTarget(
      targetCell(TAB_STOP_PROPERTIES.replace('w:pos="2520"', 'w:pos="2521"')),
    );
    const tabStop = tableCellFields(tabStopIr)[0]!;
    const plain = tableCellFields(plainIr)[0]!;
    const changed = tableCellFields(changedTabStopIr)[0]!;

    expect(tabStop.rendererBinding.sourceBindingIdentitySha256).not.toBe(
      plain.rendererBinding.sourceBindingIdentitySha256,
    );
    expect(tabStop.rendererBinding.bindingProfile).toBe(
      TAB_ONLY_BLANK_TABLE_CELL_PROFILE,
    );
    expect(plain.rendererBinding.bindingProfile).toBeUndefined();
    expect(tabStop.rendererBinding.sourceBindingIdentitySha256).not.toBe(
      changed.rendererBinding.sourceBindingIdentitySha256,
    );
    expect(tabStop.rendererBinding.certifiedBindingSha256).not.toBe(
      changed.rendererBinding.certifiedBindingSha256,
    );
  });

  it.each([
    ["a content tab in a run", `${TAB_STOP_PROPERTIES}<w:r><w:tab/></w:r>`, ""],
    [
      "tabs split across content runs",
      "<w:r><w:tab/></w:r><w:r><w:tab/></w:r>",
      "",
    ],
    [
      "a whitespace text node",
      `${TAB_STOP_PROPERTIES}<w:r><w:t xml:space="preserve"> </w:t></w:r>`,
      "",
    ],
    [
      "two tab-stop containers",
      TAB_STOP_PROPERTIES.replace(
        "</w:pPr>",
        '<w:tabs><w:tab w:val="right" w:pos="3000"/></w:tabs></w:pPr>',
      ),
      "",
    ],
    [
      "duplicate tab-stop positions",
      TAB_STOP_PROPERTIES.replace(
        "</w:tabs>",
        '<w:tab w:val="right" w:pos="2520"/></w:tabs>',
      ),
      "",
    ],
    [
      "a non-left tab stop",
      TAB_STOP_PROPERTIES.replace('w:val="left"', 'w:val="right"'),
      "",
    ],
    [
      "a negative tab-stop position",
      TAB_STOP_PROPERTIES.replace('w:pos="2520"', 'w:pos="-2520"'),
      "",
    ],
    [
      "a tab-stop leader outside the exact profile",
      TAB_STOP_PROPERTIES.replace(
        'w:pos="2520"',
        'w:pos="2520" w:leader="dot"',
      ),
      "",
    ],
    [
      "a namespace-shadowed tab attribute",
      TAB_STOP_PROPERTIES.replace(
        'w:val="left"',
        'w:val="left" evil:val="right"',
      ),
      "",
    ],
    [
      "a namespace-shadowed tab element",
      TAB_STOP_PROPERTIES.replace(
        '<w:tab w:val="left" w:pos="2520"/>',
        '<evil:tab evil:val="left" evil:pos="2520"/>',
      ),
      "",
    ],
    [
      "an unknown paragraph property",
      TAB_STOP_PROPERTIES.replace("</w:pPr>", '<w:divId w:val="1"/></w:pPr>'),
      "",
    ],
    [
      "a duplicate paragraph property",
      TAB_STOP_PROPERTIES.replace("</w:pPr>", '<w:jc w:val="left"/></w:pPr>'),
      "",
    ],
    [
      "a data binding hidden in paragraph properties",
      TAB_STOP_PROPERTIES.replace(
        "</w:pPr>",
        '<w:dataBinding w:xpath="/root/value" w:storeItemID="{00000000-0000-0000-0000-000000000000}"/></w:pPr>',
      ),
      "",
    ],
    [
      "an active altChunk after the properties",
      `${TAB_STOP_PROPERTIES}<w:altChunk r:id="syntheticExternal"/>`,
      "",
    ],
    [
      "a malformed spacing value",
      TAB_STOP_PROPERTIES.replace(
        "</w:pPr>",
        '<w:spacing w:after="unbounded"/></w:pPr>',
      ),
      "",
    ],
    [
      "raw character data inside an otherwise allowed property",
      TAB_STOP_PROPERTIES.replace(
        '<w:jc w:val="center"/>',
        '<w:jc w:val="center">SYNTHETIC_INVALID_RAW_TEXT</w:jc>',
      ),
      "",
    ],
    [
      "a tracked paragraph-deletion revision identity",
      TAB_STOP_PROPERTIES,
      "",
      ' w:rsidDel="00A1B2C3"',
    ],
    [
      "a duplicate run property",
      TAB_STOP_PROPERTIES.replace("</w:rPr>", "<w:b/></w:rPr>"),
      "",
    ],
    [
      "a data binding hidden in table-cell properties",
      TAB_STOP_PROPERTIES,
      '<w:tcPr><w:dataBinding w:xpath="/root/value" w:storeItemID="{00000000-0000-0000-0000-000000000000}"/></w:tcPr>',
    ],
    [
      "duplicate table-cell width properties",
      TAB_STOP_PROPERTIES,
      '<w:tcPr><w:tcW w:w="5000" w:type="dxa"/><w:tcW w:w="5000" w:type="dxa"/></w:tcPr>',
    ],
    [
      "a grid-spanned target",
      TAB_STOP_PROPERTIES,
      '<w:tcPr><w:gridSpan w:val="2"/></w:tcPr>',
    ],
    [
      "a vertical-merge restart",
      TAB_STOP_PROPERTIES,
      '<w:tcPr><w:vMerge w:val="restart"/></w:tcPr>',
    ],
    [
      "a vertical-merge continuation",
      TAB_STOP_PROPERTIES,
      "<w:tcPr><w:vMerge/></w:tcPr>",
    ],
    ["a drawing", `${TAB_STOP_PROPERTIES}<w:r><w:drawing/></w:r>`, ""],
    [
      "a bookmark crossing",
      `${TAB_STOP_PROPERTIES}<w:bookmarkStart w:id="8" w:name="SyntheticTarget"/><w:bookmarkEnd w:id="8"/>`,
      "",
    ],
    [
      "compatibility fallback content",
      `${TAB_STOP_PROPERTIES}<mc:AlternateContent><mc:Choice Requires="w14"><w:r/></mc:Choice><mc:Fallback><w:r/></mc:Fallback></mc:AlternateContent>`,
      "",
    ],
  ])(
    "keeps %s certification-blocked",
    async (_name, paragraph, tcPr, paragraphAttributes = "") => {
      const target = targetCell(paragraph, tcPr).replace(
        "<w:p>",
        `<w:p${paragraphAttributes}>`,
      );
      const ir = await compileTarget(target);

      expect(tableCellFields(ir)).toEqual([]);
      expect(complexCellBlockers(ir)).toHaveLength(1);
      expect(complexCellBlockers(ir)[0]).toMatchObject({
        code: "UNBOUND_COMPLEX_TABLE_CELL",
        clinicallyMaterial: true,
        blocksCertification: true,
      });
    },
  );

  it("rejects a tracked insertion at package admission", async () => {
    await expect(
      compileTarget(
        targetCell(`${TAB_STOP_PROPERTIES}<w:ins w:id="1"><w:r/></w:ins>`),
      ),
    ).rejects.toMatchObject({ code: "XML_HIDDEN_CONTENT_UNSUPPORTED" });
  });

  it("keeps multiple paragraphs certification-blocked", async () => {
    const ir = await compileTarget(
      `<w:tc><w:p>${TAB_STOP_PROPERTIES}</w:p><w:p/></w:tc>`,
    );

    expect(tableCellFields(ir)).toEqual([]);
    expect(complexCellBlockers(ir)).toHaveLength(1);
  });

  it("does not mistake a static text paragraph with tab stops for a blank field", async () => {
    const ir = await compileTarget(
      targetCell(
        `${TAB_STOP_PROPERTIES}<w:r><w:t>Synthetic neighboring text</w:t></w:r>`,
      ),
    );

    expect(tableCellFields(ir)).toEqual([]);
    expect(complexCellBlockers(ir)).toEqual([]);
  });

  it("keeps a nested table certification-blocked at the outer target", async () => {
    const nested = [
      `<w:tc><w:p>${TAB_STOP_PROPERTIES}</w:p>`,
      '<w:tbl><w:tblGrid><w:gridCol w:w="1000"/></w:tblGrid>',
      "<w:tr><w:tc><w:p><w:r><w:t>Synthetic static nested text</w:t></w:r></w:p></w:tc></w:tr>",
      "</w:tbl></w:tc>",
    ].join("");
    const ir = await compileTarget(nested);

    expect(
      tableCellFields(ir).filter(
        (field) =>
          field.rendererBinding.tableIndex === 0 &&
          field.rendererBinding.cellIndex === 1,
      ),
    ).toEqual([]);
    expect(complexCellBlockers(ir)).toHaveLength(1);
  });

  it("keeps repeated labels structurally distinct by certified path", async () => {
    const ir = await compileTarget(
      targetCell(),
      `<w:tr>
        <w:tc><w:p><w:r><w:t>Plan item</w:t></w:r></w:p></w:tc>
        ${targetCell()}
      </w:tr>`,
    );
    const fields = tableCellFields(ir);

    expect(fields).toHaveLength(2);
    expect(new Set(fields.map((field) => field.fieldId))).toHaveProperty(
      "size",
      2,
    );
    expect(
      new Set(fields.map((field) => field.rendererBinding.canonicalPath)),
    ).toHaveProperty("size", 2);
    expect(
      new Set(
        fields.map((field) => field.rendererBinding.certifiedBindingSha256),
      ),
    ).toHaveProperty("size", 2);
  });

  it("uses a physician-readable generated location when no label is deterministic", async () => {
    const unlabeled = documentXml({ target: targetCell() }).replace(
      "<w:r><w:t>Plan item</w:t></w:r>",
      "",
    );
    const ir = compileTemplateDocx(
      await buildSyntheticDocx({ documentXml: unlabeled }),
    );
    const profiled = tableCellFields(ir).find(
      (field) =>
        field.rendererBinding.bindingProfile ===
        TAB_ONLY_BLANK_TABLE_CELL_PROFILE,
    );

    expect(profiled).toMatchObject({
      originalLabel: "Table 1, row 1, column 2",
      labelSource: "generated",
      detectionStatus: "needs_confirmation",
    });
  });
});
