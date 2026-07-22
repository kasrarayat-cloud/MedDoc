import {
  delimiterSystemSuffix,
  modelClient,
  wrapAsData,
  type ModelClient,
} from '@meddoc/ai';

import { inspectDocxPackage } from '@/lib/note-template-docx';
import {
  parseOrderedXml,
  visibleText,
} from '@/lib/note-template-docx/xml';
import { detectStructuredPhi } from '@/lib/note-template-parse/phi-gate';
import { docxToTextWithControls } from '@/lib/note-template-parse/docx-content-controls';
import { PhiScanSchema } from '@/lib/note-template-parse/note-template-schema';

const MAX_PHI_SCAN_CHARS = 50_000;
const MODEL = process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-opus-4-8';

const PHI_SCAN_SYSTEM = [
  'You are a conservative PHI gate for a reusable blank clinical DOCX template.',
  'Identify patient-specific values: patient names, dates tied to a patient, ages,',
  'identifiers, contact details, record numbers, unique clinical findings, or filled',
  'encounter values. Generic labels, blank placeholders, reusable clinical choices,',
  'normal boilerplate, and practice/provider letterhead are not patient PHI.',
  'Return `phiFields` using only the supplied part paths. If any text may be',
  'patient-specific and you cannot decide safely, set `anyUncertain` true.',
  delimiterSystemSuffix('transcript'),
].join('\n');

export class TemplateTwinPhiRejectedError extends Error {
  readonly code = 'TEMPLATE_TWIN_PHI_REJECTED';

  constructor() {
    super('The Word file may contain patient-specific information. Use a blank reusable template.');
    this.name = 'TemplateTwinPhiRejectedError';
  }
}

export class TemplateTwinPhiScanUnavailableError extends Error {
  readonly code = 'TEMPLATE_TWIN_PHI_SCAN_UNAVAILABLE';

  constructor(cause?: unknown) {
    super('The required privacy check could not complete. The file was not saved.', {
      cause,
    });
    this.name = 'TemplateTwinPhiScanUnavailableError';
  }
}

function scanPartNames(source: Uint8Array): Array<{ partName: string; text: string }> {
  const inspected = inspectDocxPackage(source);
  const partNames = [
    inspected.mainPartName,
    ...inspected.headerPartNames,
    ...inspected.footerPartNames,
    ...[...inspected.zip.entries.keys()].filter((name) =>
      /^word\/(?:footnotes|endnotes|comments)\.xml$/i.test(name),
    ),
  ];
  return [...new Set(partNames)]
    .sort((left, right) => left.localeCompare(right))
    .map((partName) => {
      const entry = inspected.zip.entries.get(partName);
      if (!entry) return { partName, text: '' };
      const tree = parseOrderedXml(entry.bytes, inspected.limits);
      return { partName, text: visibleText(tree).trim() };
    })
    .filter((part) => part.text.length > 0);
}

/**
 * Fail-closed privacy gate before an immutable source is stored. The original
 * bytes and extracted text remain in memory only; ModelClient records prompt
 * hashes/usage metadata rather than the text itself.
 */
export async function assertTemplateTwinSourcePhiFree(input: {
  source: Uint8Array;
  practiceId: string;
  userId: string;
  client?: Pick<ModelClient, 'complete'>;
}): Promise<void> {
  const parts = scanPartNames(input.source);
  // Deterministic structured-PHI pre-check on the FIXED document text only.
  // A dropdown's {{one of: …}} OPTION list is the doctor's enumerated FORMAT
  // (reused across every patient — e.g. a clinic-address option "…, CA 92604"),
  // never patient PHI, so the option lists are neutralised before the scan — the
  // SAME "options are format, not content" principle the note-format PHI gate
  // applies (phi-gate.ts stripChoiceOptions). The FIXED text around the markers,
  // where a pasted patient example would actually leak, is still fully scanned;
  // the LLM part-scan below independently covers the remaining OOXML parts.
  const { text: markerText } = await docxToTextWithControls(input.source);
  const scannableText = markerText.replace(/\{\{one of:[^}]*\}\}/g, '{{options}}');
  if (detectStructuredPhi(scannableText).length > 0) {
    throw new TemplateTwinPhiRejectedError();
  }

  // Scan the DOCUMENT BODY only, with dropdown {{one of}} option lists collapsed
  // ("options are format, not content") — the same scope the shipped note-format
  // PHI gate uses. Header/footer parts are practice/provider LETTERHEAD (name,
  // clinic address, phone), explicitly NOT patient PHI (PHI_SCAN_SYSTEM), and a
  // conservative model otherwise sets `anyUncertain` on a legitimate letterhead
  // and false-rejects the whole template. The body fixed text — where a pasted
  // patient example would actually leak — is still fully scanned by both the
  // deterministic detector above and this model scan.
  const isLetterhead = (partName: string) => /word\/(header|footer)\d*\.xml$/i.test(partName);
  const fields = Object.fromEntries(
    parts
      .filter((part) => !isLetterhead(part.partName))
      .map((part) => [
        part.partName,
        part.partName === 'word/document.xml' ? scannableText : part.text,
      ]),
  );
  const serialized = JSON.stringify(fields);
  if (serialized.length > MAX_PHI_SCAN_CHARS) {
    throw new TemplateTwinPhiRejectedError();
  }
  const wrapped = wrapAsData(serialized, 'transcript');
  if (wrapped.injectionAttemptDetected) {
    throw new TemplateTwinPhiRejectedError();
  }

  try {
    const scan = await (input.client ?? modelClient).complete({
      practiceId: input.practiceId,
      visitId: null,
      userId: input.userId,
      purpose: 'tm_template_phi_scan',
      provider: 'anthropic',
      model: MODEL,
      system: PHI_SCAN_SYSTEM,
      user: ['Reusable DOCX visible text by OOXML part:', wrapped.wrapped].join('\n'),
      schema: PhiScanSchema,
      maxTokens: 1024,
      temperature: 0,
      retryOnSchemaFail: true,
      useToolUse: {
        name: 'submit_template_twin_phi_scan',
        description:
          'Report any OOXML part containing patient-specific content and whether the scan is uncertain.',
      },
    });
    const knownParts = new Set(Object.keys(fields));
    if (
      scan.anyUncertain ||
      scan.phiFields.length > 0 ||
      scan.phiFields.some((partName) => !knownParts.has(partName))
    ) {
      throw new TemplateTwinPhiRejectedError();
    }
  } catch (error) {
    if (error instanceof TemplateTwinPhiRejectedError) throw error;
    throw new TemplateTwinPhiScanUnavailableError(error);
  }
}
