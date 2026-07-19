import JSZip from 'jszip';

import { compileTemplateDocx } from '../../note-template-docx/compiler';
import { buildSyntheticDocx } from '../../note-template-docx/__tests__/synthetic-docx';
import {
  SemanticMappingSchema,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
} from '../ir';
import {
  projectEncounterFacts,
  type EncounterEntitySnapshot,
  type EncounterInputMode,
} from '../encounter-facts';
import { expectedDataTypeForFieldKind } from '../semantic-mapping';

const DOCUMENT_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p><w:r><w:t>Chief concern: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="300"/><w:alias w:val="Chief concern"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter concern</w:t></w:r></w:sdtContent></w:sdt></w:p>
    <w:p><w:r><w:t>Smoking: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="301"/><w:alias w:val="Smoking status"/><w:dropDownList><w:listItem w:displayText="Never" w:value="never"/><w:listItem w:displayText="Current" w:value="current"/></w:dropDownList></w:sdtPr><w:sdtContent><w:r><w:t>Choose an item.</w:t></w:r></w:sdtContent></w:sdt></w:p>
    <w:p><w:r><w:t>Medication documented: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="302"/><w:alias w:val="Medication documented"/><w14:checkbox><w14:checked w14:val="0"/><w14:checkedState w14:val="2612"/><w14:uncheckedState w14:val="2610"/></w14:checkbox></w:sdtPr><w:sdtContent><w:r><w:t>☐</w:t></w:r></w:sdtContent></w:sdt></w:p>
    <w:tbl><w:tblGrid><w:gridCol w:w="2200"/><w:gridCol w:w="5000"/></w:tblGrid><w:tr><w:tc><w:p><w:r><w:t>Plan</w:t></w:r></w:p></w:tc><w:tc><w:p><w:sdt><w:sdtPr><w:id w:val="303"/><w:alias w:val="Plan item"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter plan</w:t></w:r></w:sdtContent></w:sdt></w:p></w:tc></w:tr><w:tr><w:tc><w:p><w:r><w:t>Plan detail</w:t></w:r></w:p></w:tc><w:tc><w:p><w:pPr><w:tabs><w:tab w:val="left" w:pos="720"/></w:tabs><w:spacing w:after="0"/></w:pPr></w:p></w:tc></w:tr></w:tbl>
    <w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr>
  </w:body>
</w:document>`;

const HEADER_XML = `<?xml version="1.0" encoding="UTF-8"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Synthetic Clinic Header</w:t></w:r></w:p></w:hdr>`;

export const SYNTHETIC_CONTEXT = [
  'Clinician: Chief concern is synthetic wrist discomfort.',
  'Clinician: Smoking status is Current.',
  'Clinician: Medication Syntheticmed documented.',
  'Clinician: Plan use synthetic brace.',
].join('\n');

export const SYNTHETIC_ENTITIES: EncounterEntitySnapshot = {
  chief_complaint: {
    statement: 'synthetic wrist discomfort',
    evidence_quote: 'Chief concern is synthetic wrist discomfort.',
    speaker: 'Clinician',
    timestamp: 1.25,
  },
  social_history: {
    smoking: {
      status: 'Current',
      evidence_quote: 'Smoking status is Current.',
      speaker: 'Clinician',
      timestamp: 2.5,
    },
  },
  medications: [
    {
      name: 'Syntheticmed',
      evidence_quote: 'Medication Syntheticmed documented.',
      speaker: 'Clinician',
      timestamp: 3.75,
    },
  ],
  plan_discussed: [
    {
      item: 'Use synthetic brace',
      evidence_quote: 'Plan use synthetic brace.',
      speaker: 'Clinician',
      timestamp: 5,
    },
  ],
};

export async function buildTemplateTwinIntegrationFixture(): Promise<{
  source: Buffer;
  ir: TemplateDocIR;
  mappings: SemanticMapping[];
}> {
  const base = await buildSyntheticDocx({ documentXml: DOCUMENT_XML });
  const zip = await JSZip.loadAsync(base);
  zip.file('word/header1.xml', HEADER_XML);
  const source = await zip.generateAsync({
    type: 'nodebuffer',
    compression: 'DEFLATE',
    compressionOptions: { level: 6 },
  });
  const ir = compileTemplateDocx(source);
  const mappings = ir.fields.map(mappingForField);
  return { source, ir, mappings };
}

export function factsForMode(mode: EncounterInputMode) {
  return projectEncounterFacts({
    mode,
    contextText: SYNTHETIC_CONTEXT,
    entities: SYNTHETIC_ENTITIES,
    asrQuality: mode === 'text' ? undefined : 'high',
  });
}

function mappingForField(field: TemplateField): SemanticMapping {
  const expectedDataType = expectedDataTypeForFieldKind(field.kind);
  if (!expectedDataType) throw new Error('Synthetic fixture field is not fillable');
  const clinicalConcept = (() => {
    switch (field.originalLabel) {
      case 'Chief concern':
        return 'chief_complaint';
      case 'Smoking status':
        return 'social_history.smoking';
      case 'Medication documented':
        return 'medication.name';
      case 'Plan item':
      case 'Plan detail':
        return 'plan';
      default:
        throw new Error(`Unexpected synthetic field: ${field.originalLabel}`);
    }
  })();
  return SemanticMappingSchema.parse({
    fieldId: field.fieldId,
    clinicalConcept,
    expectedDataType,
    polarityBehavior:
      field.kind === 'checkbox' ? 'affirmative_only' : 'value_only',
    temporality: 'any',
    laterality: 'not_applicable',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    required: true,
    blankPolicy: 'requires_input',
    unknownPolicy: 'requires_input',
    practiceDefault: null,
    status: 'certified',
  });
}
