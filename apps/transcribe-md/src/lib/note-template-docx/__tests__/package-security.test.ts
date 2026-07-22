import { describe, expect, it } from "vitest";

import {
  inspectDocxPackage,
  readVerifiedZipPackage,
  TemplateDocxError,
} from "..";
import { buildSyntheticDocx, syntheticOpc } from "./synthetic-docx";

describe("Template Twin untrusted DOCX boundary", () => {
  it("verifies bounded ZIP metadata, CRCs, OPC parts, and internal relationships", async () => {
    const source = await buildSyntheticDocx();
    const inspected = inspectDocxPackage(source);

    expect(inspected.mainPartName).toBe("word/document.xml");
    expect(inspected.headerPartNames).toEqual(["word/header1.xml"]);
    expect(inspected.footerPartNames).toEqual(["word/footer1.xml"]);
    expect(
      inspected.zip.entries.get("word/document.xml")?.bytes.length,
    ).toBeGreaterThan(0);
    expect(
      inspected.relationships.every(
        (relationship) => !relationship.targetPartName.includes("://"),
      ),
    ).toBe(true);
  });

  it("rejects path traversal and case-folded duplicate package entries", async () => {
    const traversal = await buildSyntheticDocx({
      extraEntries: { "../synthetic-escape.xml": "<root/>" },
    });
    expectTemplateError(
      () => readVerifiedZipPackage(traversal),
      "ZIP_PATH_UNSAFE",
    );

    const duplicate = await buildSyntheticDocx({
      extraEntries: { "WORD/DOCUMENT.XML": "<root/>" },
    });
    expectTemplateError(
      () => readVerifiedZipPackage(duplicate),
      "ZIP_DUPLICATE_ENTRY",
    );
  });

  it("rejects corrupt CRC metadata before OOXML parsing", async () => {
    const valid = await buildSyntheticDocx({ compression: "STORE" });
    const corrupt = Buffer.from(valid);
    const centralHeader = corrupt.indexOf(
      Buffer.from([0x50, 0x4b, 0x01, 0x02]),
    );
    expect(centralHeader).toBeGreaterThanOrEqual(0);
    corrupt.writeUInt32LE(
      (corrupt.readUInt32LE(centralHeader + 16) ^ 0xffffffff) >>> 0,
      centralHeader + 16,
    );

    expectTemplateError(
      () => readVerifiedZipPackage(corrupt),
      "ZIP_CRC_MISMATCH",
    );
  });

  it("rejects incorrect magic bytes, oversized uploads, encryption, and symlink entries", async () => {
    expectTemplateError(
      () => readVerifiedZipPackage(Buffer.from("not a synthetic DOCX", "utf8")),
      "ZIP_MAGIC_INVALID",
    );

    const valid = await buildSyntheticDocx({ compression: "STORE" });
    expectTemplateError(
      () => readVerifiedZipPackage(valid, { maxSourceBytes: valid.length - 1 }),
      "DOCX_TOO_LARGE",
    );

    const encrypted = Buffer.from(valid);
    const encryptedCentralHeader = encrypted.indexOf(
      Buffer.from([0x50, 0x4b, 0x01, 0x02]),
    );
    encrypted.writeUInt16LE(
      encrypted.readUInt16LE(encryptedCentralHeader + 8) | 0x0001,
      encryptedCentralHeader + 8,
    );
    expectTemplateError(
      () => readVerifiedZipPackage(encrypted),
      "ZIP_ENCRYPTED_ENTRY",
    );

    const symlink = Buffer.from(valid);
    const symlinkCentralHeader = symlink.indexOf(
      Buffer.from([0x50, 0x4b, 0x01, 0x02]),
    );
    symlink.writeUInt16LE((3 << 8) | 20, symlinkCentralHeader + 4);
    symlink.writeUInt32LE((0xa000 << 16) >>> 0, symlinkCentralHeader + 38);
    expectTemplateError(
      () => readVerifiedZipPackage(symlink),
      "ZIP_SYMLINK_ENTRY",
    );
  });

  it("enforces decompression-ratio limits before inflating entries", async () => {
    const source = await buildSyntheticDocx({ compression: "DEFLATE" });
    expectTemplateError(
      () => readVerifiedZipPackage(source, { maxCompressionRatio: 1.01 }),
      "ZIP_COMPRESSION_RATIO_EXCEEDED",
    );
  });

  it("rejects external relationships, macro content, and embedded OLE objects", async () => {
    const external = await buildSyntheticDocx({
      documentRelationships: syntheticOpc.documentRelationships.replace(
        "</Relationships>",
        '<Relationship Id="rIdExternal" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://invalid.example/synthetic" TargetMode="External"/></Relationships>',
      ),
    });
    expectTemplateError(
      () => inspectDocxPackage(external),
      "EXTERNAL_RELATIONSHIP_REJECTED",
    );

    const macro = await buildSyntheticDocx({
      contentTypes: syntheticOpc.contentTypes.replace(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
        "application/vnd.ms-word.document.macroEnabled.main+xml",
      ),
    });
    expectTemplateError(() => inspectDocxPackage(macro), "DOCM_REJECTED");

    const embedded = await buildSyntheticDocx({
      extraEntries: {
        "word/embeddings/oleObject1.bin": new Uint8Array([1, 2, 3]),
      },
    });
    expectTemplateError(
      () => inspectDocxPackage(embedded),
      "EMBEDDED_OBJECT_REJECTED",
    );
  });

  it("rejects DTD/entity declarations before XML parsing", async () => {
    const source = await buildSyntheticDocx({
      documentXml: syntheticOpc.documentXml.replace(
        "<w:document",
        '<!DOCTYPE w:document [<!ENTITY synthetic "blocked">]><w:document',
      ),
    });
    expectTemplateError(() => inspectDocxPackage(source), "XML_DTD_REJECTED");
  });
});

function expectTemplateError(
  action: () => unknown,
  code: TemplateDocxError["code"],
): void {
  try {
    action();
    throw new Error(`Expected TemplateDocxError ${code}`);
  } catch (error) {
    expect(error).toBeInstanceOf(TemplateDocxError);
    expect((error as TemplateDocxError).code).toBe(code);
  }
}
