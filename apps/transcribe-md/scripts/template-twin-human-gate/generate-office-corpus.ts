import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import JSZip from "jszip";

import { buildSyntheticDocx } from "../../src/lib/note-template-docx/__tests__/synthetic-docx";
import { buildTabOnlyTableCellOfficeCorpusDocx } from "../../src/lib/note-template-docx/__tests__/tab-only-office-corpus";
import { buildOfficeExpectedValueManifest } from "../../src/lib/note-template-docx/office-docx-byte-readback";
import { compileTemplateDocx } from "../../src/lib/note-template-docx/compiler";
import { inspectDocxPackage } from "../../src/lib/note-template-docx/package-security";
import { readbackTemplateDocxOutput } from "../../src/lib/note-template-docx/output-readback";
import { renderTemplateDocx } from "../../src/lib/note-template-docx/renderer";
import {
  projectEncounterFacts,
  type EncounterEntitySnapshot,
} from "../../src/lib/template-twin/encounter-facts";
import {
  SemanticMappingSchema,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
} from "../../src/lib/template-twin/ir";
import { resolveTemplateFields } from "../../src/lib/template-twin/resolver";
import { expectedDataTypeForFieldKind } from "../../src/lib/template-twin/semantic-mapping/compatibility";
import { validateTemplateTwin } from "../../src/lib/template-twin/validation";

const FIXED_ZIP_DATE = new Date("2000-01-01T00:00:00.000Z");
const W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
const W14 = "http://schemas.microsoft.com/office/word/2010/wordml";
const R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";

interface CliOptions {
  readonly outputRoot: string;
  readonly sourceCommit: string;
  readonly generatedAtIso: string;
}

interface CorpusCase {
  readonly id: string;
  readonly source: () => Promise<Buffer>;
  readonly conceptForField: (field: TemplateField, index: number) => string;
  readonly entities: EncounterEntitySnapshot;
  readonly quotes: readonly string[];
  readonly expected: "rendered_verified" | "blocked_as_expected";
  readonly expectedCompilerBlockerCodes?: readonly string[];
  readonly expectedBlockerCodes?: readonly string[];
  readonly expectedPageCount: number | null;
  readonly minimumExpectedPages: number;
}

function invariant(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function parseOptions(argv: readonly string[]): CliOptions {
  const values = new Map<string, string>();
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || !value)
      throw new Error("Expected --name value arguments.");
    values.set(key.slice(2), value);
  }
  const outputRoot = values.get("output-root");
  const sourceCommit = values.get("source-commit");
  const generatedAtIso = values.get("generated-at");
  invariant(
    typeof outputRoot === "string" &&
      outputRoot.startsWith("/tmp/template-twin-human-gate-"),
    "Output must be in the dedicated /tmp namespace.",
  );
  invariant(
    typeof sourceCommit === "string" && /^[a-f0-9]{40}$/u.test(sourceCommit),
    "A full lowercase source commit is required.",
  );
  invariant(
    typeof generatedAtIso === "string" &&
      !Number.isNaN(Date.parse(generatedAtIso)),
    "A deterministic generated-at timestamp is required.",
  );
  return { outputRoot, sourceCommit, generatedAtIso };
}

function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function xmlText(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function xmlAttribute(value: string): string {
  return xmlText(value).replaceAll('"', "&quot;").replaceAll("'", "&apos;");
}

function textControl(id: number, tag: string, alias: string): string {
  return `<w:sdt><w:sdtPr><w:id w:val="${id}"/><w:tag w:val="${xmlAttribute(tag)}"/><w:alias w:val="${xmlAttribute(alias)}"/><w:text/><w:showingPlcHdr/></w:sdtPr><w:sdtContent><w:r><w:rPr><w:rStyle w:val="PlaceholderText"/></w:rPr><w:t>Enter synthetic value</w:t></w:r></w:sdtContent></w:sdt>`;
}

function dropdownControl(id: number, tag: string, alias: string): string {
  return `<w:sdt><w:sdtPr><w:id w:val="${id}"/><w:tag w:val="${tag}"/><w:alias w:val="${alias}"/><w:dropDownList><w:listItem w:displayText="First" w:value="first"/><w:listItem w:displayText="Middle" w:value="middle"/><w:listItem w:displayText="Last" w:value="last"/></w:dropDownList></w:sdtPr><w:sdtContent><w:r><w:t>Choose an item.</w:t></w:r></w:sdtContent></w:sdt>`;
}

function comboControl(id: number, tag: string, alias: string): string {
  return `<w:sdt><w:sdtPr><w:id w:val="${id}"/><w:tag w:val="${tag}"/><w:alias w:val="${alias}"/><w:comboBox><w:listItem w:displayText="Initial" w:value="initial"/><w:listItem w:displayText="Follow-up" w:value="follow_up"/><w:listItem w:displayText="Final" w:value="final"/></w:comboBox></w:sdtPr><w:sdtContent><w:r><w:t>Initial</w:t></w:r></w:sdtContent></w:sdt>`;
}

function dateControl(id: number, tag: string, alias: string): string {
  return `<w:sdt><w:sdtPr><w:id w:val="${id}"/><w:tag w:val="${tag}"/><w:alias w:val="${alias}"/><w:date><w:dateFormat w:val="yyyy-MM-dd"/><w:lid w:val="en-US"/><w:storeMappedDataAs w:val="dateTime"/></w:date><w:showingPlcHdr/></w:sdtPr><w:sdtContent><w:r><w:rPr><w:rStyle w:val="PlaceholderText"/></w:rPr><w:t>YYYY-MM-DD</w:t></w:r></w:sdtContent></w:sdt>`;
}

function checkboxControl(id: number, tag: string, alias: string): string {
  return `<w:sdt><w:sdtPr><w:id w:val="${id}"/><w:tag w:val="${tag}"/><w:alias w:val="${alias}"/><w14:checkbox><w14:checked w14:val="0"/><w14:checkedState w14:val="2612" w14:font="MS Gothic"/><w14:uncheckedState w14:val="2610" w14:font="MS Gothic"/></w14:checkbox></w:sdtPr><w:sdtContent><w:r><w:t>☐</w:t></w:r></w:sdtContent></w:sdt>`;
}

function legacyTextField(name: string, kind: "text" | "date"): string {
  const details =
    kind === "date"
      ? '<w:type w:val="date"/><w:default w:val="2000-01-01"/><w:format w:val="yyyy-MM-dd"/>'
      : '<w:type w:val="regular"/><w:default w:val="Synthetic placeholder"/><w:maxLength w:val="32767"/>';
  const result = kind === "date" ? "2000-01-01" : "Synthetic placeholder";
  return `<w:p><w:r><w:t xml:space="preserve">${xmlText(name)}: </w:t></w:r><w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="${xmlAttribute(name)}"/><w:enabled/><w:textInput>${details}</w:textInput></w:ffData></w:fldChar></w:r><w:r><w:instrText xml:space="preserve"> FORMTEXT </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>${result}</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>`;
}

function legacyDropdownField(name: string): string {
  return `<w:p><w:r><w:t xml:space="preserve">${xmlText(name)}: </w:t></w:r><w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="${xmlAttribute(name)}"/><w:enabled/><w:ddList><w:result w:val="0"/><w:listEntry w:val="Low"/><w:listEntry w:val="Medium"/><w:listEntry w:val="High"/></w:ddList></w:ffData></w:fldChar></w:r><w:r><w:instrText xml:space="preserve"> FORMDROPDOWN </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>Low</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>`;
}

function legacyCheckboxField(name: string): string {
  return `<w:p><w:r><w:t xml:space="preserve">${xmlText(name)}: </w:t></w:r><w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="${xmlAttribute(name)}"/><w:enabled/><w:checkBox><w:sizeAuto/><w:default w:val="0"/><w:checked w:val="0"/></w:checkBox></w:ffData></w:fldChar></w:r><w:r><w:instrText xml:space="preserve"> FORMCHECKBOX </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>☐</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>`;
}

async function normalizeDocx(bytes: Uint8Array): Promise<Buffer> {
  const zip = await JSZip.loadAsync(bytes);
  zip.forEach((_name, entry) => {
    entry.date = FIXED_ZIP_DATE;
  });
  return zip.generateAsync({
    type: "nodebuffer",
    compression: "DEFLATE",
    compressionOptions: { level: 6 },
    platform: "DOS",
  });
}

function staticHeaderFooter(): Record<string, string> {
  return {
    "word/header1.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:hdr xmlns:w="${W}"><w:p><w:r><w:t>Synthetic Practice — Template Twin QA</w:t></w:r></w:p></w:hdr>`,
    "word/footer1.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr xmlns:w="${W}"><w:p><w:r><w:t>Synthetic document; no patient data.</w:t></w:r></w:p></w:ftr>`,
  };
}

async function modernControlsSource(): Promise<Buffer> {
  const documentXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="${W}" xmlns:w14="${W14}" xmlns:r="${R}"><w:body>
  <w:p><w:r><w:t>Synthetic clinical Office corpus</w:t></w:r></w:p>
  <w:p><w:r><w:t>Short text: </w:t></w:r>${textControl(1001, "short_text", "Short text")}</w:p>
  <w:p><w:r><w:t>Normal text: </w:t></w:r>${textControl(1002, "normal_text", "Normal text")}</w:p>
  <w:p><w:r><w:t>First dropdown: </w:t></w:r>${dropdownControl(1003, "dropdown_first", "First dropdown")}</w:p>
  <w:p><w:r><w:t>Middle dropdown: </w:t></w:r>${dropdownControl(1004, "dropdown_middle", "Middle dropdown")}</w:p>
  <w:p><w:r><w:t>Last dropdown: </w:t></w:r>${dropdownControl(1005, "dropdown_last", "Last dropdown")}</w:p>
  <w:p><w:r><w:t>Combo: </w:t></w:r>${comboControl(1006, "combo_value", "Combo")}</w:p>
  <w:p><w:r><w:t>Date: </w:t></w:r>${dateControl(1007, "encounter_date", "Encounter date")}</w:p>
  <w:p><w:r><w:t>Affirmative: </w:t></w:r>${checkboxControl(1008, "checkbox_true", "Affirmative checkbox")}</w:p>
  <w:p><w:r><w:t>Explicit denial: </w:t></w:r>${checkboxControl(1009, "checkbox_false", "Explicit denial checkbox")}</w:p>
  <w:p><w:r><w:t>Unicode and XML: </w:t></w:r>${textControl(1010, "unicode_xml_text", "Unicode and XML text")}</w:p>
  <w:tbl><w:tblPr><w:tblW w:w="7800" w:type="dxa"/><w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid><w:gridCol w:w="2800"/><w:gridCol w:w="5000"/></w:tblGrid><w:tr><w:tc><w:p><w:r><w:t>Assessment</w:t></w:r></w:p></w:tc><w:tc><w:p>${textControl(1011, "assessment", "Assessment")}</w:p></w:tc></w:tr></w:tbl>
  <w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720"/></w:sectPr>
</w:body></w:document>`;
  return normalizeDocx(
    await buildSyntheticDocx({
      documentXml,
      extraEntries: staticHeaderFooter(),
    }),
  );
}

async function maximumTextSource(): Promise<Buffer> {
  const documentXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="${W}" xmlns:r="${R}"><w:body><w:p><w:r><w:t>Maximum approved text</w:t></w:r></w:p><w:p>${textControl(3001, "maximum_text", "Maximum text")}</w:p><w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr></w:body></w:document>`;
  return normalizeDocx(
    await buildSyntheticDocx({
      documentXml,
      extraEntries: staticHeaderFooter(),
    }),
  );
}

async function legacyControlsSource(): Promise<Buffer> {
  const body = [
    legacyTextField("Legacy note", "text"),
    legacyDropdownField("Legacy severity"),
    legacyCheckboxField("Legacy checkbox"),
  ].join("");
  const documentXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="${W}" xmlns:r="${R}"><w:body><w:p><w:r><w:t>Synthetic legacy controls</w:t></w:r></w:p>${body}<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr></w:body></w:document>`;
  return normalizeDocx(
    await buildSyntheticDocx({
      documentXml,
      extraEntries: staticHeaderFooter(),
    }),
  );
}

async function unsupportedLegacyDateSource(): Promise<Buffer> {
  const documentXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="${W}" xmlns:r="${R}"><w:body><w:p><w:r><w:t>Synthetic unsupported legacy date</w:t></w:r></w:p>${legacyTextField("Legacy date", "date")}<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr></w:body></w:document>`;
  return normalizeDocx(
    await buildSyntheticDocx({
      documentXml,
      extraEntries: staticHeaderFooter(),
    }),
  );
}

async function ordinaryPlaceholderSource(): Promise<Buffer> {
  const documentXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="${W}" xmlns:r="${R}"><w:body>
  <w:p><w:r><w:t>Synthetic placeholder corpus</w:t></w:r></w:p>
  <w:p><w:r><w:t xml:space="preserve">Finding: &lt;&lt;insert synthetic </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>finding&gt;&gt;</w:t></w:r><w:r><w:t xml:space="preserve"> (reviewed)</w:t></w:r></w:p>
  <w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr>
</w:body></w:document>`;
  return normalizeDocx(
    await buildSyntheticDocx({
      documentXml,
      extraEntries: staticHeaderFooter(),
    }),
  );
}

async function unresolvedCheckboxSource(): Promise<Buffer> {
  const documentXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="${W}" xmlns:w14="${W14}" xmlns:r="${R}"><w:body>
  <w:p><w:r><w:t>Synthetic unresolved safety case: </w:t></w:r><w:sdt><w:sdtPr><w:id w:val="2001"/><w:tag w:val="unresolved_checkbox"/><w:alias w:val="Required safety confirmation"/><w14:checkbox><w14:checked w14:val="0"/><w14:checkedState w14:val="2612"/><w14:uncheckedState w14:val="2610"/></w14:checkbox></w:sdtPr><w:sdtContent><w:r><w:t>☐</w:t></w:r></w:sdtContent></w:sdt></w:p>
  <w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr>
</w:body></w:document>`;
  return normalizeDocx(
    await buildSyntheticDocx({
      documentXml,
      extraEntries: staticHeaderFooter(),
    }),
  );
}

function mappingsFor(
  ir: TemplateDocIR,
  conceptForField: CorpusCase["conceptForField"],
): SemanticMapping[] {
  return ir.fields.map((field, index) => {
    const expectedDataType = expectedDataTypeForFieldKind(field.kind);
    invariant(
      expectedDataType !== null,
      `No fillable data type for ${field.kind}.`,
    );
    return SemanticMappingSchema.parse({
      fieldId: field.fieldId,
      clinicalConcept: conceptForField(field, index),
      expectedDataType,
      polarityBehavior:
        field.rendererBinding.tag === "checkbox_false"
          ? "explicit_denial_allowed"
          : field.kind === "checkbox"
            ? "affirmative_only"
            : "value_only",
      temporality: "any",
      laterality: "not_applicable",
      unitPolicy: "not_applicable",
      approvedSynonyms: [],
      required: true,
      blankPolicy: "requires_input",
      unknownPolicy: "requires_input",
      practiceDefault: null,
      status: "certified",
    });
  });
}

function bindingManifest(ir: TemplateDocIR): unknown {
  return {
    irSchemaVersion: ir.irSchemaVersion,
    compilerVersion: ir.compilerVersion,
    sourceSha256: ir.source.sha256,
    structureSha256: ir.structureSha256,
    staticContentSha256: ir.staticContentSha256,
    fields: ir.fields.map((field) => ({
      fieldId: field.fieldId,
      kind: field.kind,
      detectionStatus: field.detectionStatus,
      allowedOptions: field.allowedOptions,
      binding: field.rendererBinding,
    })),
  };
}

function packageSummary(bytes: Uint8Array): unknown {
  const inspected = inspectDocxPackage(bytes);
  return {
    sourceSha256: inspected.sourceSha256,
    sizeBytes: bytes.byteLength,
    entryCount: inspected.zip.entries.size,
    mainPartName: inspected.mainPartName,
    headerPartNames: inspected.headerPartNames,
    footerPartNames: inspected.footerPartNames,
    relationshipCount: inspected.relationships.length,
  };
}

async function writeJson(file: string, value: unknown): Promise<void> {
  await mkdir(path.dirname(file), { recursive: true });
  await writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function cases(): readonly CorpusCase[] {
  const normalText =
    "Synthetic normal clinical narrative for a local Office compatibility audit.";
  const unicodeText =
    'Synthetic café — αβ; symbols & < > "quoted" remain literal.';
  const maximumText = "Synthetic stable compatibility value "
    .repeat(1_200)
    .slice(0, 32_767)
    .padEnd(32_767, "x");
  return [
    {
      id: "modern-controls",
      source: modernControlsSource,
      conceptForField: (field) => {
        const tag = field.rendererBinding.tag;
        if (tag === "short_text") return "chief_complaint";
        if (tag === "normal_text") return "hpi.quality";
        if (tag === "dropdown_first") return "social_history.smoking";
        if (tag === "dropdown_middle") return "social_history.alcohol";
        if (tag === "dropdown_last") return "social_history.drugs";
        if (tag === "combo_value") return "hpi.severity";
        if (tag === "encounter_date") return "hpi.onset";
        if (tag === "checkbox_true") return "medication.name";
        if (tag === "checkbox_false") return "allergy.substance";
        if (tag === "unicode_xml_text") return "social_history.occupation";
        if (tag === "assessment") return "assessment";
        throw new Error(`No synthetic mapping for ${tag ?? field.fieldId}.`);
      },
      entities: {
        chief_complaint: {
          statement: "OK",
          evidence_quote: "Short synthetic value is OK.",
          speaker: "Clinician",
        },
        hpi: {
          quality: normalText,
          severity: "follow_up",
          onset: "2026-07-16",
          evidence_quote:
            "Synthetic quality, follow_up category, and 2026-07-16 onset.",
          speaker: "Clinician",
        },
        medications: [
          {
            name: "Syntheticmed",
            evidence_quote: "Medication Syntheticmed was reviewed.",
            speaker: "Clinician",
          },
        ],
        allergies: [
          {
            substance: "Synthetic latex",
            evidence_quote: "No allergy to Synthetic latex.",
            speaker: "Clinician",
          },
        ],
        social_history: {
          smoking: {
            status: "first",
            evidence_quote: "Smoking selection is first.",
            speaker: "Clinician",
          },
          alcohol: {
            status: "middle",
            evidence_quote: "Alcohol selection is middle.",
            speaker: "Clinician",
          },
          drugs: {
            status: "last",
            evidence_quote: "Substance selection is last.",
            speaker: "Clinician",
          },
          occupation: {
            value: unicodeText,
            evidence_quote: unicodeText,
            speaker: "Clinician",
          },
        },
        assessment_discussed: [
          {
            finding: "Synthetic assessment retained exactly.",
            evidence_quote: "Synthetic assessment retained exactly.",
            speaker: "Clinician",
          },
        ],
      },
      quotes: [
        "Short synthetic value is OK.",
        "Synthetic quality, follow_up category, and 2026-07-16 onset.",
        "Medication Syntheticmed was reviewed.",
        "No allergy to Synthetic latex.",
        "Smoking selection is first.",
        "Alcohol selection is middle.",
        "Substance selection is last.",
        unicodeText,
        "Synthetic assessment retained exactly.",
      ],
      expected: "rendered_verified",
      expectedPageCount: 1,
      minimumExpectedPages: 1,
    },
    {
      id: "maximum-text",
      source: maximumTextSource,
      conceptForField: () => "assessment",
      entities: {
        assessment_discussed: [
          {
            finding: maximumText,
            evidence_quote: maximumText,
            speaker: "Clinician",
          },
        ],
      },
      quotes: [maximumText],
      expected: "rendered_verified",
      expectedPageCount: null,
      minimumExpectedPages: 1,
    },
    {
      id: "legacy-controls",
      source: legacyControlsSource,
      conceptForField: (field) => {
        const name = field.rendererBinding.legacyName;
        if (name === "Legacy note") return "past_medical_history";
        if (name === "Legacy severity") return "hpi.duration";
        if (name === "Legacy checkbox") return "test.name";
        throw new Error(
          `No synthetic legacy mapping for ${name ?? field.fieldId}.`,
        );
      },
      entities: {
        hpi: {
          duration: "Medium",
          evidence_quote: "Synthetic duration is Medium.",
          speaker: "Clinician",
        },
        past_medical_history: [
          {
            condition: "Synthetic prior condition",
            evidence_quote: "History of Synthetic prior condition.",
            speaker: "Clinician",
          },
        ],
        tests_mentioned: [
          {
            test: "Synthetic local test",
            evidence_quote: "Synthetic local test was reviewed.",
            speaker: "Clinician",
          },
        ],
      },
      quotes: [
        "Synthetic duration is Medium.",
        "History of Synthetic prior condition.",
        "Synthetic local test was reviewed.",
      ],
      expected: "rendered_verified",
      expectedPageCount: 1,
      minimumExpectedPages: 1,
    },
    {
      id: "legacy-date-rejection",
      source: unsupportedLegacyDateSource,
      conceptForField: () => "hpi.timing",
      entities: {},
      quotes: [],
      expected: "blocked_as_expected",
      expectedCompilerBlockerCodes: [
        "LEGACY_FORM_FIELD_PROFILE_UNSUPPORTED",
      ],
      expectedPageCount: 1,
      minimumExpectedPages: 1,
    },
    {
      id: "ordinary-placeholder-token",
      source: ordinaryPlaceholderSource,
      conceptForField: () => "chief_complaint",
      entities: {
        chief_complaint: {
          statement: "Synthetic Unicode finding — café & review <complete>",
          evidence_quote:
            "Synthetic Unicode finding — café & review <complete>",
          speaker: "Clinician",
        },
      },
      quotes: ["Synthetic Unicode finding — café & review <complete>"],
      expected: "rendered_verified",
      expectedPageCount: 1,
      minimumExpectedPages: 1,
    },
    {
      id: "tab-only-table-cell",
      source: async () =>
        normalizeDocx(await buildTabOnlyTableCellOfficeCorpusDocx()),
      conceptForField: () => "assessment",
      entities: {
        assessment_discussed: [
          {
            finding: "Synthetic tab-cell assessment.",
            evidence_quote: "Synthetic tab-cell assessment.",
            speaker: "Clinician",
          },
        ],
      },
      quotes: ["Synthetic tab-cell assessment."],
      expected: "rendered_verified",
      expectedPageCount: 1,
      minimumExpectedPages: 1,
    },
    {
      id: "unresolved-checkbox",
      source: unresolvedCheckboxSource,
      conceptForField: () => "allergy.substance",
      entities: {},
      quotes: [],
      expected: "blocked_as_expected",
      expectedBlockerCodes: [
        "CLINICALLY_MEANINGFUL_CHECKBOX_UNRESOLVED",
        "FIELD_NEEDS_CLINICIAN_INPUT",
      ],
      expectedPageCount: 1,
      minimumExpectedPages: 1,
    },
  ];
}

async function generateCase(
  outputRoot: string,
  testCase: CorpusCase,
): Promise<Record<string, unknown>> {
  const caseRoot = path.join(outputRoot, testCase.id);
  await mkdir(caseRoot, { recursive: true });
  const source = await testCase.source();
  const sourcePath = path.join(caseRoot, `${testCase.id}.source.docx`);
  await writeFile(sourcePath, source);
  const reopenedSource = await readFile(sourcePath);
  invariant(
    sha256(reopenedSource) === sha256(source),
    `${testCase.id}: source reopen mismatch.`,
  );
  const ir = compileTemplateDocx(reopenedSource);
  const compilerBlockerCodes = ir.unsupported.map((item) => item.code).sort();
  const expectedCompilerBlockerCodes = [
    ...(testCase.expectedCompilerBlockerCodes ?? []),
  ].sort();
  if (expectedCompilerBlockerCodes.length > 0) {
    invariant(
      testCase.expected === "blocked_as_expected",
      `${testCase.id}: compiler-blocked cases must be marked blocked_as_expected.`,
    );
    invariant(
      JSON.stringify(compilerBlockerCodes) ===
        JSON.stringify(expectedCompilerBlockerCodes),
      `${testCase.id}: compiler blocker census changed: ${compilerBlockerCodes.join(",")}.`,
    );
    await writeJson(path.join(caseRoot, "compiler-blockers.json"), {
      expectedCompilerBlockerCodes,
      blockers: ir.unsupported,
    });
    return {
      id: testCase.id,
      status: testCase.expected,
      sourcePath,
      outputPath: null,
      fieldCount: ir.fields.length,
      compilerBlockerCodes,
      validationCodes: [],
      sourceSha256: sha256(reopenedSource),
      outputSha256: null,
      sourceSizeBytes: reopenedSource.length,
      outputSizeBytes: null,
      expectedPageCount: testCase.expectedPageCount,
      minimumExpectedPages: testCase.minimumExpectedPages,
    };
  }
  invariant(
    compilerBlockerCodes.length === 0,
    `${testCase.id}: unexpected compiler blockers.`,
  );
  const mappings = mappingsFor(ir, testCase.conceptForField);
  const facts = projectEncounterFacts({
    mode: "text",
    contextText: testCase.quotes.join("\n"),
    entities: testCase.entities,
  });
  const certifiedFieldIds = ir.fields.map((field) => field.fieldId);
  const resolutions = resolveTemplateFields({
    fields: ir.fields,
    mappings,
    facts,
    certifiedFieldIds,
  });
  const validation = validateTemplateTwin({
    fields: ir.fields,
    mappings,
    facts,
    resolutions,
    tables: ir.tables,
    unsupported: ir.unsupported,
    certifiedFieldIds,
    now: "2026-07-16T00:00:00.000Z",
  });
  const validationCodes = validation.issues.map((issue) => issue.code).sort();
  await writeJson(path.join(caseRoot, "expected-values.json"), {
    syntheticOnly: true,
    fields: ir.fields.map((field) => {
      const resolution = resolutions.find(
        (candidate) => candidate.fieldId === field.fieldId,
      );
      invariant(resolution, `Missing resolution for ${field.fieldId}.`);
      return {
        fieldId: field.fieldId,
        kind: field.kind,
        status: resolution.status,
        value: resolution.value,
        selectedOptionOrdinal: resolution.selectedOptionOrdinal,
        sourceFactIds: resolution.sourceFactIds,
        evidenceAnchorIds: resolution.evidenceAnchorIds,
      };
    }),
  });
  await writeJson(
    path.join(caseRoot, "certified-bindings.json"),
    bindingManifest(ir),
  );
  await writeJson(path.join(caseRoot, "expected-layout.json"), {
    expectedPageCount: testCase.expectedPageCount,
    minimumExpectedPages: testCase.minimumExpectedPages,
    humanReviewRequired: true,
  });
  if (testCase.expected === "blocked_as_expected") {
    invariant(
      !validation.valid,
      `${testCase.id}: expected signing blocker was absent.`,
    );
    for (const code of testCase.expectedBlockerCodes ?? []) {
      invariant(
        validationCodes.includes(code),
        `${testCase.id}: expected blocker ${code} was absent.`,
      );
    }
    await writeJson(path.join(caseRoot, "output-readback.json"), {
      status: "not_run",
      reason:
        "Safety validation blocked rendering; no output was manufactured.",
    });
    await writeJson(path.join(caseRoot, "package-inspection.json"), {
      source: packageSummary(reopenedSource),
      output: null,
    });
    return {
      id: testCase.id,
      status: testCase.expected,
      sourcePath,
      outputPath: null,
      fieldCount: ir.fields.length,
      validationCodes,
      sourceSha256: sha256(reopenedSource),
      outputSha256: null,
      sourceSizeBytes: reopenedSource.length,
      outputSizeBytes: null,
      expectedPageCount: testCase.expectedPageCount,
      minimumExpectedPages: testCase.minimumExpectedPages,
    };
  }
  invariant(
    validation.valid,
    `${testCase.id}: validation failed: ${validationCodes.join(",")}`,
  );
  const rendered = await renderTemplateDocx({
    source: reopenedSource,
    ir,
    resolutions,
    validation,
  });
  invariant(
    rendered.verification.verified,
    `${testCase.id}: strict renderer verification failed.`,
  );
  const outputPath = path.join(caseRoot, `${testCase.id}.output.docx`);
  await writeFile(outputPath, rendered.document);
  const output = await readFile(outputPath);
  invariant(
    sha256(output) === rendered.outputSha256,
    `${testCase.id}: output reopen mismatch.`,
  );
  const readback = readbackTemplateDocxOutput({
    source: reopenedSource,
    output,
    ir,
    resolutions,
  });
  invariant(
    readback.every(
      (field) =>
        field.bindingEvidence?.status === "verified" && field.occurrences === 1,
    ),
    `${testCase.id}: independent readback did not prove field identity and occurrence.`,
  );
  await writeJson(path.join(caseRoot, "output-readback.json"), {
    verificationContractVersion:
      rendered.verification.verificationContractVersion,
    fields: readback,
  });
  await writeJson(
    path.join(caseRoot, "office-expected-manifest.json"),
    buildOfficeExpectedValueManifest({
      syntheticOnly: true,
      sourceDocxBytes: reopenedSource,
      rendererOutputDocxBytes: output,
      ir,
      resolutions,
    }),
  );
  await writeJson(path.join(caseRoot, "static-region-verification.json"), {
    verificationContractVersion:
      rendered.verification.verificationContractVersion,
    verified: rendered.verification.verified,
    staticRegionCheck: rendered.verification.staticRegionCheck,
    untouchedEntriesVerified: rendered.verification.untouchedEntriesVerified,
    modifiedPartsVerified: rendered.verification.modifiedPartsVerified,
  });
  await writeJson(path.join(caseRoot, "package-inspection.json"), {
    source: packageSummary(reopenedSource),
    output: packageSummary(output),
  });
  return {
    id: testCase.id,
    status: testCase.expected,
    sourcePath,
    outputPath,
    fieldCount: ir.fields.length,
    validationCodes,
    sourceSha256: sha256(reopenedSource),
    outputSha256: sha256(output),
    sourceSizeBytes: reopenedSource.length,
    outputSizeBytes: output.length,
    expectedPageCount: testCase.expectedPageCount,
    minimumExpectedPages: testCase.minimumExpectedPages,
  };
}

async function main(): Promise<void> {
  const options = parseOptions(process.argv.slice(2));
  const corpusRoot = path.join(options.outputRoot, "corpus");
  await mkdir(corpusRoot, { recursive: true });
  const results: Record<string, unknown>[] = [];
  for (const testCase of cases())
    results.push(await generateCase(corpusRoot, testCase));
  const manifest = {
    corpusVersion: "template-twin-human-gate-office-corpus/1.0.0",
    sourceCommit: options.sourceCommit,
    generatedAtIso: options.generatedAtIso,
    syntheticOnly: true,
    pipeline: [
      "compileTemplateDocx",
      "projectEncounterFacts",
      "resolveTemplateFields",
      "validateTemplateTwin",
      "renderTemplateDocx",
      "readbackTemplateDocxOutput",
    ],
    cases: results,
    totals: {
      cases: results.length,
      renderedVerified: results.filter(
        (result) => result.status === "rendered_verified",
      ).length,
      blockedAsExpected: results.filter(
        (result) => result.status === "blocked_as_expected",
      ).length,
      failed: 0,
    },
  };
  await writeJson(path.join(corpusRoot, "corpus-manifest.json"), manifest);
  process.stdout.write(
    `${JSON.stringify({ corpusRoot, totals: manifest.totals })}\n`,
  );
}

void main();
