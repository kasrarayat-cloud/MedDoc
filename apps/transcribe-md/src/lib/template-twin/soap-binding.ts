import { canonicalSha256 } from './canonical';

export const TEMPLATE_TWIN_SOAP_BINDING_REVIEW_REASON =
  'The SOAP note changed after the Original Template DOCX was generated. Regenerate and review the document before signing.';

/**
 * Hashes the exact SOAP string through the same canonical JSON boundary used
 * by Template Twin manifests. Whitespace, punctuation, and section content
 * are significant: any physician-visible edit must produce a new digest.
 */
export function canonicalSoapSha256(soapFinal: string): string {
  return canonicalSha256({ soapFinal });
}

interface TemplateTwinInvalidationClient {
  templateTwinFillManifest: {
    updateMany(input: {
      where: {
        visitId: string;
        status: { not: 'SIGNED' };
        signedDecisionAt: null;
      };
      data: {
        status: 'NEEDS_REVIEW';
        reviewedAt: null;
        reviewedById: null;
        reviewedManifestVersion: null;
        reviewedManifestSha256: null;
      };
    }): Promise<{ count: number }>;
  };
}

/**
 * Must run in the same database transaction as a physician-visible SOAP
 * mutation. The immutable prior manifest/output remain available for audit,
 * but can no longer authorize signing or masquerade as current review data.
 */
export function invalidateTemplateTwinAfterSoapEdit(
  client: TemplateTwinInvalidationClient,
  visitId: string,
): Promise<{ count: number }> {
  return client.templateTwinFillManifest.updateMany({
    where: {
      visitId,
      status: { not: 'SIGNED' },
      signedDecisionAt: null,
    },
    data: {
      status: 'NEEDS_REVIEW',
      reviewedAt: null,
      reviewedById: null,
      reviewedManifestVersion: null,
      reviewedManifestSha256: null,
    },
  });
}
