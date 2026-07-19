import type { ImgHTMLAttributes } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('next/image', () => ({
  default: (
    props: ImgHTMLAttributes<HTMLImageElement> & { unoptimized?: boolean },
  ) => {
    const { unoptimized, ...imageProps } = props;
    void unoptimized;
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img {...imageProps} alt={imageProps.alt ?? ''} />
    );
  },
}));

import { StaticAssetReviewWorkspace } from '../static-asset-review-workspace';

const SHA = 'a'.repeat(64);
const PREVIEW_RECEIPT =
  '123e4567-e89b-42d3-a456-426614174000.' + 'A'.repeat(43);
const INDEX = {
  ok: true,
  readiness: {
    ready: true,
    code: 'TT_STATIC_ASSET_LOCAL_OCR_READY',
    message: 'Bounded local image-text inspection is available.',
    engineVersion: 'synthetic-local-ocr/1.0',
  },
  maximumBytes: 5 * 1024 * 1024,
  imageBytesSentToExternalProviders: false,
  extractedTextPrivacyScanProvider: 'anthropic',
  assets: [
    {
      sha256: SHA,
      status: 'APPROVED',
      mimeType: 'image/png',
      width: 320,
      height: 80,
      sizeBytes: 2048,
      scannerVersion: 'template-twin-static-png/1.0.0',
      ocrEngineVersion: 'synthetic-local-ocr/1.0',
      decisionVersion: 1,
      createdAtIso: '2026-07-16T00:00:00.000Z',
      updatedAtIso: '2026-07-16T00:00:00.000Z',
    },
  ],
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('practice-admin static image review workspace', () => {
  it('requires inspection, exact-byte attestation, and a reason before approval', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(INDEX))
      .mockResolvedValueOnce(
        jsonResponse({
          ok: true,
          status: 'needs_attestation',
          evidence: {
            sha256: SHA,
            mimeType: 'image/png',
            width: 320,
            height: 80,
            sizeBytes: 2048,
            scannerVersion: 'template-twin-static-png/1.0.0',
            ocrEngineVersion: 'synthetic-local-ocr/1.0',
            privacyEvidenceSha256: 'b'.repeat(64),
          },
          previewDataUrl: 'data:image/png;base64,iVBORw0KGgo=',
          previewReviewReceipt: PREVIEW_RECEIPT,
          previewReviewExpiresAtIso: '2026-07-16T00:15:00.000Z',
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ ok: true, status: 'approved', binding: { sha256: SHA } }, 201),
      )
      .mockResolvedValueOnce(jsonResponse(INDEX));
    vi.stubGlobal('fetch', fetchMock);
    render(<StaticAssetReviewWorkspace />);

    await screen.findByText('Bounded local image-text inspection is available. Engine: synthetic-local-ocr/1.0.');
    const file = new File([Uint8Array.from([137, 80, 78, 71])], 'synthetic-logo.png', {
      type: 'image/png',
    });
    fireEvent.change(screen.getByLabelText('Practice image'), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Inspect image' }));

    await screen.findByRole('img', {
      name: 'Reviewed reusable practice image preview',
    });
    const approve = screen.getByRole('button', {
      name: 'Approve for this practice',
    });
    expect(approve).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Practice decision reason'), {
      target: { value: 'Reusable synthetic blank practice logo.' },
    });
    expect(approve).toBeDisabled();
    fireEvent.click(
      screen.getByRole('checkbox', {
        name: /I attest that this exact image is a reusable blank practice asset/,
      }),
    );
    expect(approve).toBeEnabled();
    fireEvent.click(approve);

    await screen.findByText(
      'The exact image bytes are approved for new Template Twin versions in this practice.',
    );
    expect(fetchMock).toHaveBeenCalledTimes(4);
    const inspectForm = fetchMock.mock.calls[1]?.[1]?.body as FormData;
    expect(inspectForm.get('action')).toBe('inspect');
    expect(inspectForm.get('file')).toBe(file);
    const approvalForm = fetchMock.mock.calls[2]?.[1]?.body as FormData;
    expect(approvalForm.get('expectedSha256')).toBe(SHA);
    expect(approvalForm.get('previewReviewReceipt')).toBe(PREVIEW_RECEIPT);
    expect(approvalForm.get('attestedReusableBlankAsset')).toBe('true');
    expect(approvalForm.get('reason')).toBe(
      'Reusable synthetic blank practice logo.',
    );
    expect(document.body.textContent).not.toContain(PREVIEW_RECEIPT);
  });

  it('does not expose approval controls when the server omits preview proof', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(INDEX))
      .mockResolvedValueOnce(
        jsonResponse({
          ok: true,
          status: 'needs_attestation',
          evidence: {
            sha256: SHA,
            mimeType: 'image/png',
            width: 320,
            height: 80,
            sizeBytes: 2048,
            scannerVersion: 'template-twin-static-png/1.0.0',
            ocrEngineVersion: 'synthetic-local-ocr/1.0',
            privacyEvidenceSha256: 'b'.repeat(64),
          },
          previewDataUrl: 'data:image/png;base64,iVBORw0KGgo=',
        }),
      );
    vi.stubGlobal('fetch', fetchMock);
    render(<StaticAssetReviewWorkspace />);
    await screen.findByText(/Bounded local image-text inspection is available/);
    const file = new File([Uint8Array.from([137, 80, 78, 71])], 'synthetic-logo.png', {
      type: 'image/png',
    });
    fireEvent.change(screen.getByLabelText('Practice image'), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Inspect image' }));
    await screen.findByRole('alert');
    expect(screen.queryByRole('button', { name: 'Approve for this practice' })).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('keeps image selection blocked when bounded local OCR is unavailable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          ...INDEX,
          readiness: {
            ready: false,
            code: 'TT_STATIC_ASSET_LOCAL_OCR_NOT_CONFIGURED',
            message: 'Bounded local image-text inspection is not configured.',
          },
        }),
      ),
    );
    render(<StaticAssetReviewWorkspace />);

    await screen.findByText('Bounded local image-text inspection is not configured.');
    expect(screen.getByLabelText('Practice image')).toBeDisabled();
    expect(screen.getByText('Blocked')).toBeInTheDocument();
  });

  it('revokes an approved digest without requiring image bytes or OCR', async () => {
    const unavailableIndex = {
      ...INDEX,
      readiness: {
        ready: false,
        code: 'TT_STATIC_ASSET_LOCAL_OCR_UNAVAILABLE',
        message: 'Local OCR is temporarily unavailable.',
      },
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(unavailableIndex))
      .mockResolvedValueOnce(jsonResponse({ ok: true, status: 'revoked' }))
      .mockResolvedValueOnce(
        jsonResponse({
          ...unavailableIndex,
          assets: [{ ...INDEX.assets[0], status: 'REVOKED' }],
        }),
      );
    vi.stubGlobal('fetch', fetchMock);
    render(<StaticAssetReviewWorkspace />);

    await screen.findByRole('button', { name: 'Revoke for new templates' });
    fireEvent.click(screen.getByRole('button', { name: 'Revoke for new templates' }));
    fireEvent.change(
      screen.getByLabelText('Why should new templates stop using this image?'),
      { target: { value: 'Synthetic logo was retired by the practice.' } },
    );
    fireEvent.click(screen.getByRole('button', { name: 'Confirm revocation' }));

    await screen.findByText(/Approval was revoked/);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const revokeForm = fetchMock.mock.calls[1]?.[1]?.body as FormData;
    expect(revokeForm.get('action')).toBe('revoke');
    expect(revokeForm.get('sha256')).toBe(SHA);
    expect(revokeForm.get('file')).toBeNull();
  });
});
