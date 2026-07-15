import JSZip from 'jszip';

import type { SemanticMapping } from '../../../src/lib/template-twin/ir';

export const TEMPLATE_TWIN_SYNTHETIC_EVIDENCE = [
  'Synthetic test encounter with no real patient information.',
  'Chief concern is synthetic wrist discomfort.',
  'Smoking status is Current.',
  'Medication Syntheticmed documented.',
  'Plan use synthetic brace.',
].join(' ');

export interface TemplateTwinPersistedField {
  fieldId: string;
  originalLabel: string;
  fieldKind: string;
  mapping: SemanticMapping;
}

const CONTENT_TYPES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
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
</Relationships>`;

const DOCUMENT_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p><w:r><w:t>Synthetic Template Twin QA — immutable static title</w:t></w:r></w:p>
    <w:p>
      <w:r><w:t>Chief concern: </w:t></w:r>
      <w:sdt>
        <w:sdtPr><w:id w:val="300"/><w:alias w:val="Chief concern"/><w:tag w:val="chief_concern"/><w:text/><w:showingPlcHdr/></w:sdtPr>
        <w:sdtContent><w:r><w:rPr><w:rStyle w:val="PlaceholderText"/></w:rPr><w:t>Enter concern</w:t></w:r></w:sdtContent>
      </w:sdt>
    </w:p>
    <w:p>
      <w:r><w:t>Smoking: </w:t></w:r>
      <w:sdt>
        <w:sdtPr><w:id w:val="301"/><w:alias w:val="Smoking status"/><w:tag w:val="smoking_status"/><w:dropDownList><w:listItem w:displayText="Never" w:value="never"/><w:listItem w:displayText="Current" w:value="current"/></w:dropDownList></w:sdtPr>
        <w:sdtContent><w:r><w:t>Choose an item.</w:t></w:r></w:sdtContent>
      </w:sdt>
    </w:p>
    <w:p>
      <w:r><w:t>Medication documented: </w:t></w:r>
      <w:sdt>
        <w:sdtPr><w:id w:val="302"/><w:alias w:val="Medication documented"/><w:tag w:val="medication_documented"/><w14:checkbox><w14:checked w14:val="0"/><w14:checkedState w14:val="2612"/><w14:uncheckedState w14:val="2610"/></w14:checkbox></w:sdtPr>
        <w:sdtContent><w:r><w:t>☐</w:t></w:r></w:sdtContent>
      </w:sdt>
    </w:p>
    <w:tbl>
      <w:tblGrid><w:gridCol w:w="2200"/><w:gridCol w:w="5000"/></w:tblGrid>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Plan</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:sdt><w:sdtPr><w:id w:val="303"/><w:alias w:val="Plan item"/><w:tag w:val="plan_item"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter plan</w:t></w:r></w:sdtContent></w:sdt></w:p></w:tc>
      </w:tr>
    </w:tbl>
    <w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr>
  </w:body>
</w:document>`;

const HEADER_XML = `<?xml version="1.0" encoding="UTF-8"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Synthetic Clinic Header</w:t></w:r></w:p></w:hdr>`;

const FOOTER_XML = `<?xml version="1.0" encoding="UTF-8"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Page </w:t></w:r><w:fldSimple w:instr=" PAGE "><w:r><w:t>1</w:t></w:r></w:fldSimple></w:p></w:ftr>`;

export async function buildTemplateTwinSafeAlphaDocx(): Promise<Buffer> {
  const zip = new JSZip();
  zip.file('[Content_Types].xml', CONTENT_TYPES);
  zip.file('_rels/.rels', ROOT_RELATIONSHIPS);
  zip.file('word/document.xml', DOCUMENT_XML);
  zip.file('word/_rels/document.xml.rels', DOCUMENT_RELATIONSHIPS);
  zip.file('word/header1.xml', HEADER_XML);
  zip.file('word/footer1.xml', FOOTER_XML);
  zip.file(
    'word/styles.xml',
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="paragraph" w:styleId="Normal"/><w:style w:type="character" w:styleId="PlaceholderText"/></w:styles>',
  );
  return zip.generateAsync({
    type: 'nodebuffer',
    compression: 'DEFLATE',
    compressionOptions: { level: 6 },
  });
}

export function certifiedTemplateTwinMappings(
  fields: readonly TemplateTwinPersistedField[],
): SemanticMapping[] {
  const conceptByLabel: Readonly<Record<string, string>> = {
    'Chief concern': 'chief_complaint',
    'Smoking status': 'social_history.smoking',
    'Medication documented': 'medication.name',
    'Plan item': 'plan',
  };

  return fields.map((field) => {
    const clinicalConcept = conceptByLabel[field.originalLabel];
    if (!clinicalConcept) {
      throw new Error(
        `Unexpected Template Twin QA field label: ${field.originalLabel}`,
      );
    }
    return {
      ...field.mapping,
      clinicalConcept,
      polarityBehavior:
        field.fieldKind === 'checkbox' ? 'affirmative_only' : 'value_only',
      temporality: 'any',
      laterality: 'not_applicable',
      unitPolicy: 'not_applicable',
      approvedSynonyms: [],
      required: true,
      blankPolicy: 'requires_input',
      unknownPolicy: 'requires_input',
      practiceDefault: null,
      status: 'certified',
    } satisfies SemanticMapping;
  });
}
