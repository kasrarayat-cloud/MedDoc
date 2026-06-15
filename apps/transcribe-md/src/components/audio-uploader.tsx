'use client';

// ============================================================================
// AudioUploader — drop-zone + XHR upload to /api/visits/[id]/upload.
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. Drop-zone renders as a hairline-
// dashed surface-1 card with a sage icon chip; the picked-file
// preview becomes a hairline surface-1 row with a sage progress
// bar; the primary CTA is `.qm-lin-btn-primary`. The XHR upload
// pipeline (URL, progress events, error categorization, 202 success
// path) is preserved byte-for-byte — only JSX/className changes.
// The `theme` prop is preserved as a no-op.
// ============================================================================

import { useCallback, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { UploadCloud, Mic, File as FileIcon, X, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import { isSkinBeta } from '@/config/skin-beta';

// Mirror the server-side allow-list. `audio/*` also covers provider-
// specific variants like audio/x-wav; we re-validate on the server.
const ACCEPT_ATTR = '.mp3,.m4a,.wav,.ogg,.webm,.flac,audio/*';

const MAX_BYTES = 500 * 1024 * 1024;

type AudioUploaderTheme = 'legacy' | 'clinician';

interface AudioUploaderProps {
  visitId: string;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: AudioUploaderTheme;
}

export function AudioUploader({ visitId }: AudioUploaderProps) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const pickFile = useCallback((f: File | null) => {
    if (!f) return;
    if (f.size > MAX_BYTES) {
      setUploadError(
        `File is ${(f.size / 1024 / 1024).toFixed(0)} MB — limit is 500 MB.`
      );
      return;
    }
    if (!f.type.startsWith('audio/') && !/\.(mp3|m4a|wav|ogg|webm|flac)$/i.test(f.name)) {
      setUploadError(`${f.name} doesn't look like an audio file.`);
      return;
    }
    setUploadError(null);
    setFile(f);
  }, []);

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      pickFile(e.target.files?.[0] ?? null);
    },
    [pickFile]
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      pickFile(e.dataTransfer.files?.[0] ?? null);
    },
    [pickFile]
  );

  const upload = useCallback(() => {
    if (!file) return;
    setProgress(0);
    setUploadError(null);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/api/visits/${visitId}/upload`, true);
    xhr.setRequestHeader(
      'Content-Type',
      file.type || 'application/octet-stream'
    );
    xhr.setRequestHeader('X-TM-Filename', file.name);

    xhr.upload.onprogress = (evt) => {
      if (!evt.lengthComputable) return;
      setProgress(Math.round((evt.loaded / evt.total) * 100));
    };

    xhr.onload = () => {
      if (xhr.status === 202) {
        toast.success('Upload complete', {
          description: 'Transcribing and generating your SOAP note now.',
        });
        router.refresh();
        return;
      }
      let msg = `Upload failed (${xhr.status}).`;
      let toastTitle = 'Upload failed';
      let toastDescription = msg;
      try {
        const body = JSON.parse(xhr.responseText) as {
          error?: string;
          code?: string;
          retry?: boolean;
        };
        if (body?.error) {
          msg = body.error;
          toastDescription = body.error;
        }
        switch (body?.code) {
          case 'FILE_TOO_LARGE':
            toastTitle = 'File too large';
            break;
          case 'UNSUPPORTED_FORMAT':
            toastTitle = 'Unsupported file format';
            break;
          case 'STORAGE_TEMPORARY':
          case 'QUEUE_TEMPORARY':
            toastTitle = 'Temporary storage error';
            toastDescription = `${body.error ?? msg} (Please try the upload again.)`;
            break;
          case 'STORAGE_PERMANENT':
            toastTitle = 'Storage misconfigured';
            toastDescription = `${body.error ?? msg} (Please contact support — this is not something a retry will fix.)`;
            break;
          default:
            break;
        }
      } catch {
        /* ignore */
      }
      setProgress(null);
      setUploadError(msg);
      toast.error(toastTitle, { description: toastDescription });
    };

    xhr.onerror = () => {
      setProgress(null);
      setUploadError('Network error during upload.');
      toast.error('Upload failed', { description: 'Network error.' });
    };

    xhr.send(file);
  }, [file, visitId, router]);

  const clearFile = useCallback(() => {
    setFile(null);
    setProgress(null);
    setUploadError(null);
    if (inputRef.current) inputRef.current.value = '';
  }, []);

  const uploading = progress !== null && progress < 100;

  // C3 calm skin (flag-gated) — same drop-zone + same XHR upload to
  // /api/visits/[id]/upload, with the calm header + honest tone. Flag OFF →
  // the centered Linear V1 layout renders.
  const c3 = isSkinBeta();

  return (
    <div className={c3 ? 'qm-c3-cap' : 'mx-auto w-full max-w-2xl'}>
      <div className={c3 ? 'qm-c3-cap-head' : 'mb-6 text-center'}>
        {c3 && <span className="qm-c3-cap-kicker">Audio upload</span>}
        <h2
          style={
            c3
              ? undefined
              : {
                  margin: 0,
                  fontFamily: 'var(--font-sans)',
                  fontSize: 28,
                  fontWeight: 500,
                  lineHeight: 1.15,
                  letterSpacing: '-0.015em',
                  color: 'var(--color-linear-text)',
                }
          }
          className={c3 ? 'qm-c3-cap-h' : undefined}
        >
          {c3 ? 'Add the visit audio' : 'Upload your visit audio'}
        </h2>
        <p
          className="mt-2"
          style={{
            fontSize: 14,
            lineHeight: 1.55,
            color: 'var(--color-linear-text-2)',
          }}
        >
          MP3, M4A, WAV, OGG, WebM, or FLAC — up to 500 MB.
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        role="button"
        tabIndex={0}
        aria-label="Upload audio file"
        className={cn(
          'relative flex cursor-pointer flex-col items-center justify-center',
          'rounded-lg border-2 border-dashed px-6 py-14 text-center',
          'transition-colors duration-150 ease-out',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage focus-visible:ring-offset-2 focus-visible:ring-offset-linear-bg',
          dragging
            ? 'border-linear-sage bg-linear-sage-tint'
            : 'border-linear-border-strong bg-linear-surface-1 hover:border-[rgba(122,166,140,0.45)] hover:bg-linear-surface-2'
        )}
      >
        <div
          aria-hidden
          className="mb-4 flex h-14 w-14 items-center justify-center rounded-md"
          style={{
            background: 'var(--color-linear-sage-tint)',
            border: '1px solid rgba(122,166,140,0.32)',
            color: 'var(--color-linear-sage-bright)',
          }}
        >
          <UploadCloud className="h-6 w-6" aria-hidden />
        </div>
        <div className="text-[15px] font-medium text-linear-text">
          Drop an audio file here, or click to browse
        </div>
        <div className="mt-1.5 text-[12px] text-linear-text-3">
          Your recording stays private — uploaded directly to your workspace.
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT_ATTR}
          className="hidden"
          onChange={onInputChange}
        />
      </div>

      {file && (
        <div className="mt-5 rounded-lg border border-linear-border bg-linear-surface-1 p-4">
          <div className="flex items-start gap-3">
            <div
              aria-hidden
              className="flex h-9 w-9 flex-none items-center justify-center rounded-md bg-linear-surface-2 text-linear-text-2"
            >
              <FileIcon className="h-4 w-4" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[14px] font-medium text-linear-text">
                {file.name}
              </div>
              <div className="mt-0.5 text-[11px] text-linear-text-3">
                {(file.size / 1024 / 1024).toFixed(1)} MB · {file.type || 'audio'}
              </div>
              {progress !== null && (
                <div className="mt-3 space-y-1.5">
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-linear-surface-2">
                    <div
                      className="h-full rounded-full transition-[width]"
                      style={{
                        width: `${progress}%`,
                        background: 'var(--color-linear-sage)',
                      }}
                    />
                  </div>
                  <div className="text-[11px] text-linear-text-3">
                    {progress < 100
                      ? `Uploading… ${progress}%`
                      : 'Upload complete. Queuing for transcription…'}
                  </div>
                </div>
              )}
            </div>
            {progress === null && (
              <button
                type="button"
                onClick={clearFile}
                aria-label="Remove file"
                className="flex-none rounded-md p-1 text-linear-text-3 hover:bg-linear-surface-2 hover:text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage focus-visible:ring-offset-2 focus-visible:ring-offset-linear-bg"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            )}
          </div>
        </div>
      )}

      {uploadError && (
        <p role="alert" className="mt-3 text-[13px] text-linear-danger">
          {uploadError}
        </p>
      )}

      <div className="mt-6 flex items-center justify-center">
        <button
          type="button"
          onClick={upload}
          disabled={!file || uploading}
          className="qm-lin-btn-primary"
          style={{ padding: '10px 18px', height: 38 }}
        >
          <Mic className="h-4 w-4" aria-hidden />
          {uploading ? 'Uploading…' : 'Upload & transcribe'}
          {!uploading && <ArrowRight className="h-4 w-4" aria-hidden />}
        </button>
      </div>
    </div>
  );
}
