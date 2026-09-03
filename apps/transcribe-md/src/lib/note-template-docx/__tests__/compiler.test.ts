import { describe, expect, it } from "vitest";

import { TemplateDocIRSchema } from "../../template-twin/ir";
import { compileTemplateDocx } from "..";
import { buildSyntheticDocx, syntheticOpc } from "./synthetic-docx";

describe("deterministic Template Twin DOCX compiler", () => {
  it("extracts stable controls and exact native option order from the body, header, and tables", async () => {
    const source = await buildSyntheticDocx();
    const first = compileTemplateDocx(source);
    const second = compileTemplateDocx(source);

    expect(TemplateDocIRSchema.safeParse(first).success).toBe(true);
    expect(second).toEqual(first);
    expect(second.structureSha256).toBe(first.structureSha256);

    const examSide = first.fields.find(
      (field) => field.originalLabel === "Exam side",
    );
    expect(examSide?.kind).toBe("single_select");
    expect(examSide?.allowedOptions).toEqual([
      { ordinal: 0, displayText: "Left", value: "L" },
      { ordinal: 1, displayText: "Right", value: "R" },
      { ordinal: 2, displayText: "Bilateral", value: "B" },
    ]);
    expect(examSide?.rendererBinding.sdtId).toBe("100");
    expect(examSide?.rendererBinding.tag).toBe("exam_side");

    expect(
      first.fields.find(
        (field) => field.originalLabel === "Medication reviewed",
      )?.kind,
    ).toBe("checkbox");
    expect(
      first.fields.find((field) => field.originalLabel === "Encounter date")
        ?.kind,
    ).toBe("date");
    expect(
      first.fields.find((field) => field.originalLabel === "Legacy severity")
        ?.rendererBinding.bindingType,
    ).toBe("legacy_form_field");
    expect(
      first.fields.find(
        (field) => field.originalLabel === "Practice display name",
      )?.rendererBinding.partName,
    ).toBe("word/header1.xml");
    expect(
      first.fields.find(
        (field) => field.originalLabel === "Additional finding",
      ),
    ).toMatchObject({
      labelSource: "left_cell",
      detectionStatus: "needs_confirmation",
      rendererBinding: { bindingType: "table_cell" },
    });
    expect(first.stats.comboBoxes).toBe(1);
    expect(first.stats.headers).toBe(1);
    expect(first.stats.footers).toBe(1);
  });

  it("records merged cells, nested tables, repeat bindings, and immutable renderer locations", async () => {
    const compiled = compileTemplateDocx(await buildSyntheticDocx());
    const outerTable = compiled.tables.find((table) =>
      table.cells.some((cell) => cell.gridSpan === 2),
    );
    // ⚠️ FILTER-AND-COUNT — `kind` is a label class, not a key.
    const repeatingTables = compiled.tables.filter(
      (table) => table.kind === "repeating_table",
    );
    expect(repeatingTables.length).toBe(1);
    const repeatingTable = repeatingTables[0];
    const repeatField = compiled.fields.find(
      (field) => field.originalLabel === "Repeat finding",
    );

    expect(outerTable?.gridColumnWidths).toEqual([2800, 4200]);
    expect(
      outerTable?.cells.some(
        (cell) => cell.gridSpan === 2 && cell.verticalMerge === "restart",
      ),
    ).toBe(true);
    expect(
      outerTable?.cells.some((cell) => cell.verticalMerge === "continue"),
    ).toBe(true);
    expect(outerTable?.cells.some((cell) => cell.nestedTableCount === 1)).toBe(
      true,
    );
    expect(compiled.tables.length).toBeGreaterThanOrEqual(3);

    expect(repeatingTable?.repeatPrototypeRow).toBe(0);
    expect(repeatField?.rowPrototype).toBe(true);
    expect(repeatField?.rendererBinding.repeatAncestorPath).toBeTruthy();
    expect(repeatField?.tableId).toBe(repeatingTable?.tableId);
    expect(repeatField?.rendererBinding.path).toMatch(/^\/w:document\[0\]/);
  });

  it("surfaces clinically material unsupported constructs instead of dropping them", async () => {
    const compiled = compileTemplateDocx(await buildSyntheticDocx());
    const dataBound = compiled.fields.find(
      (field) => field.originalLabel === "Data-bound synthetic value",
    );
    const unsupported = compiled.unsupported.find(
      (item) => item.code === "DATA_BOUND_CONTENT_CONTROL",
    );

    expect(dataBound?.detectionStatus).toBe("unsupported");
    expect(unsupported).toMatchObject({
      clinicallyMaterial: true,
      blocksCertification: true,
      partName: "word/document.xml",
    });
    expect(compiled.stats.blockingUnsupported).toBeGreaterThanOrEqual(1);
  });

  it("changes source and binding hashes when the immutable source changes", async () => {
    const original = compileTemplateDocx(await buildSyntheticDocx());
    const changed = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: syntheticOpc.documentXml.replace(
          "Synthetic clinical template",
          "Synthetic clinical template revision",
        ),
      }),
    );

    expect(changed.source.sha256).not.toBe(original.source.sha256);
    expect(changed.staticContentSha256).not.toBe(original.staticContentSha256);
    expect(changed.fields[0]?.fieldId).not.toBe(original.fields[0]?.fieldId);
  });

  it("keeps duplicate labels as distinct path-bound fields and bounds long labels", async () => {
    const duplicateLabelXml = syntheticOpc.documentXml.replace(
      'w:alias w:val="Assessment narrative"',
      'w:alias w:val="Exam side"',
    );
    const duplicate = compileTemplateDocx(
      await buildSyntheticDocx({ documentXml: duplicateLabelXml }),
    );
    const sameLabelFields = duplicate.fields.filter(
      (field) => field.originalLabel === "Exam side",
    );
    expect(sameLabelFields).toHaveLength(2);
    expect(new Set(sameLabelFields.map((field) => field.fieldId)).size).toBe(2);
    expect(
      new Set(sameLabelFields.map((field) => field.rendererBinding.path)).size,
    ).toBe(2);

    const longLabel = "Synthetic measurement ".repeat(20);
    const longLabelXml = syntheticOpc.documentXml.replace(
      "Assessment narrative",
      longLabel,
    );
    const bounded = compileTemplateDocx(
      await buildSyntheticDocx({ documentXml: longLabelXml }),
    );
    expect(
      bounded.fields.find((field) =>
        field.originalLabel.startsWith("Synthetic"),
      )?.originalLabel,
    ).toHaveLength(240);
  });

  it("masks mutable content-control results from the static-region hash", async () => {
    const original = compileTemplateDocx(await buildSyntheticDocx());
    const changedDisplayValue = compileTemplateDocx(
      await buildSyntheticDocx({
        documentXml: syntheticOpc.documentXml.replace(
          "Choose an item.",
          "Left",
        ),
      }),
    );

    expect(changedDisplayValue.source.sha256).not.toBe(original.source.sha256);
    expect(changedDisplayValue.staticContentSha256).toBe(
      original.staticContentSha256,
    );
  });
});
