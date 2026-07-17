import { createHash } from "node:crypto";

import JSZip from "jszip";
import {
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
} from "@meddoc/ai";

import { DOCX_MIME_TYPE } from "./storage";
import { TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER } from "./staging-qa-ui-contract";
export {
  TEMPLATE_TWIN_STAGING_QA_STATIC_INTENT_REASON,
  TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER,
} from "./staging-qa-ui-contract";

const FIXED_ZIP_DATE = new Date("2026-01-01T00:00:00.000Z");
const W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
const W14 = "http://schemas.microsoft.com/office/word/2010/wordml";
const R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";

export { TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION };
export const TEMPLATE_TWIN_STAGING_QA_FIXTURE_FILENAME =
  "template-twin-synthetic-qa-v1.docx" as const;
export const TEMPLATE_TWIN_STAGING_QA_FIXTURE_MIME = DOCX_MIME_TYPE;
/**
 * Exact byte identity of the only document admitted by the staging workflow.
 * This is intentionally a reviewed constant, rather than a value learned from
 * an uploaded file. Changing the fixture requires a new fixture version and a
 * migration review of the database admission backstop.
 */
export const TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256 =
  "9c917a831e661d5fdcf92a6e13cbc542adda9fb86a2292cf34689fc333c375d4" as const;
export const TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES = 4_686 as const;
export const TEMPLATE_TWIN_STAGING_QA_TEMPLATE_NAME =
  "Template Twin Synthetic QA Fixture" as const;
export const TEMPLATE_TWIN_STAGING_QA_ENCOUNTER_SCOPE =
  "Synthetic follow-up encounter" as const;
export const TEMPLATE_TWIN_STAGING_QA_VERSION_DESCRIPTION =
  "Reviewed synthetic staging fixture v1" as const;
export const TEMPLATE_TWIN_STAGING_QA_SOAP_EDIT_SUFFIX =
  "\n\nSynthetic staging SOAP edit marker." as const;
export const TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT =
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT;
export const TEMPLATE_TWIN_STAGING_QA_WAV_SIZE_BYTES = 8_044 as const;
export const TEMPLATE_TWIN_STAGING_QA_WAV_SHA256 =
  "181e56881cc6c02c9ab4611787128d87b07b404a466cf826194480ed1e769dfd" as const;

const CONTENT_TYPES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/><Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/><Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>`;
const ROOT_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>`;
const DOCUMENT_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rIdSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/><Relationship Id="rIdFonts" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/><Relationship Id="rIdHeader" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/><Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/></Relationships>`;

function textControl(id: number, tag: string, alias: string): string {
  return `<w:sdt><w:sdtPr><w:id w:val="${id}"/><w:tag w:val="${tag}"/><w:alias w:val="${alias}"/><w:text/><w:showingPlcHdr/></w:sdtPr><w:sdtContent><w:r><w:rPr><w:rStyle w:val="PlaceholderText"/></w:rPr><w:t>Enter synthetic value</w:t></w:r></w:sdtContent></w:sdt>`;
}

const DOCUMENT_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="${W}" xmlns:w14="${W14}" xmlns:r="${R}"><w:body>
  <w:p><w:pPr><w:pStyle w:val="QAHeading"/></w:pPr><w:r><w:t>Template Twin — Synthetic QA Fixture</w:t></w:r></w:p>
  <w:p><w:r><w:t>Chief concern: </w:t></w:r>${textControl(4101, "qa_chief_concern", "Synthetic chief concern")}</w:p>
  <w:p><w:r><w:t>Smoking status: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="4102"/><w:tag w:val="qa_smoking_status"/><w:alias w:val="Synthetic smoking status"/><w:dropDownList><w:listItem w:displayText="Never" w:value="never"/><w:listItem w:displayText="Former" w:value="former"/><w:listItem w:displayText="Current" w:value="current"/></w:dropDownList></w:sdtPr><w:sdtContent><w:r><w:t>Choose an item.</w:t></w:r></w:sdtContent></w:sdt></w:p>
  <w:p><w:r><w:t>Encounter category: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="4103"/><w:tag w:val="qa_encounter_category"/><w:alias w:val="Synthetic encounter category"/><w:comboBox><w:listItem w:displayText="Initial" w:value="initial"/><w:listItem w:displayText="Follow-up" w:value="follow_up"/></w:comboBox></w:sdtPr><w:sdtContent><w:r><w:t>Initial</w:t></w:r></w:sdtContent></w:sdt></w:p>
  <w:p><w:r><w:t>Encounter date: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="4104"/><w:tag w:val="qa_encounter_date"/><w:alias w:val="Synthetic encounter date"/><w:date><w:dateFormat w:val="yyyy-MM-dd"/><w:lid w:val="en-US"/><w:storeMappedDataAs w:val="dateTime"/></w:date><w:showingPlcHdr/></w:sdtPr><w:sdtContent><w:r><w:rPr><w:rStyle w:val="PlaceholderText"/></w:rPr><w:t>YYYY-MM-DD</w:t></w:r></w:sdtContent></w:sdt></w:p>
  <w:p><w:r><w:t>Respiratory symptom documented: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="4105"/><w:tag w:val="qa_respiratory_symptom"/><w:alias w:val="Synthetic respiratory symptom"/><w14:checkbox><w14:checked w14:val="0"/><w14:checkedState w14:val="2612" w14:font="MS Gothic"/><w14:uncheckedState w14:val="2610" w14:font="MS Gothic"/></w14:checkbox></w:sdtPr><w:sdtContent><w:r><w:t>☐</w:t></w:r></w:sdtContent></w:sdt></w:p>
  <w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/><w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid><w:gridCol w:w="3200"/><w:gridCol w:w="5800"/></w:tblGrid>
    <w:tr><w:tc><w:tcPr><w:tcW w:w="3200" w:type="dxa"/></w:tcPr><w:p><w:r><w:t>Plan item</w:t></w:r></w:p></w:tc><w:tc><w:tcPr><w:tcW w:w="5800" w:type="dxa"/></w:tcPr><w:p>${textControl(4106, "qa_plan_item", "Synthetic plan item")}</w:p></w:tc></w:tr>
    <w:tr><w:tc><w:tcPr><w:tcW w:w="3200" w:type="dxa"/></w:tcPr><w:p><w:r><w:t>Plan detail</w:t></w:r></w:p></w:tc><w:tc><w:tcPr><w:tcW w:w="5800" w:type="dxa"/></w:tcPr><w:p><w:pPr><w:tabs><w:tab w:val="left" w:pos="2520"/></w:tabs><w:jc w:val="left"/></w:pPr></w:p></w:tc></w:tr>
  </w:tbl>
  <w:p><w:r><w:t xml:space="preserve">Additional synthetic detail: &lt;&lt;insert synthetic </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>detail&gt;&gt;</w:t></w:r><w:r><w:t xml:space="preserve"> (physician confirmation required)</w:t></w:r></w:p>
  <w:p><w:r><w:t>SYNTHETIC TEST ONLY — NOT FOR PATIENT CARE</w:t></w:r></w:p>
  <w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/><w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" w:header="540" w:footer="540" w:gutter="0"/></w:sectPr>
</w:body></w:document>`;

const ENTRIES: Readonly<Record<string, string>> = {
  "[Content_Types].xml": CONTENT_TYPES,
  "_rels/.rels": ROOT_RELS,
  "docProps/core.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Template Twin synthetic QA fixture</dc:title><dc:creator>Synthetic QA</dc:creator><cp:lastModifiedBy>Synthetic QA</cp:lastModifiedBy></cp:coreProperties>`,
  "docProps/app.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Template Twin Synthetic QA</Application><AppVersion>1.0</AppVersion></Properties>`,
  "word/document.xml": DOCUMENT_XML,
  "word/_rels/document.xml.rels": DOCUMENT_RELS,
  "word/styles.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="${W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style><w:style w:type="paragraph" w:styleId="QAHeading"><w:name w:val="QA Heading"/><w:basedOn w:val="Normal"/><w:qFormat/><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style><w:style w:type="character" w:styleId="PlaceholderText"><w:name w:val="Placeholder Text"/><w:rPr><w:color w:val="A0A0A0"/></w:rPr></w:style></w:styles>`,
  "word/settings.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings xmlns:w="${W}"><w:zoom w:percent="100"/><w:defaultTabStop w:val="720"/><w:compat/></w:settings>`,
  "word/fontTable.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:fonts xmlns:w="${W}"><w:font w:name="Calibri"><w:family w:val="swiss"/><w:pitch w:val="variable"/></w:font><w:font w:name="MS Gothic"><w:family w:val="modern"/><w:pitch w:val="fixed"/></w:font></w:fonts>`,
  "word/header1.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:hdr xmlns:w="${W}"><w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/></w:rPr><w:t>Synthetic Clinic — Template Twin QA</w:t></w:r></w:p></w:hdr>`,
  "word/footer1.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr xmlns:w="${W}"><w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:t>Synthetic document; no patient data.</w:t></w:r></w:p></w:ftr>`,
};

export function templateTwinStagingQaSha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

/**
 * Identify the one immutable DOCX source that may expose staging-only UI.
 * Template names, encounter scopes, and a globally enabled gate are not
 * provenance: only the compiler-persisted source digest and byte count are.
 */
export function isTemplateTwinStagingQaFixtureSource(input: {
  sha256: string;
  sizeBytes: number;
}): boolean {
  return (
    input.sha256 === TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256 &&
    input.sizeBytes === TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES
  );
}

export async function buildTemplateTwinStagingQaDocx(): Promise<Buffer> {
  // Build each call from an independent JSZip instance. The fixed timestamps,
  // entry order, platform, and compression settings make this byte-for-byte
  // deterministic without relying on an in-process cache as false proof.
  const zip = new JSZip();
  for (const [name, value] of Object.entries(ENTRIES)) {
    zip.file(name, value, { date: FIXED_ZIP_DATE, createFolders: false });
  }
  return zip.generateAsync({
    type: "nodebuffer",
    compression: "DEFLATE",
    compressionOptions: { level: 6 },
    platform: "DOS",
  });
}

export async function templateTwinStagingQaFixtureDescriptor(): Promise<{
  bytes: Buffer;
  sha256: string;
  sizeBytes: number;
  filename: typeof TEMPLATE_TWIN_STAGING_QA_FIXTURE_FILENAME;
  mimeType: typeof TEMPLATE_TWIN_STAGING_QA_FIXTURE_MIME;
  fixtureVersion: typeof TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION;
}> {
  if (
    TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER !==
    TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT
  ) {
    throw new Error(
      "The visible synthetic evidence starter drifted from the reviewed provider transcript.",
    );
  }
  const bytes = await buildTemplateTwinStagingQaDocx();
  const sha256 = templateTwinStagingQaSha256(bytes);
  if (sha256 !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256) {
    throw new Error(
      "The synthetic QA fixture bytes changed without a versioned allowlist update.",
    );
  }
  if (bytes.byteLength !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES) {
    throw new Error(
      "The synthetic QA fixture size changed without a versioned allowlist update.",
    );
  }
  return {
    bytes,
    sha256,
    sizeBytes: bytes.byteLength,
    filename: TEMPLATE_TWIN_STAGING_QA_FIXTURE_FILENAME,
    mimeType: TEMPLATE_TWIN_STAGING_QA_FIXTURE_MIME,
    fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  };
}

/** Deterministic 0.5-second mono PCM WAV. It carries no speech or metadata. */
export function buildTemplateTwinStagingQaWav(): Buffer {
  const sampleRate = 8_000;
  const sampleCount = sampleRate / 2;
  const bytes = Buffer.alloc(44 + sampleCount * 2);
  bytes.write("RIFF", 0, "ascii");
  bytes.writeUInt32LE(bytes.byteLength - 8, 4);
  bytes.write("WAVE", 8, "ascii");
  bytes.write("fmt ", 12, "ascii");
  bytes.writeUInt32LE(16, 16);
  bytes.writeUInt16LE(1, 20);
  bytes.writeUInt16LE(1, 22);
  bytes.writeUInt32LE(sampleRate, 24);
  bytes.writeUInt32LE(sampleRate * 2, 28);
  bytes.writeUInt16LE(2, 32);
  bytes.writeUInt16LE(16, 34);
  bytes.write("data", 36, "ascii");
  bytes.writeUInt32LE(sampleCount * 2, 40);
  for (let index = 0; index < sampleCount; index += 1) {
    const sample = Math.round(
      Math.sin((2 * Math.PI * 440 * index) / sampleRate) * 512,
    );
    bytes.writeInt16LE(sample, 44 + index * 2);
  }
  if (
    bytes.byteLength !== TEMPLATE_TWIN_STAGING_QA_WAV_SIZE_BYTES ||
    templateTwinStagingQaSha256(bytes) !== TEMPLATE_TWIN_STAGING_QA_WAV_SHA256
  ) {
    throw new Error(
      "The synthetic QA voice fixture changed without an allowlist update.",
    );
  }
  return bytes;
}
