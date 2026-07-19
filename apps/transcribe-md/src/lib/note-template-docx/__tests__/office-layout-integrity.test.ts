import { describe, expect, it } from "vitest";

import { buildSyntheticDocx } from "./synthetic-docx";
import {
  buildOfficeLayoutIntegrityManifestQa,
  compareOfficeLayoutIntegrityManifestsQa,
} from "../office-layout-integrity";

const W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";

async function layoutManifest(input: {
  readonly documentXml: string;
  readonly stylesXml?: string;
  readonly numberingXml?: string;
}) {
  const bytes = await buildSyntheticDocx({
    documentXml: input.documentXml,
    extraEntries: {
      ...(input.stylesXml ? { "word/styles.xml": input.stylesXml } : {}),
      ...(input.numberingXml
        ? { "word/numbering.xml": input.numberingXml }
        : {}),
    },
  });
  return buildOfficeLayoutIntegrityManifestQa({
    syntheticOnly: true,
    docxBytes: bytes,
  });
}

describe("Office canonical layout integrity", () => {
  it("normalizes namespace prefixes, property order, boolean lexical values, and zero gutter", async () => {
    const before = await layoutManifest({
      documentXml: `<w:document xmlns:w="${W}"><w:body><w:p><w:pPr><w:spacing w:after="120"/><w:keepNext/><w:jc w:val="center"/></w:pPr><w:r><w:t>Synthetic layout</w:t></w:r></w:p><w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080"/></w:sectPr></w:body></w:document>`,
    });
    const after = await layoutManifest({
      documentXml: `<x:document xmlns:x="${W}"><x:body><x:p><x:pPr><x:jc x:val="center"/><x:keepNext x:val="true"/><x:spacing x:after="120"/></x:pPr><x:r><x:t>Synthetic layout</x:t></x:r></x:p><x:sectPr><x:pgMar x:gutter="0" x:left="1080" x:bottom="1080" x:right="1080" x:top="1080"/><x:pgSz x:h="15840" x:w="12240"/></x:sectPr></x:body></x:document>`,
    });

    expect(
      compareOfficeLayoutIntegrityManifestsQa(before, after),
    ).toMatchObject({
      matches: true,
      changedRegionIds: [],
    });
  });

  it("resolves numbering IDs through canonical definitions instead of treating renumbering as drift", async () => {
    const document = (numId: string) =>
      `<w:document xmlns:w="${W}"><w:body><w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="${numId}"/></w:numPr></w:pPr><w:r><w:t>Synthetic item</w:t></w:r></w:p><w:sectPr/></w:body></w:document>`;
    const numbering = (numId: string, abstractNumId: string) =>
      `<w:numbering xmlns:w="${W}"><w:abstractNum w:abstractNumId="${abstractNumId}"><w:nsid w:val="DEADBEEF"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/></w:lvl></w:abstractNum><w:num w:numId="${numId}"><w:abstractNumId w:val="${abstractNumId}"/></w:num></w:numbering>`;
    const before = await layoutManifest({
      documentXml: document("1"),
      numberingXml: numbering("1", "7"),
    });
    const after = await layoutManifest({
      documentXml: document("42"),
      numberingXml: numbering("42", "99"),
    });

    expect(compareOfficeLayoutIntegrityManifestsQa(before, after).matches).toBe(
      true,
    );
  });

  it("detects inheritance-relevant Normal style and numbering definition changes", async () => {
    const documentXml = `<w:document xmlns:w="${W}"><w:body><w:p><w:pPr><w:pStyle w:val="Normal"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>Synthetic item</w:t></w:r></w:p><w:sectPr/></w:body></w:document>`;
    const styles = (alignment: "left" | "center") =>
      `<w:styles xmlns:w="${W}"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:pPr><w:jc w:val="${alignment}"/></w:pPr></w:style></w:styles>`;
    const numbering = (alignment: "left" | "right") =>
      `<w:numbering xmlns:w="${W}"><w:abstractNum w:abstractNumId="7"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="${alignment}"/></w:lvl></w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="7"/></w:num></w:numbering>`;
    const baseline = await layoutManifest({
      documentXml,
      stylesXml: styles("left"),
      numberingXml: numbering("left"),
    });
    const styleChanged = await layoutManifest({
      documentXml,
      stylesXml: styles("center"),
      numberingXml: numbering("left"),
    });
    const numberingChanged = await layoutManifest({
      documentXml,
      stylesXml: styles("left"),
      numberingXml: numbering("right"),
    });

    expect(
      compareOfficeLayoutIntegrityManifestsQa(baseline, styleChanged)
        .changedRegionIds,
    ).toContain("styles:style_definitions");
    expect(
      compareOfficeLayoutIntegrityManifestsQa(baseline, numberingChanged)
        .changedRegionIds,
    ).toContain("numbering:numbering_definitions");
  });

  it("preserves table-grid column order while normalizing property order", async () => {
    const document = (columns: string) =>
      `<w:document xmlns:w="${W}"><w:body><w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/></w:tblPr><w:tblGrid>${columns}</w:tblGrid><w:tr><w:tc><w:p><w:r><w:t>Left</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Right</w:t></w:r></w:p></w:tc></w:tr></w:tbl><w:sectPr/></w:body></w:document>`;
    const before = await layoutManifest({
      documentXml: document('<w:gridCol w:w="3000"/><w:gridCol w:w="6000"/>'),
    });
    const after = await layoutManifest({
      documentXml: document('<w:gridCol w:w="6000"/><w:gridCol w:w="3000"/>'),
    });

    expect(
      compareOfficeLayoutIntegrityManifestsQa(before, after).changedRegionIds,
    ).toContain("main_document:table_grid");
  });
});
