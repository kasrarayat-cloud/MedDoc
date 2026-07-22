// ============================================================================
// Native Template Twin DOCX export — serve the doctor's OWN document.
// ----------------------------------------------------------------------------
// When a visit was filled against a Template Twin native template, the fill
// engine has already rendered the ORIGINAL .docx with the resolved field values
// and roundtrip-VERIFIED it, storing the bytes under the tenant's private prefix
// (fill manifest outputObjectKey). Export just serves those verified bytes — the
// doctor gets their exact template back, formatting preserved.
//
// Returns null when the visit is not a twin visit or has no verified native
// output; the caller falls back to the QuillMD-styled generateVisitDocx. The
// sign route is NOT involved. Ownership is enforced here (the manifest's visit
// must belong to userId) on top of the route's own ownership gate.
// ============================================================================

import prisma from '@meddoc/db';

import {
  createTemplateTwinArtifactStore,
  type TemplateTwinArtifactStore,
} from './storage';

export interface NativeTemplateExport {
  bytes: Buffer;
  outputSha256: string;
  roundTripVerified: boolean;
}

export async function loadNativeTemplateDocxForVisit(
  visitId: string,
  userId: string,
  deps?: { storage?: TemplateTwinArtifactStore },
): Promise<NativeTemplateExport | null> {
  const manifest = await prisma.templateTwinFillManifest.findFirst({
    where: {
      visitId,
      // Ownership: the fill manifest's visit must belong to the requester.
      visit: { userId, deletedAt: null },
      status: 'VERIFIED',
      roundTripVerified: true,
      outputObjectKey: { not: null },
    },
    select: {
      practiceId: true,
      outputObjectKey: true,
      outputSha256: true,
      outputSizeBytes: true,
    },
  });
  if (
    !manifest ||
    !manifest.outputObjectKey ||
    !manifest.outputSha256 ||
    manifest.outputSizeBytes == null
  ) {
    return null;
  }

  const storage = deps?.storage ?? createTemplateTwinArtifactStore();
  const bytes = await storage.readOutputArtifact({
    practiceId: manifest.practiceId,
    objectKey: manifest.outputObjectKey,
    expectedSha256: manifest.outputSha256,
    expectedSizeBytes: manifest.outputSizeBytes,
  });
  return { bytes, outputSha256: manifest.outputSha256, roundTripVerified: true };
}
