import JSZip from "jszip";

const CONTENT_TYPES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
</Types>`;

const ROOT_RELATIONSHIPS = `<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>`;

const DOCUMENT_RELATIONSHIPS = `<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdHeader" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>
  <Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
  <Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rIdNumbering" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
</Relationships>`;

const DOCUMENT_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
  xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p><w:bookmarkStart w:id="1" w:name="ClinicalHeading"/><w:r><w:t>Synthetic clinical template</w:t></w:r><w:bookmarkEnd w:id="1"/></w:p>
    <w:p><w:r><w:t>Exam side: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="100"/><w:alias w:val="Exam side"/><w:tag w:val="exam_side"/><w:dropDownList><w:listItem w:displayText="Left" w:value="L"/><w:listItem w:displayText="Right" w:value="R"/><w:listItem w:displayText="Bilateral" w:value="B"/></w:dropDownList></w:sdtPr><w:sdtContent><w:r><w:t>Choose an item.</w:t></w:r></w:sdtContent></w:sdt></w:p>
    <w:p><w:sdt><w:sdtPr><w:id w:val="101"/><w:alias w:val="Encounter category"/><w:comboBox><w:listItem w:displayText="Initial" w:value="initial"/><w:listItem w:displayText="Follow-up" w:value="follow_up"/></w:comboBox></w:sdtPr><w:sdtContent><w:r><w:t>Initial</w:t></w:r></w:sdtContent></w:sdt></w:p>
    <w:p><w:sdt><w:sdtPr><w:id w:val="102"/><w:alias w:val="Assessment narrative"/><w:text w:multiLine="true"/></w:sdtPr><w:sdtContent><w:r><w:t>Enter assessment</w:t></w:r></w:sdtContent></w:sdt></w:p>
    <w:p><w:sdt><w:sdtPr><w:id w:val="103"/><w:alias w:val="Encounter date"/><w:date w:fullDate="2026-01-01T00:00:00Z"><w:dateFormat w:val="yyyy-MM-dd"/></w:date></w:sdtPr><w:sdtContent><w:r><w:t>2026-01-01</w:t></w:r></w:sdtContent></w:sdt></w:p>
    <w:p><w:sdt><w:sdtPr><w:id w:val="104"/><w:alias w:val="Medication reviewed"/><w14:checkbox><w14:checked w14:val="0"/><w14:checkedState w14:val="2612"/><w14:uncheckedState w14:val="2610"/></w14:checkbox></w:sdtPr><w:sdtContent><w:r><w:t>☐</w:t></w:r></w:sdtContent></w:sdt></w:p>
    <w:p><w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Legacy severity"/><w:ddList><w:listEntry w:val="Mild"/><w:listEntry w:val="Moderate"/><w:listEntry w:val="Severe"/></w:ddList></w:ffData></w:fldChar></w:r><w:r><w:instrText> FORMDROPDOWN </w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>
    <w:tbl>
      <w:tblGrid><w:gridCol w:w="2800"/><w:gridCol w:w="4200"/></w:tblGrid>
      <w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/><w:vMerge w:val="restart"/></w:tcPr><w:p><w:r><w:t>Findings</w:t></w:r></w:p></w:tc></w:tr>
      <w:tr>
        <w:tc><w:tcPr><w:vMerge/></w:tcPr><w:p><w:sdt><w:sdtPr><w:id w:val="105"/><w:alias w:val="Finding value"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter finding</w:t></w:r></w:sdtContent></w:sdt></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Nested:</w:t></w:r></w:p><w:tbl><w:tblGrid><w:gridCol w:w="1200"/></w:tblGrid><w:tr><w:tc><w:p><w:r><w:t>Synthetic nested value</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:tc>
      </w:tr>
      <w:tr><w:tc><w:p><w:r><w:t>Additional finding</w:t></w:r></w:p></w:tc><w:tc><w:p/></w:tc></w:tr>
    </w:tbl>
    <w:sdt><w:sdtPr><w:id w:val="106"/><w:alias w:val="Repeat findings"/><w15:repeatingSection/></w:sdtPr><w:sdtContent>
      <w:tbl><w:tblGrid><w:gridCol w:w="3600"/></w:tblGrid><w:tr><w:tc><w:p><w:sdt><w:sdtPr><w:id w:val="107"/><w:alias w:val="Repeat finding"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter repeat finding</w:t></w:r></w:sdtContent></w:sdt></w:p></w:tc></w:tr></w:tbl>
    </w:sdtContent></w:sdt>
    <w:p><w:sdt><w:sdtPr><w:id w:val="108"/><w:alias w:val="Data-bound synthetic value"/><w:text/><w:dataBinding w:xpath="/root/value" w:storeItemID="{00000000-0000-0000-0000-000000000000}"/></w:sdtPr><w:sdtContent><w:r><w:t>Unapproved bound value</w:t></w:r></w:sdtContent></w:sdt></w:p>
    <w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr>
  </w:body>
</w:document>`;

const HEADER_XML = `<?xml version="1.0" encoding="UTF-8"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Practice logo placeholder</w:t></w:r><w:sdt><w:sdtPr><w:id w:val="201"/><w:alias w:val="Practice display name"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Synthetic Practice</w:t></w:r></w:sdtContent></w:sdt></w:p></w:hdr>`;

const FOOTER_XML = `<?xml version="1.0" encoding="UTF-8"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Page </w:t></w:r><w:fldSimple w:instr=" PAGE "><w:r><w:t>1</w:t></w:r></w:fldSimple></w:p></w:ftr>`;

export interface SyntheticDocxOptions {
  contentTypes?: string;
  rootRelationships?: string;
  documentRelationships?: string;
  documentXml?: string;
  extraEntries?: Record<string, string | Uint8Array>;
  compression?: "STORE" | "DEFLATE";
  archiveComment?: string;
  firstEntryComment?: string;
}

export async function buildSyntheticDocx(
  options: SyntheticDocxOptions = {},
): Promise<Buffer> {
  const documentXml = options.documentXml ?? DOCUMENT_XML;
  const usesDefaultContentTypes = options.contentTypes === undefined;
  const usesDefaultDocumentRelationships =
    options.documentRelationships === undefined;
  const referencesHeader = documentXml.includes('r:id="rIdHeader"');
  const referencesFooter = documentXml.includes('r:id="rIdFooter"');
  const contentTypes = usesDefaultContentTypes
    ? CONTENT_TYPES.replace(
        referencesHeader
          ? ""
          : /\s*<Override PartName="\/word\/header1\.xml"[^>]*\/>/u,
        "",
      ).replace(
        referencesFooter
          ? ""
          : /\s*<Override PartName="\/word\/footer1\.xml"[^>]*\/>/u,
        "",
      )
    : options.contentTypes!;
  const documentRelationships = usesDefaultDocumentRelationships
    ? DOCUMENT_RELATIONSHIPS.replace(
        referencesHeader ? "" : /\s*<Relationship Id="rIdHeader"[^>]*\/>/u,
        "",
      ).replace(
        referencesFooter ? "" : /\s*<Relationship Id="rIdFooter"[^>]*\/>/u,
        "",
      )
    : options.documentRelationships!;
  const zip = new JSZip();
  zip.file("[Content_Types].xml", contentTypes, {
    comment: options.firstEntryComment,
  });
  zip.file("_rels/.rels", options.rootRelationships ?? ROOT_RELATIONSHIPS);
  zip.file("word/document.xml", documentXml);
  zip.file("word/_rels/document.xml.rels", documentRelationships);
  if (referencesHeader || !usesDefaultDocumentRelationships) {
    zip.file("word/header1.xml", HEADER_XML);
  }
  if (referencesFooter || !usesDefaultDocumentRelationships) {
    zip.file("word/footer1.xml", FOOTER_XML);
  }
  zip.file(
    "word/styles.xml",
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="paragraph" w:styleId="Normal"/></w:styles>',
  );
  zip.file(
    "word/numbering.xml",
    '<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>',
  );
  for (const [name, value] of Object.entries(options.extraEntries ?? {})) {
    zip.file(name, value);
  }
  return zip.generateAsync({
    type: "nodebuffer",
    compression: options.compression ?? "DEFLATE",
    compressionOptions: { level: 6 },
    comment: options.archiveComment,
  });
}

export const syntheticOpc = {
  contentTypes: CONTENT_TYPES,
  rootRelationships: ROOT_RELATIONSHIPS,
  documentRelationships: DOCUMENT_RELATIONSHIPS,
  documentXml: DOCUMENT_XML,
};
