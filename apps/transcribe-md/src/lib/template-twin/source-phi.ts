import {
  delimiterSystemSuffix,
  modelClient,
  wrapAsData,
  type ModelClient,
} from '@meddoc/ai';
import { createHash } from 'node:crypto';

import { inspectDocxPackage } from '@/lib/note-template-docx';
import {
  childrenOf,
  decodeXmlScalar,
  expandedXmlVisits,
  parseOrderedXml,
  tagOf,
  type OrderedXmlNode,
} from '@/lib/note-template-docx/xml';
import { detectStructuredPhi } from '@/lib/note-template-parse/phi-gate';
import { PhiScanSchema } from '@/lib/note-template-parse/note-template-schema';

import {
  type TemplateTwinSourcePhiScanEvidence,
} from './source-phi-evidence';

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

export class TemplateTwinSourcePrivacyUnsupportedError extends Error {
  readonly code = 'TEMPLATE_TWIN_SOURCE_PRIVACY_UNSUPPORTED';

  constructor() {
    super(
      'This Word file contains media, metadata, or package parts that safe alpha cannot inspect reliably. Remove them or use a supported blank DOCX.',
    );
    this.name = 'TemplateTwinSourcePrivacyUnsupportedError';
  }
}

const SAFE_ALPHA_XML_PART_RE = /^(?:\[Content_Types\]\.xml|_rels\/\.rels|docProps\/(?:app|core|custom)\.xml|word\/(?:document|styles|numbering|settings|webSettings|fontTable|footnotes|endnotes|comments|commentsExtended|people)\.xml|word\/(?:header|footer)[1-9][0-9]{0,3}\.xml|word\/_rels\/(?:document|header[1-9][0-9]{0,3}|footer[1-9][0-9]{0,3}|footnotes|endnotes|comments)\.xml\.rels|word\/theme\/theme[1-9][0-9]{0,3}\.xml)$/i;
const SAFE_ALPHA_MEDIA_PART_RE =
  /^word\/media\/image[1-9][0-9]{0,5}\.(?:png|jpe?g|gif|bmp|tiff?)$/i;
const APPROVED_ASSET_CONFIG_ENV =
  'TEMPLATE_TWIN_APPROVED_STATIC_ASSETS_BY_PRACTICE_JSON';
export type { TemplateTwinSourcePhiScanEvidence } from './source-phi-evidence';

interface ScannablePackageParts {
  readonly parts: Array<{
    partName: string;
    text: string;
    deterministicText: string;
  }>;
  readonly usedApprovedStaticAssetSha256: readonly string[];
}

function scanPartNames(
  source: Uint8Array,
  approvedStaticAssetSha256: ReadonlySet<string>,
): ScannablePackageParts {
  const inspected = inspectDocxPackage(source);
  const partNames: string[] = [];
  const usedApprovedStaticAssetSha256 = new Set<string>();
  for (const [partName, entry] of inspected.zip.entries) {
    if (/^customXml\//i.test(partName)) {
      throw new TemplateTwinSourcePrivacyUnsupportedError();
    }
    if (/^word\/media\//i.test(partName)) {
      // Do not preserve arbitrary media paths: a filename can itself contain
      // a patient identifier even when the byte digest belongs to an approved
      // logo. Word-authored raster assets use deterministic image<N> names.
      if (!SAFE_ALPHA_MEDIA_PART_RE.test(partName)) {
        throw new TemplateTwinSourcePrivacyUnsupportedError();
      }
      const sha256 = createHash('sha256').update(entry.bytes).digest('hex');
      if (!approvedStaticAssetSha256.has(sha256)) {
        throw new TemplateTwinSourcePrivacyUnsupportedError();
      }
      usedApprovedStaticAssetSha256.add(sha256);
      continue;
    }
    if (!SAFE_ALPHA_XML_PART_RE.test(partName)) {
      throw new TemplateTwinSourcePrivacyUnsupportedError();
    }
    if (partName.endsWith('.xml') || partName.endsWith('.rels')) {
      partNames.push(partName);
    }
  }
  const parts = [...new Set(partNames)]
    .sort((left, right) => left.localeCompare(right))
    .map((partName) => {
      const entry = inspected.zip.entries.get(partName);
      if (!entry) return { partName, text: '', deterministicText: '' };
      const tree = parseOrderedXml(entry.bytes, inspected.limits);
      return {
        partName,
        // Part names are preserved in every clone and may themselves contain
        // identifiers. Include the normalized name in both deterministic and
        // model privacy scans even though safe-alpha also restricts filenames.
        text: [partName, privacyRelevantXmlText(tree, false)].join('\n').trim(),
        deterministicText: [partName, privacyRelevantXmlText(tree, true)]
          .join('\n')
          .trim(),
      };
    })
    .filter((part) => part.text.length > 0);
  return {
    parts,
    usedApprovedStaticAssetSha256: [...usedApprovedStaticAssetSha256].sort(),
  };
}

function privacyRelevantXmlText(
  tree: OrderedXmlNode[],
  deterministic: boolean,
): string {
  const values: string[] = [];
  const visitByNode = new Map(
    expandedXmlVisits(tree).map((visit) => [visit.node, visit]),
  );
  const stack = [...tree].reverse();
  while (stack.length > 0) {
    const node = stack.pop()!;
    const tag = tagOf(node);
    if (tag === '#text') {
      values.push(decodeXmlScalar(String(node[tag] ?? '')));
      continue;
    }
    const visit = visitByNode.get(node);
    if (visit) {
      for (const attribute of visit.attributes) {
        // The parser has already bounded aggregate attribute count/size and
        // removed xmlns declarations. Scan every remaining value: a finite
        // name allowlist would let an unknown or foreign attribute preserve
        // patient data in every cloned output.
        if (
          !deterministic ||
          !(
            attribute.localName === 'storeItemID' &&
            /^\{[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\}$/i.test(
              attribute.value,
            )
          )
        ) {
          values.push(attribute.value);
        }
      }
    }
    const children = childrenOf(node);
    for (let index = children.length - 1; index >= 0; index -= 1) {
      stack.push(children[index]!);
    }
  }
  return values.join('\n');
}

function configuredApprovedStaticAssets(practiceId: string): Set<string> {
  const configured = process.env[APPROVED_ASSET_CONFIG_ENV];
  if (!configured) return new Set();
  try {
    const parsed = JSON.parse(configured) as unknown;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('configuration must be an object');
    }
    const values = (parsed as Record<string, unknown>)[practiceId];
    if (values === undefined) return new Set();
    if (
      !Array.isArray(values) ||
      values.length > 100 ||
      values.some(
        (value) =>
          typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value),
      )
    ) {
      throw new Error('practice asset digests are invalid');
    }
    return new Set(values);
  } catch (error) {
    throw new TemplateTwinPhiScanUnavailableError(error);
  }
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
}): Promise<TemplateTwinSourcePhiScanEvidence> {
  const approvedStaticAssets = configuredApprovedStaticAssets(input.practiceId);
  const { parts, usedApprovedStaticAssetSha256 } = scanPartNames(
    input.source,
    approvedStaticAssets,
  );
  const mainText =
    parts.find((part) => part.partName === 'word/document.xml')
      ?.deterministicText ?? '';
  if (
    detectStructuredPhi(mainText).length > 0 ||
    parts.some(
      (part) => detectStructuredPhi(part.deterministicText).length > 0,
    )
  ) {
    throw new TemplateTwinPhiRejectedError();
  }

  const fields = Object.fromEntries(parts.map((part) => [part.partName, part.text]));
  const serialized = JSON.stringify(fields);
  if (serialized.length > MAX_PHI_SCAN_CHARS) {
    throw new TemplateTwinSourcePrivacyUnsupportedError();
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
    const approvedStaticAssetDigests = [...approvedStaticAssets].sort();
    return {
      profileVersion: 'template-twin-source-phi-safe-alpha-v1',
      provider: 'anthropic',
      model: MODEL,
      scannedAt: new Date().toISOString(),
      scannedPartCount: parts.length,
      approvedStaticAssetPolicySha256: createHash('sha256')
        .update(
          JSON.stringify({
            practiceId: input.practiceId,
            sha256: approvedStaticAssetDigests,
          }),
        )
        .digest('hex'),
      approvedStaticAssetCount: approvedStaticAssetDigests.length,
      approvedStaticAssetUsedCount: usedApprovedStaticAssetSha256.length,
      approvedStaticAssetUsageSha256: createHash('sha256')
        .update(JSON.stringify(usedApprovedStaticAssetSha256))
        .digest('hex'),
    };
  } catch (error) {
    if (error instanceof TemplateTwinPhiRejectedError) throw error;
    throw new TemplateTwinPhiScanUnavailableError(error);
  }
}
