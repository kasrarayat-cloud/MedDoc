'use client';

import Image from 'next/image';
import { useCallback, useEffect, useRef, useState } from 'react';

import styles from './static-asset-review.module.css';

const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const ENDPOINT = '/api/note-templates/template-twin/static-assets';

interface Readiness {
  ready: boolean;
  code: string;
  message: string;
  engineVersion?: string;
}

interface AssetListItem {
  sha256: string;
  status: 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED' | 'REVOKED';
  mimeType: 'image/png';
  width: number;
  height: number;
  sizeBytes: number;
  scannerVersion: string;
  ocrEngineVersion: string;
  decisionVersion: number;
  createdAtIso: string;
  updatedAtIso: string;
}

interface InspectionEvidence {
  sha256: string;
  mimeType: 'image/png';
  width: number;
  height: number;
  sizeBytes: number;
  scannerVersion: string;
  ocrEngineVersion: string;
  privacyEvidenceSha256: string;
}

interface Inspection {
  evidence: InspectionEvidence;
  previewDataUrl: string;
  /** Opaque server proof held in memory only; never displayed or persisted. */
  previewReviewReceipt: string;
  previewReviewExpiresAtIso: string;
}

interface IndexResponse {
  ok: true;
  readiness: Readiness;
  maximumBytes: number;
  imageBytesSentToExternalProviders: false;
  extractedTextPrivacyScanProvider: string;
  assets: AssetListItem[];
}

interface ErrorResponse {
  ok: false;
  error?: string;
  code?: string;
}

function humanBytes(value: number): string {
  if (value < 1024) return `${value} bytes`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatStatus(status: AssetListItem['status']): string {
  return status.toLowerCase().replaceAll('_', ' ');
}

function statusClass(status: AssetListItem['status']): string {
  if (status === 'APPROVED') return styles.statusApproved;
  if (status === 'REJECTED') return styles.statusRejected;
  if (status === 'REVOKED') return styles.statusRevoked;
  return '';
}

async function responseBody(response: Response): Promise<Record<string, unknown>> {
  try {
    return (await response.json()) as Record<string, unknown>;
  } catch {
    return {};
  }
}

export function StaticAssetReviewWorkspace() {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [assets, setAssets] = useState<AssetListItem[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [reason, setReason] = useState('');
  const [attested, setAttested] = useState(false);
  const [busy, setBusy] = useState<string | null>('loading');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [revokingSha, setRevokingSha] = useState<string | null>(null);
  const [revokeReason, setRevokeReason] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadIndex = useCallback(async (signal?: AbortSignal) => {
    const response = await fetch(ENDPOINT, {
      method: 'GET',
      credentials: 'same-origin',
      cache: 'no-store',
      signal,
    });
    const payload = (await responseBody(response)) as unknown as
      | IndexResponse
      | ErrorResponse;
    if (!response.ok || !payload.ok) {
      throw new Error(
        ('error' in payload && payload.error) ||
          'Reusable image review is unavailable.',
      );
    }
    setReadiness(payload.readiness);
    setAssets(payload.assets);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      loadIndex(controller.signal)
        .catch((caught: unknown) => {
          if (controller.signal.aborted) return;
          setError(
            caught instanceof Error
              ? caught.message
              : 'Could not load image review.',
          );
        })
        .finally(() => {
          if (!controller.signal.aborted) setBusy(null);
        });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [loadIndex]);

  function resetCandidate(): void {
    setFile(null);
    setInspection(null);
    setReason('');
    setAttested(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function chooseFile(event: React.ChangeEvent<HTMLInputElement>): void {
    const selected = event.target.files?.[0] ?? null;
    setError('');
    setMessage('');
    setInspection(null);
    setReason('');
    setAttested(false);
    if (!selected) {
      setFile(null);
      return;
    }
    if (
      selected.type !== 'image/png' ||
      !selected.name.toLowerCase().endsWith('.png')
    ) {
      event.target.value = '';
      setFile(null);
      setError('Choose one non-animated PNG image.');
      return;
    }
    if (selected.size < 1 || selected.size > MAX_IMAGE_BYTES) {
      event.target.value = '';
      setFile(null);
      setError('The PNG must be non-empty and no larger than five megabytes.');
      return;
    }
    setFile(selected);
  }

  async function post(form: FormData): Promise<Record<string, unknown>> {
    const response = await fetch(ENDPOINT, {
      method: 'POST',
      credentials: 'same-origin',
      body: form,
    });
    const payload = await responseBody(response);
    if (!response.ok || payload.ok !== true) {
      throw new Error(
        (typeof payload.error === 'string' && payload.error) ||
          'The reusable-image review did not complete.',
      );
    }
    return payload;
  }

  async function inspectCandidate(): Promise<void> {
    if (!file || !readiness?.ready) return;
    setBusy('inspect');
    setError('');
    setMessage('');
    try {
      const form = new FormData();
      form.set('action', 'inspect');
      form.set('file', file);
      const payload = await post(form);
      if (
        typeof payload.previewReviewReceipt !== 'string' ||
        typeof payload.previewReviewExpiresAtIso !== 'string'
      ) {
        throw new Error(
          'The reviewed-image proof was not issued. Inspect the image again.',
        );
      }
      setInspection({
        evidence: payload.evidence as unknown as InspectionEvidence,
        previewDataUrl: String(payload.previewDataUrl),
        previewReviewReceipt: payload.previewReviewReceipt,
        previewReviewExpiresAtIso: payload.previewReviewExpiresAtIso,
      });
      setMessage(
        'Safety inspection passed. Review the exact image and its practice-wide intent before deciding.',
      );
    } catch (caught) {
      setInspection(null);
      setError(caught instanceof Error ? caught.message : 'Image inspection failed.');
    } finally {
      setBusy(null);
    }
  }

  async function decide(action: 'approve' | 'reject'): Promise<void> {
    if (!file || !inspection) return;
    setBusy(action);
    setError('');
    setMessage('');
    try {
      const form = new FormData();
      form.set('action', action);
      form.set('file', file);
      form.set('expectedSha256', inspection.evidence.sha256);
      form.set('reason', reason);
      if (action === 'approve') {
        form.set('previewReviewReceipt', inspection.previewReviewReceipt);
        form.set('attestedReusableBlankAsset', String(attested));
      }
      await post(form);
      resetCandidate();
      setMessage(
        action === 'approve'
          ? 'The exact image bytes are approved for new Template Twin versions in this practice.'
          : 'The exact image bytes were rejected and remain unavailable to templates.',
      );
      try {
        await loadIndex();
      } catch {
        setError(
          'The decision was saved, but the practice image list could not refresh. Reload this page to see the current record.',
        );
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The decision was not saved.');
    } finally {
      setBusy(null);
    }
  }

  async function revoke(sha256: string): Promise<void> {
    setBusy(`revoke:${sha256}`);
    setError('');
    setMessage('');
    try {
      const form = new FormData();
      form.set('action', 'revoke');
      form.set('sha256', sha256);
      form.set('reason', revokeReason);
      await post(form);
      setRevokingSha(null);
      setRevokeReason('');
      setMessage(
        'Approval was revoked. New template certifications cannot use these image bytes; historical signed documents are unchanged.',
      );
      try {
        await loadIndex();
      } catch {
        setError(
          'Revocation was saved, but the practice image list could not refresh. Reload this page to see the current record.',
        );
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Revocation was not saved.');
    } finally {
      setBusy(null);
    }
  }

  const ready = readiness?.ready === true;
  const decisionReady = reason.trim().length >= 8;

  return (
    <div className={styles.stack}>
      {error && (
        <div className={styles.error} role="alert">
          {error}
        </div>
      )}
      {message && (
        <div className={styles.message} role="status">
          {message}
        </div>
      )}

      <section className={styles.card} aria-labelledby="asset-readiness-heading">
        <div className={styles.cardHeader}>
          <div>
            <h2 className={styles.cardTitle} id="asset-readiness-heading">
              Safety inspection readiness
            </h2>
            <p className={styles.cardCopy}>
              Image bytes stay inside QuillMD. Bounded local OCR reads visible
              text; only extracted text and metadata are sent through the
              configured privacy scan.
            </p>
          </div>
          <span
            className={`${styles.status} ${
              ready ? styles.statusReady : styles.statusBlocked
            }`}
          >
            {busy === 'loading' ? 'Checking' : ready ? 'Ready' : 'Blocked'}
          </span>
        </div>
        {readiness && (
          <p className={styles.cardCopy} role={ready ? undefined : 'alert'}>
            {readiness.message}
            {readiness.engineVersion ? ` Engine: ${readiness.engineVersion}.` : ''}
          </p>
        )}
      </section>

      <section className={styles.card} aria-labelledby="asset-review-heading">
        <div className={styles.cardHeader}>
          <div>
            <h2 className={styles.cardTitle} id="asset-review-heading">
              Review a reusable practice image
            </h2>
            <p className={styles.cardCopy}>
              Use a blank practice mark or logo only. Do not choose screenshots,
              patient images, signatures, forms completed for a patient, or
              anything encounter-specific.
            </p>
          </div>
          <span className={styles.status}>PNG · 5 MB max</span>
        </div>

        <div className={styles.formGrid}>
          <div>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="template-twin-static-image">
                Practice image
              </label>
              <input
                ref={fileInputRef}
                className={styles.input}
                id="template-twin-static-image"
                type="file"
                accept="image/png,.png"
                disabled={!ready || busy !== null}
                onChange={chooseFile}
              />
              <p className={styles.helper}>
                A changed byte creates a different image identity and requires a
                new review.
              </p>
            </div>
            <div className={styles.actions}>
              <button
                className={styles.button}
                type="button"
                disabled={!file || !ready || busy !== null}
                onClick={() => void inspectCandidate()}
              >
                {busy === 'inspect' ? 'Inspecting…' : 'Inspect image'}
              </button>
              {file && (
                <button
                  className={styles.secondaryButton}
                  type="button"
                  disabled={busy !== null}
                  onClick={resetCandidate}
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          <div className={styles.previewFrame} aria-live="polite">
            {inspection ? (
              <Image
                alt="Reviewed reusable practice image preview"
                className={styles.previewImage}
                src={inspection.previewDataUrl}
                width={inspection.evidence.width}
                height={inspection.evidence.height}
                unoptimized
              />
            ) : (
              <p className={styles.helper}>
                A preview appears only after all automated checks pass.
              </p>
            )}
          </div>
        </div>

        {inspection && (
          <div>
            <dl className={styles.evidenceList}>
              <div className={styles.evidenceItem}>
                <dt>Exact image</dt>
                <dd>{inspection.evidence.sha256.slice(0, 12)}…</dd>
              </div>
              <div className={styles.evidenceItem}>
                <dt>Dimensions</dt>
                <dd>
                  {inspection.evidence.width} × {inspection.evidence.height}
                </dd>
              </div>
              <div className={styles.evidenceItem}>
                <dt>File size</dt>
                <dd>{humanBytes(inspection.evidence.sizeBytes)}</dd>
              </div>
              <div className={styles.evidenceItem}>
                <dt>Privacy evidence</dt>
                <dd>Complete · {inspection.evidence.privacyEvidenceSha256.slice(0, 12)}…</dd>
              </div>
            </dl>
            <details className={styles.advanced}>
              <summary>Advanced inspection identity</summary>
              <div className={styles.digest}>
                SHA-256 {inspection.evidence.sha256}
              </div>
              <div>Scanner {inspection.evidence.scannerVersion}</div>
              <div>Local OCR {inspection.evidence.ocrEngineVersion}</div>
              <div className={styles.digest}>
                Privacy evidence {inspection.evidence.privacyEvidenceSha256}
              </div>
            </details>

            <div className={styles.field} style={{ marginTop: 14 }}>
              <label className={styles.label} htmlFor="static-asset-reason">
                Practice decision reason
              </label>
              <textarea
                className={styles.textarea}
                id="static-asset-reason"
                maxLength={1000}
                value={reason}
                disabled={busy !== null}
                onChange={(event) => setReason(event.target.value)}
                placeholder="For example: Blank synthetic practice logo used on all unsigned templates. Do not include patient details."
              />
              <p className={styles.helper}>8–1,000 characters. Never include patient details.</p>
            </div>
            <label className={styles.attestation}>
              <input
                type="checkbox"
                checked={attested}
                disabled={busy !== null}
                onChange={(event) => setAttested(event.target.checked)}
              />
              <span>
                I attest that this exact image is a reusable blank practice
                asset, contains no patient-specific content, and may be used in
                new templates for this practice.
              </span>
            </label>
            <div className={styles.actions}>
              <button
                className={styles.button}
                type="button"
                disabled={!decisionReady || !attested || busy !== null}
                onClick={() => void decide('approve')}
              >
                {busy === 'approve' ? 'Approving…' : 'Approve for this practice'}
              </button>
              <button
                className={styles.secondaryButton}
                type="button"
                disabled={!decisionReady || busy !== null}
                onClick={() => void decide('reject')}
              >
                {busy === 'reject' ? 'Rejecting…' : 'Reject these exact bytes'}
              </button>
            </div>
          </div>
        )}
      </section>

      <section className={styles.card} aria-labelledby="approved-assets-heading">
        <div className={styles.cardHeader}>
          <div>
            <h2 className={styles.cardTitle} id="approved-assets-heading">
              Practice image decisions
            </h2>
            <p className={styles.cardCopy}>
              Approval is practice-scoped and byte-exact. Revocation prevents
              new certifications without changing historical signed documents.
            </p>
          </div>
          <span className={styles.status}>{assets.length} recorded</span>
        </div>

        {assets.length === 0 ? (
          <p className={styles.cardCopy}>No reusable image decisions are recorded.</p>
        ) : (
          <div className={styles.assetList}>
            {assets.map((asset) => (
              <article className={styles.assetRow} key={asset.sha256}>
                <div className={styles.assetSummary}>
                  <div>
                    <h3 className={styles.assetName}>
                      PNG · {asset.width} × {asset.height}
                    </h3>
                    <p className={styles.assetMeta}>
                      {humanBytes(asset.sizeBytes)} · updated{' '}
                      {new Date(asset.updatedAtIso).toLocaleDateString()} · decision{' '}
                      {asset.decisionVersion}
                    </p>
                  </div>
                  <span className={`${styles.status} ${statusClass(asset.status)}`}>
                    {formatStatus(asset.status)}
                  </span>
                </div>
                <details className={styles.advanced}>
                  <summary>Advanced verification details</summary>
                  <div className={styles.digest}>SHA-256 {asset.sha256}</div>
                  <div>Scanner {asset.scannerVersion}</div>
                  <div>Local OCR {asset.ocrEngineVersion}</div>
                </details>
                {asset.status === 'APPROVED' && (
                  <div>
                    {revokingSha === asset.sha256 ? (
                      <div className={styles.revokeForm}>
                        <div className={styles.field}>
                          <label
                            className={styles.label}
                            htmlFor={`revoke-reason-${asset.sha256}`}
                          >
                            Why should new templates stop using this image?
                          </label>
                          <textarea
                            className={styles.textarea}
                            id={`revoke-reason-${asset.sha256}`}
                            maxLength={1000}
                            value={revokeReason}
                            disabled={busy !== null}
                            onChange={(event) => setRevokeReason(event.target.value)}
                          />
                        </div>
                        <div className={styles.actions}>
                          <button
                            className={styles.secondaryButton}
                            type="button"
                            disabled={revokeReason.trim().length < 8 || busy !== null}
                            onClick={() => void revoke(asset.sha256)}
                          >
                            {busy === `revoke:${asset.sha256}`
                              ? 'Revoking…'
                              : 'Confirm revocation'}
                          </button>
                          <button
                            className={styles.secondaryButton}
                            type="button"
                            disabled={busy !== null}
                            onClick={() => {
                              setRevokingSha(null);
                              setRevokeReason('');
                            }}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className={styles.actions}>
                        <button
                          className={styles.secondaryButton}
                          type="button"
                          disabled={busy !== null}
                          onClick={() => {
                            setRevokingSha(asset.sha256);
                            setRevokeReason('');
                          }}
                        >
                          Revoke for new templates
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
