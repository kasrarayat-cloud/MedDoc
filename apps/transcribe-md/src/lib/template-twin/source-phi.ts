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
import {
  TemplateTwinAuxiliaryPartUnsupportedError,
  inspectStandardWordAuxiliaryParts,
  isStandardWordAuxiliaryPartName,
} from './auxiliary-parts';
import {
  TemplateTwinStaticAssetError,
  assertTemplateTwinStaticAssetPackageMatchesApproval,
  resolveApprovedTemplateTwinStaticAssets,
  type TemplateTwinStaticAssetApprovalBinding,
} from './static-assets';

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
  /^word\/media\/image[1-9][0-9]{0,5}\.png$/i;
export type { TemplateTwinSourcePhiScanEvidence } from './source-phi-evidence';

interface ScannablePackageParts {
  readonly parts: Array<{
    partName: string;
    text: string;
    deterministicText: string;
  }>;
  readonly staticAssetApprovalBindings: readonly TemplateTwinStaticAssetApprovalBinding[];
  readonly auxiliaryPartCount: number;
  readonly auxiliaryPartManifestSha256: string;
}

async function scanPartNames(
  source: Uint8Array,
  practiceId: string,
  approvalResolver: (
    practiceId: string,
    sha256: readonly string[],
  ) => Promise<readonly TemplateTwinStaticAssetApprovalBinding[]>,
): Promise<ScannablePackageParts> {
  const inspected = inspectDocxPackage(source);
  let auxiliary;
  try {
    auxiliary = inspectStandardWordAuxiliaryParts(inspected);
  } catch (error) {
    if (error instanceof TemplateTwinAuxiliaryPartUnsupportedError) {
      throw new TemplateTwinSourcePrivacyUnsupportedError();
    }
    throw error;
  }
  const partNames: string[] = [];
  const mediaSha256 = new Set<string>();
  const mediaBytesBySha256 = new Map<string, Uint8Array>();
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
      if (inspected.contentTypes.get(partName) !== 'image/png') {
        throw new TemplateTwinSourcePrivacyUnsupportedError();
      }
      const sha256 = createHash('sha256').update(entry.bytes).digest('hex');
      mediaSha256.add(sha256);
      mediaBytesBySha256.set(sha256, entry.bytes);
      continue;
    }
    if (
      !SAFE_ALPHA_XML_PART_RE.test(partName) &&
      !isStandardWordAuxiliaryPartName(partName)
    ) {
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
  let staticAssetApprovalBindings: readonly TemplateTwinStaticAssetApprovalBinding[];
  try {
    staticAssetApprovalBindings = await approvalResolver(
      practiceId,
      [...mediaSha256].sort(),
    );
  } catch (error) {
    if (error instanceof TemplateTwinStaticAssetError) {
      throw new TemplateTwinSourcePrivacyUnsupportedError();
    }
    throw new TemplateTwinPhiScanUnavailableError(error);
  }
  const approvedDigests = staticAssetApprovalBindings
    .map((binding) => binding.sha256)
    .sort();
  const requiredDigests = [...mediaSha256].sort();
  if (
    approvedDigests.length !== requiredDigests.length ||
    approvedDigests.some((value, index) => value !== requiredDigests[index])
  ) {
    throw new TemplateTwinSourcePrivacyUnsupportedError();
  }
  for (const binding of staticAssetApprovalBindings) {
    const bytes = mediaBytesBySha256.get(binding.sha256);
    if (!bytes) throw new TemplateTwinSourcePrivacyUnsupportedError();
    try {
      assertTemplateTwinStaticAssetPackageMatchesApproval({ bytes, binding });
    } catch (error) {
      if (error instanceof TemplateTwinStaticAssetError) {
        throw new TemplateTwinSourcePrivacyUnsupportedError();
      }
      throw error;
    }
  }
  return {
    parts,
    staticAssetApprovalBindings: [...staticAssetApprovalBindings].sort(
      (left, right) => left.sha256.localeCompare(right.sha256),
    ),
    auxiliaryPartCount: auxiliary.parts.length,
    auxiliaryPartManifestSha256: auxiliary.manifestSha256,
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
  staticAssetApprovalResolver?: (
    practiceId: string,
    sha256: readonly string[],
  ) => Promise<readonly TemplateTwinStaticAssetApprovalBinding[]>;
}): Promise<TemplateTwinSourcePhiScanEvidence> {
  const {
    parts,
    staticAssetApprovalBindings,
    auxiliaryPartCount,
    auxiliaryPartManifestSha256,
  } = await scanPartNames(
    input.source,
    input.practiceId,
    input.staticAssetApprovalResolver ??
      ((practiceId, sha256) =>
        resolveApprovedTemplateTwinStaticAssets({ practiceId, sha256 })),
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
    const approvedStaticAssetDigests = staticAssetApprovalBindings.map(
      (binding) => binding.sha256,
    );
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
            bindings: staticAssetApprovalBindings,
          }),
        )
        .digest('hex'),
      approvedStaticAssetCount: approvedStaticAssetDigests.length,
      approvedStaticAssetUsedCount: staticAssetApprovalBindings.length,
      approvedStaticAssetUsageSha256: createHash('sha256')
        .update(JSON.stringify(approvedStaticAssetDigests))
        .digest('hex'),
      staticAssetApprovalBindings: [...staticAssetApprovalBindings],
      auxiliaryInspectionProfileVersion:
        'template-twin-word-auxiliary-safe-v1',
      auxiliaryPartCount,
      auxiliaryPartManifestSha256,
    };
  } catch (error) {
    if (error instanceof TemplateTwinPhiRejectedError) throw error;
    throw new TemplateTwinPhiScanUnavailableError(error);
  }
}
