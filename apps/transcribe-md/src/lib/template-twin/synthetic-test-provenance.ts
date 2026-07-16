import { canonicalSha256 } from './canonical';

const SHA256 = /^[a-f0-9]{64}$/;

export interface TemplateTwinSyntheticTestProvenanceInput {
  compiledVersionId: string;
  latestSyntheticTestManifest: unknown;
  latestTestMappingsSha256: string | null;
  latestTestFieldIntentsSha256?: string | null;
  latestTestOutputObjectKey: string | null;
  latestTestOutputVersionId: string | null;
  latestTestOutputEtag: string | null;
  latestTestOutputSha256: string | null;
  latestTestStaticContentSha256: string | null;
  latestTestRoundTrip: unknown;
  latestTestVerifiedAt: Date | null;
}

/**
 * Opaque acknowledgement boundary for the exact synthetic proof shown to the
 * physician. The hash deliberately covers the evidence manifest, rendered
 * artifact identity, independent readback proof, and verification timestamp.
 * Re-running or replacing a test therefore invalidates every prior browser
 * acknowledgement even when the semantic mappings did not change.
 */
export function templateTwinSyntheticTestProvenanceSha256(
  input: TemplateTwinSyntheticTestProvenanceInput,
): string | null {
  if (
    !input.compiledVersionId ||
    input.latestSyntheticTestManifest === null ||
    input.latestSyntheticTestManifest === undefined ||
    !input.latestTestMappingsSha256 ||
    !SHA256.test(input.latestTestMappingsSha256) ||
    !input.latestTestFieldIntentsSha256 ||
    !SHA256.test(input.latestTestFieldIntentsSha256) ||
    !input.latestTestOutputObjectKey ||
    !input.latestTestOutputVersionId?.trim() ||
    !input.latestTestOutputEtag?.trim() ||
    !input.latestTestOutputSha256 ||
    !SHA256.test(input.latestTestOutputSha256) ||
    !input.latestTestStaticContentSha256 ||
    !SHA256.test(input.latestTestStaticContentSha256) ||
    input.latestTestRoundTrip === null ||
    input.latestTestRoundTrip === undefined ||
    !(input.latestTestVerifiedAt instanceof Date) ||
    !Number.isFinite(input.latestTestVerifiedAt.valueOf())
  ) {
    return null;
  }

  return canonicalSha256({
    compiledVersionId: input.compiledVersionId,
    mappingsSha256: input.latestTestMappingsSha256,
    fieldIntentsSha256: input.latestTestFieldIntentsSha256,
    manifestSha256: canonicalSha256(input.latestSyntheticTestManifest),
    outputObjectKey: input.latestTestOutputObjectKey,
    outputVersionId: input.latestTestOutputVersionId,
    outputEtag: input.latestTestOutputEtag,
    outputSha256: input.latestTestOutputSha256,
    staticContentSha256: input.latestTestStaticContentSha256,
    roundTripSha256: canonicalSha256(input.latestTestRoundTrip),
    verifiedAt: input.latestTestVerifiedAt.toISOString(),
  });
}
