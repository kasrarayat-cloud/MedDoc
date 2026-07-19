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

  it("rejects ZIP archive comments, entry comments, and extra fields", async () => {
    const archiveComment = await buildSyntheticDocx({
      archiveComment: "hidden.patient@example.test",
    });
    expectTemplateError(
      () => readVerifiedZipPackage(archiveComment),
      "ZIP_METADATA_UNSUPPORTED",
    );

    const entryComment = await buildSyntheticDocx({
      firstEntryComment: "hidden.patient@example.test",
    });
    expectTemplateError(
      () => readVerifiedZipPackage(entryComment),
      "ZIP_METADATA_UNSUPPORTED",
    );

    const valid = await buildSyntheticDocx({ compression: "STORE" });
    expectTemplateError(
      () => readVerifiedZipPackage(withCentralDirectoryExtra(valid)),
      "ZIP_METADATA_UNSUPPORTED",
    );
    expectTemplateError(
      () => readVerifiedZipPackage(withFirstLocalHeaderExtra(valid)),
      "ZIP_METADATA_UNSUPPORTED",
    );

    expect(() =>
      readVerifiedZipPackage(withMicrosoftZeroPaddingExtra(valid, false)),
    ).not.toThrow();
    expectTemplateError(
      () => readVerifiedZipPackage(withMicrosoftZeroPaddingExtra(valid, true)),
      "ZIP_METADATA_UNSUPPORTED",
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
        '<Relationship Id="rIdExternal" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://malicious.example.test/synthetic" TargetMode="External"/></Relationships>',
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

  it("rejects namespace-shadowed OPC relationship attributes", async () => {
    const shadowed = await buildSyntheticDocx({
      rootRelationships: syntheticOpc.rootRelationships
        .replace(
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships" xmlns:evil="https://synthetic.test/evil">',
        )
        .replace(
          'Target="word/document.xml"',
          'Target="word/document.xml" evil:Target="https://synthetic.test/remote.docx"',
        ),
    });
    expectTemplateError(
      () => inspectDocxPackage(shadowed),
      "OPC_RELATIONSHIP_INVALID",
    );
  });

  it("canonicalizes XML character references before relationship safety checks", async () => {
    const encodedExternal = await buildSyntheticDocx({
      documentRelationships: syntheticOpc.documentRelationships.replace(
        "</Relationships>",
        '<Relationship Id="rIdEncoded" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="h&#x74;tps://synthetic.test/remote"/></Relationships>',
      ),
    });
    expectTemplateError(
      () => inspectDocxPackage(encodedExternal),
      "EXTERNAL_RELATIONSHIP_REJECTED",
    );
  });

  it("rejects namespace-shadowed content type attributes", async () => {
    const shadowed = await buildSyntheticDocx({
      contentTypes: syntheticOpc.contentTypes
        .replace(
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types" xmlns:evil="https://synthetic.test/evil">',
        )
        .replace(
          'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"',
          'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml" evil:ContentType="application/synthetic-active"',
        ),
    });
    expectTemplateError(
      () => inspectDocxPackage(shadowed),
      "OPC_CONTENT_TYPE_INVALID",
    );
  });

  it("rejects foreign-namespace elements that shadow Word fill structures", async () => {
    const shadowed = await buildSyntheticDocx({
      documentXml: syntheticOpc.documentXml
        .replace(
          '<w:document ',
          '<w:document xmlns:evil="https://synthetic.test/evil" ',
        )
        .replace('<w:sdt>', '<evil:sdt>')
        .replace('</w:sdt>', '</evil:sdt>'),
    });
    expectTemplateError(
      () => inspectDocxPackage(shadowed),
      "ACTIVE_CONTENT_REJECTED",
    );
  });

  it("rejects fldSimple and fragmented complex active field instructions", async () => {
    const simple = await buildSyntheticDocx({
      documentXml: syntheticOpc.documentXml.replace(
        '<w:sectPr>',
        '<w:p><w:fldSimple w:instr=" DDEAUTO synthetic.test "><w:r><w:t>blocked</w:t></w:r></w:fldSimple></w:p><w:sectPr>',
      ),
    });
    expectTemplateError(
      () => inspectDocxPackage(simple),
      "ACTIVE_CONTENT_REJECTED",
    );

    const fragmented = await buildSyntheticDocx({
      documentXml: syntheticOpc.documentXml.replace(
        '<w:sectPr>',
        '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText>D D E</w:instrText></w:r><w:r><w:instrText>A U T O synthetic.test</w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p><w:sectPr>',
      ),
    });
    expectTemplateError(
      () => inspectDocxPackage(fragmented),
      "ACTIVE_CONTENT_REJECTED",
    );

    const encoded = await buildSyntheticDocx({
      documentXml: syntheticOpc.documentXml.replace(
        '<w:sectPr>',
        '<w:p><w:fldSimple w:instr=" D&#68;EAUTO synthetic.test "><w:r><w:t>blocked</w:t></w:r></w:fldSimple></w:p><w:sectPr>',
      ),
    });
    expectTemplateError(
      () => inspectDocxPackage(encoded),
      "ACTIVE_CONTENT_REJECTED",
    );
  });

  it("rejects hidden Word text, unresolved revisions, and comment payloads", async () => {
    for (const hiddenRunProperty of ["vanish", "webHidden", "specVanish"]) {
      const hidden = await buildSyntheticDocx({
        documentXml: syntheticOpc.documentXml.replace(
          "<w:sectPr>",
          `<w:p><w:r><w:rPr><w:${hiddenRunProperty}/></w:rPr><w:t>synthetic hidden patient-like text</w:t></w:r></w:p><w:sectPr>`,
        ),
      });
      expectTemplateError(
        () => inspectDocxPackage(hidden),
        "XML_HIDDEN_CONTENT_UNSUPPORTED",
      );
    }

    for (const revision of ["del", "ins", "moveFrom", "moveTo"]) {
      const unresolved = await buildSyntheticDocx({
        documentXml: syntheticOpc.documentXml.replace(
          "<w:sectPr>",
          `<w:${revision} w:id="9"><w:r><w:t>synthetic revision text</w:t></w:r></w:${revision}><w:sectPr>`,
        ),
      });
      expectTemplateError(
        () => inspectDocxPackage(unresolved),
        "XML_HIDDEN_CONTENT_UNSUPPORTED",
      );
    }

    const comments = await buildSyntheticDocx({
      extraEntries: {
        "word/comments.xml":
          '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:comment w:id="0"><w:p><w:r><w:t>synthetic hidden comment</w:t></w:r></w:p></w:comment></w:comments>',
      },
    });
    expectTemplateError(
      () => inspectDocxPackage(comments),
      "XML_HIDDEN_CONTENT_UNSUPPORTED",
    );

    const collaborationPeople = await buildSyntheticDocx({
      extraEntries: {
        "word/people.xml":
          '<w15:people xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml"><w15:person w15:author="Synthetic Author"/></w15:people>',
      },
    });
    expectTemplateError(
      () => inspectDocxPackage(collaborationPeople),
      "XML_HIDDEN_CONTENT_UNSUPPORTED",
    );
  });

  it("enforces parsed XML element, attribute, and aggregate text limits", async () => {
    const source = await buildSyntheticDocx();
    expectTemplateError(
      () => inspectDocxPackage(source, { maxXmlElements: 12 }),
      "DOCUMENT_STRUCTURE_LIMIT_EXCEEDED",
    );
    expectTemplateError(
      () => inspectDocxPackage(source, { maxXmlAttributes: 12 }),
      "DOCUMENT_STRUCTURE_LIMIT_EXCEEDED",
    );
    expectTemplateError(
      () => inspectDocxPackage(source, { maxXmlAttributeCharacters: 64 }),
      "DOCUMENT_STRUCTURE_LIMIT_EXCEEDED",
    );
    expectTemplateError(
      () => inspectDocxPackage(source, { maxXmlTextCharacters: 32 }),
      "DOCUMENT_STRUCTURE_LIMIT_EXCEEDED",
    );
    expectTemplateError(
      () => inspectDocxPackage(source, { maxXmlDepth: 4 }),
      "DOCUMENT_STRUCTURE_LIMIT_EXCEEDED",
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

  it.each([
    ["XML comment", "<!-- hidden.patient@example.test -->"],
    ["processing instruction", "<?synthetic hidden.patient@example.test?>"],
    ["CDATA", "<![CDATA[hidden.patient@example.test]]>"],
  ])("rejects hidden text in %s", async (_name, hiddenXml) => {
    const source = await buildSyntheticDocx({
      documentXml: syntheticOpc.documentXml.replace(
        "<w:body>",
        `<w:body>${hiddenXml}`,
      ),
    });
    expectTemplateError(
      () => inspectDocxPackage(source),
      "XML_HIDDEN_CONTENT_UNSUPPORTED",
    );
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

function withCentralDirectoryExtra(source: Buffer): Buffer {
  const eocdOffset = source.lastIndexOf(
    Buffer.from([0x50, 0x4b, 0x05, 0x06]),
  );
  const directoryOffset = source.readUInt32LE(eocdOffset + 16);
  const nameLength = source.readUInt16LE(directoryOffset + 28);
  const insertAt = directoryOffset + 46 + nameLength;
  const extra = Buffer.from([
    0xfe,
    0xca,
    0x04,
    0x00,
    0x50,
    0x48,
    0x49,
    0x21,
  ]);
  const result = Buffer.concat([
    source.subarray(0, insertAt),
    extra,
    source.subarray(insertAt),
  ]);
  result.writeUInt16LE(extra.length, directoryOffset + 30);
  const movedEocdOffset = eocdOffset + extra.length;
  result.writeUInt32LE(
    source.readUInt32LE(eocdOffset + 12) + extra.length,
    movedEocdOffset + 12,
  );
  return result;
}

function withFirstLocalHeaderExtra(source: Buffer): Buffer {
  const eocdOffset = source.lastIndexOf(
    Buffer.from([0x50, 0x4b, 0x05, 0x06]),
  );
  const directoryOffset = source.readUInt32LE(eocdOffset + 16);
  const nameLength = source.readUInt16LE(26);
  const insertAt = 30 + nameLength;
  const extra = Buffer.from([
    0xfe,
    0xca,
    0x04,
    0x00,
    0x50,
    0x48,
    0x49,
    0x21,
  ]);
  const result = Buffer.concat([
    source.subarray(0, insertAt),
    extra,
    source.subarray(insertAt),
  ]);
  result.writeUInt16LE(extra.length, 28);
  const movedEocdOffset = eocdOffset + extra.length;
  result.writeUInt32LE(directoryOffset + extra.length, movedEocdOffset + 16);
  return result;
}

function withMicrosoftZeroPaddingExtra(
  source: Buffer,
  injectHiddenByte: boolean,
): Buffer {
  const eocdOffset = source.lastIndexOf(
    Buffer.from([0x50, 0x4b, 0x05, 0x06]),
  );
  const directoryOffset = source.readUInt32LE(eocdOffset + 16);
  const totalEntries = source.readUInt16LE(eocdOffset + 10);
  const nameLength = source.readUInt16LE(26);
  const insertAt = 30 + nameLength;
  const extra = Buffer.alloc(264);
  extra.writeUInt16LE(0xa220, 0);
  extra.writeUInt16LE(260, 2);
  extra.writeUInt16LE(0xa028, 4);
  extra.writeUInt16LE(0x0100, 6);
  if (injectHiddenByte) extra[extra.length - 1] = 0x50;

  const result = Buffer.concat([
    source.subarray(0, insertAt),
    extra,
    source.subarray(insertAt),
  ]);
  result.writeUInt16LE(extra.length, 28);
  const movedDirectoryOffset = directoryOffset + extra.length;
  const movedEocdOffset = eocdOffset + extra.length;
  result.writeUInt32LE(movedDirectoryOffset, movedEocdOffset + 16);

  let centralOffset = movedDirectoryOffset;
  for (let index = 0; index < totalEntries; index += 1) {
    const localHeaderOffset = result.readUInt32LE(centralOffset + 42);
    if (localHeaderOffset > 0) {
      result.writeUInt32LE(localHeaderOffset + extra.length, centralOffset + 42);
    }
    const centralNameLength = result.readUInt16LE(centralOffset + 28);
    const centralExtraLength = result.readUInt16LE(centralOffset + 30);
    const centralCommentLength = result.readUInt16LE(centralOffset + 32);
    centralOffset +=
      46 + centralNameLength + centralExtraLength + centralCommentLength;
  }
  return result;
}
