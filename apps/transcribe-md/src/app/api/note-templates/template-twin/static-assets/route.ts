import { NextResponse } from 'next/server';
import { z } from 'zod';

import { AuthError } from '@/lib/auth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import {
  boundedMultipartFormData,
  isMultipartFile,
  isSameOriginTemplateTwinMutation,
  TemplateTwinMultipartError,
} from '@/lib/template-twin/request-security';
import { requireTemplateTwinStaticAssetAdmin } from '@/lib/template-twin/static-asset-admin';
import { configuredTemplateTwinLocalOcr } from '@/lib/template-twin/static-asset-ocr';
import {
  approveTemplateTwinStaticAsset,
  inspectTemplateTwinStaticAssetForReview,
  listTemplateTwinStaticAssetsForPractice,
  rejectTemplateTwinStaticAsset,
  revokeTemplateTwinStaticAsset,
  TemplateTwinStaticAssetError,
} from '@/lib/template-twin/static-assets';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 30;

const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_MULTIPART_BYTES = MAX_IMAGE_BYTES + 64 * 1024;
const SHA256 = /^[a-f0-9]{64}$/;
const PREVIEW_RECEIPT =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.[A-Za-z0-9_-]{43}$/;

const ActionSchema = z.enum(['inspect', 'approve', 'reject', 'revoke']);

function json(body: unknown, status = 200) {
  return NextResponse.json(body, {
    status,
    headers: {
      'Cache-Control': 'no-store, private',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'no-referrer',
    },
  });
}

function safeError(error: unknown): { status: number; message: string; code: string } {
  if (error instanceof AuthError) {
    return {
      status: error.code === 'UNAUTHENTICATED' ? 401 : 403,
      code: error.code,
      message: error.message,
    };
  }
  if (error instanceof TemplateTwinMultipartError) {
    return {
      status: error.code === 'MULTIPART_TOO_LARGE' ? 413 : 400,
      code: error.code,
      message:
        error.code === 'MULTIPART_TOO_LARGE'
          ? 'Reusable template images are limited to five megabytes.'
          : 'The image-review request was malformed.',
    };
  }
  if (error instanceof TemplateTwinStaticAssetError) {
    const unavailable =
      error.code === 'TT_STATIC_ASSET_OCR_UNAVAILABLE' ||
      error.code === 'TT_STATIC_ASSET_PRIVACY_SCAN_UNAVAILABLE' ||
      error.code === 'TT_STATIC_ASSET_PREVIEW_RECEIPT_UNAVAILABLE';
    const forbidden = error.code === 'TT_STATIC_ASSET_ADMIN_REQUIRED';
    return {
      status:
        unavailable
          ? 503
          : forbidden
            ? 403
            : error.code === 'TT_STATIC_ASSET_ROLLOUT_STALE' ||
                error.code === 'TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID'
              ? 409
              : 422,
      code: error.code,
      message: error.message,
    };
  }
  return {
    status: 500,
    code: 'TT_STATIC_ASSET_REQUEST_FAILED',
    message: 'The reusable-image safety review did not complete.',
  };
}

export async function GET() {
  try {
    const actor = await requireTemplateTwinStaticAssetAdmin();
    const [readiness, assets] = await Promise.all([
      configuredTemplateTwinLocalOcr(),
      listTemplateTwinStaticAssetsForPractice({ actor }),
    ]);
    return json({
      ok: true,
      readiness: readiness.ready
        ? {
            ready: true,
            code: readiness.code,
            message: readiness.message,
            engineVersion: readiness.engineVersion,
          }
        : readiness,
      acceptedMimeTypes: ['image/png'],
      maximumBytes: MAX_IMAGE_BYTES,
      imageBytesSentToExternalProviders: false,
      extractedTextPrivacyScanProvider: 'anthropic',
      assets,
    });
  } catch (error) {
    const safe = safeError(error);
    return json({ ok: false, error: safe.message, code: safe.code }, safe.status);
  }
}

export async function POST(request: Request) {
  if (!isSameOriginTemplateTwinMutation(request)) {
    return json(
      {
        ok: false,
        code: 'TT_STATIC_ASSET_SAME_ORIGIN_REQUIRED',
        error: 'The image-review request was not same-origin.',
      },
      403,
    );
  }
  const contentLength = Number(request.headers.get('content-length') ?? '0');
  if (Number.isFinite(contentLength) && contentLength > MAX_MULTIPART_BYTES) {
    return json(
      {
        ok: false,
        code: 'MULTIPART_TOO_LARGE',
        error: 'Reusable template images are limited to five megabytes.',
      },
      413,
    );
  }

  try {
    const actor = await requireTemplateTwinStaticAssetAdmin();
    const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, actor.userId);
    if (blocked) return blocked;
    const form = await boundedMultipartFormData(request, MAX_MULTIPART_BYTES);
    const action = ActionSchema.safeParse(form.get('action'));
    if (!action.success) {
      return json(
        {
          ok: false,
          code: 'TT_STATIC_ASSET_ACTION_INVALID',
          error: 'Choose inspect, approve, reject, or revoke.',
        },
        400,
      );
    }

    if (action.data === 'revoke') {
      const parsed = z
        .object({
          sha256: z.string().regex(SHA256),
          reason: z.string().trim().min(8).max(1000),
        })
        .safeParse({ sha256: form.get('sha256'), reason: form.get('reason') });
      if (!parsed.success) {
        return json(
          {
            ok: false,
            code: 'TT_STATIC_ASSET_REVOCATION_INVALID',
            error: 'Select the exact approved asset and provide a revocation reason.',
          },
          400,
        );
      }
      await revokeTemplateTwinStaticAsset({
        practiceId: actor.practiceId,
        sha256: parsed.data.sha256,
        reason: parsed.data.reason,
        actor,
      });
      return json({ ok: true, status: 'revoked' });
    }

    const readiness = await configuredTemplateTwinLocalOcr();
    if (!readiness.ready) {
      return json(
        { ok: false, code: readiness.code, error: readiness.message },
        503,
      );
    }
    const file = form.get('file');
    if (
      !isMultipartFile(file) ||
      file.type !== 'image/png' ||
      !file.name.toLowerCase().endsWith('.png')
    ) {
      return json(
        {
          ok: false,
          code: 'TT_STATIC_ASSET_TYPE_UNSUPPORTED',
          error: 'Choose one non-animated PNG image.',
        },
        415,
      );
    }
    if (file.size < 1 || file.size > MAX_IMAGE_BYTES) {
      return json(
        {
          ok: false,
          code: 'TT_STATIC_ASSET_RESOURCE_LIMIT',
          error: 'Reusable template images must be non-empty and no larger than five megabytes.',
        },
        413,
      );
    }
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (bytes.byteLength !== file.size) {
      return json(
        {
          ok: false,
          code: 'TT_STATIC_ASSET_INVALID_BYTES',
          error: 'The uploaded image was incomplete.',
        },
        400,
      );
    }

    if (action.data === 'inspect') {
      const inspected = await inspectTemplateTwinStaticAssetForReview({
        bytes,
        claimedMimeType: file.type,
        actor,
        ocr: readiness.ocr,
      });
      return json({
        ok: true,
        status: 'needs_attestation',
        evidence: inspected.evidence,
        previewReviewReceipt: inspected.previewReviewReceipt,
        previewReviewExpiresAtIso: inspected.previewReviewExpiresAtIso,
        previewDataUrl: `data:image/png;base64,${Buffer.from(
          inspected.previewBytes,
        ).toString('base64')}`,
      });
    }

    const common = z
      .object({
        expectedSha256: z.string().regex(SHA256),
        reason: z.string().trim().min(8).max(1000),
        previewReviewReceipt: z.string().regex(PREVIEW_RECEIPT).optional(),
      })
      .safeParse({
        expectedSha256: form.get('expectedSha256'),
        reason: form.get('reason'),
        previewReviewReceipt: form.get('previewReviewReceipt') ?? undefined,
      });
    if (!common.success) {
      return json(
        {
          ok: false,
          code: 'TT_STATIC_ASSET_DECISION_INVALID',
          error: 'Review the exact image and provide a decision reason.',
        },
        400,
      );
    }
    if (action.data === 'approve') {
      if (!common.data.previewReviewReceipt) {
        return json(
          {
            ok: false,
            code: 'TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID',
            error: 'Review the exact image preview before approving it.',
          },
          409,
        );
      }
      const binding = await approveTemplateTwinStaticAsset({
        bytes,
        claimedMimeType: file.type,
        actor,
        ocr: readiness.ocr,
        expectedSha256: common.data.expectedSha256,
        reason: common.data.reason,
        previewReviewReceipt: common.data.previewReviewReceipt,
        attestedReusableBlankAsset:
          form.get('attestedReusableBlankAsset') === 'true',
      });
      return json({ ok: true, status: 'approved', binding }, 201);
    }
    await rejectTemplateTwinStaticAsset({
      bytes,
      claimedMimeType: file.type,
      actor,
      ocr: readiness.ocr,
      expectedSha256: common.data.expectedSha256,
      reason: common.data.reason,
    });
    return json({ ok: true, status: 'rejected' });
  } catch (error) {
    const safe = safeError(error);
    return json({ ok: false, error: safe.message, code: safe.code }, safe.status);
  }
}
