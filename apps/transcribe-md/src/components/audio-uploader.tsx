'use client';

// ============================================================================
// AudioUploader — drop-zone + XHR upload to /api/visits/[id]/upload.
// ----------------------------------------------------------------------------
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the dark glass + violet
// gradient chrome verbatim. `theme="clinician"` swaps to a soft cream
// `.qm-cl-card` drop-zone, sage line-art icon chip, Source Serif 4
// title, and a primary `qm-cl-btn`. The XHR upload pipeline (URL,
// progress events, error categorization, 202 success path) is preserved
// byte-for-byte — only JSX/className surfaces change.
// ============================================================================

import { useCallback, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { UploadCloud, Mic, File as FileIcon, X, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import { SpecularButton } from '@/components/specular-button';

// Mirror the server-side allow-list. `audio/*` also covers provider-
// specific variants like audio/x-wav; we re-validate on the server.
const ACCEPT_ATTR = '.mp3,.m4a,.wav,.ogg,.webm,.flac,audio/*';

const MAX_BYTES = 500 * 1024 * 1024;

type AudioUploaderTheme = 'legacy' | 'clinician';

interface AudioUploaderProps {
  visitId: string;
  /** Phase 2 (Clinician remodel) — additive theme prop. */
  theme?: AudioUploaderTheme;
}

export function AudioUploader({ visitId, theme = 'legacy' }: AudioUploaderProps) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const isClinician = theme === 'clinician';

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
        // The parent page polls /status — a refresh flips the UI to
        // the Processing state. Refresh() is sufficient; the visit
        // page re-reads status and renders <ProcessingState/>.
        router.refresh();
        return;
      }
      let msg = `Upload failed (${xhr.status}).`;
      let toastTitle = 'Upload failed';
      let toastDescription = msg;
      // T-M16.4: read optional {code, retry} from the error body so
      // FILE_TOO_LARGE / UNSUPPORTED_FORMAT / STORAGE_* paths show the
      // right user-facing CTA (contact support vs try again).
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

  return (
    <div className="mx-auto w-full max-w-2xl">
      <div className="mb-6 text-center">
        <h2
          className={
            isClinician
              ? 'qm-cl-serif'
              : 'type-h1 text-text-primary'
          }
          style={
            isClinician
              ? {
                  fontSize: 32,
                  fontWeight: 400,
                  lineHeight: 1.15,
                  letterSpacing: '-0.015em',
                  color: 'var(--ink)',
                  margin: 0,
                }
              : undefined
          }
        >
          Upload your visit audio
        </h2>
        <p
          className={cn(
            'mt-2',
            isClinician
              ? 'qm-cl-serif text-clinician-ink-2'
              : 'text-[14px] text-text-tertiary'
          )}
          style={
            isClinician
              ? { fontSize: 15, fontStyle: 'italic', lineHeight: 1.55 }
              : undefined
          }
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
          'rounded-2xl border-2 border-dashed px-6 py-14 text-center',
          'transition-colors duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]',
          isClinician
            ? cn(
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-clinician-sage focus-visible:ring-offset-2 focus-visible:ring-offset-clinician-cream',
                dragging
                  ? 'border-clinician-sage bg-clinician-cream-card'
                  : 'border-clinician-line-strong bg-clinician-cream-card hover:border-clinician-sage/60 hover:bg-clinician-cream-2/50'
              )
            : cn(
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base',
                dragging
                  ? 'border-violet-400 bg-violet-500/8'
                  : 'border-border-default hover:border-violet-500/50 hover:bg-bg-surface-1/40'
              )
        )}
      >
        <div
          aria-hidden
          className={cn(
            'mb-4 flex h-14 w-14 items-center justify-center rounded-full'
          )}
          style={
            isClinician
              ? {
                  background: 'var(--sage-tint-strong)',
                  color: 'var(--sage-deep)',
                }
              : {
                  backgroundImage:
                    'linear-gradient(135deg,#4C1D95 0%,#7C3AED 100%)',
                  boxShadow: '0 0 0 1px rgba(167,139,250,0.3)',
                }
          }
        >
          <UploadCloud
            className={cn('h-6 w-6', isClinician ? '' : 'text-white')}
            aria-hidden
          />
        </div>
        <div
          className={cn(
            isClinician
              ? 'qm-cl-serif text-clinician-ink'
              : 'text-[15px] font-medium text-text-primary'
          )}
          style={
            isClinician
              ? { fontSize: 17, fontWeight: 500, letterSpacing: '-0.005em' }
              : undefined
          }
        >
          Drop an audio file here, or click to browse
        </div>
        <div
          className={cn(
            'mt-1.5 text-[12px]',
            isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
          )}
        >
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
        <div
          className={cn(
            'mt-5 rounded-xl p-4',
            isClinician
              ? 'qm-cl-card'
              : 'border border-border-default bg-bg-surface-1/60'
          )}
        >
          <div className="flex items-start gap-3">
            <div
              aria-hidden
              className={cn(
                'flex h-9 w-9 flex-none items-center justify-center rounded-lg',
                isClinician
                  ? 'bg-clinician-cream-2 text-clinician-ink-2'
                  : 'bg-bg-surface-3'
              )}
            >
              <FileIcon
                className={cn(
                  'h-4 w-4',
                  isClinician ? '' : 'text-text-tertiary'
                )}
                aria-hidden
              />
            </div>
            <div className="min-w-0 flex-1">
              <div
                className={cn(
                  'truncate text-[13px] font-medium',
                  isClinician
                    ? 'qm-cl-serif text-clinician-ink'
                    : 'text-text-primary'
                )}
                style={isClinician ? { fontSize: 15 } : undefined}
              >
                {file.name}
              </div>
              <div
                className={cn(
                  'mt-0.5 text-[11px]',
                  isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
                )}
              >
                {(file.size / 1024 / 1024).toFixed(1)} MB · {file.type || 'audio'}
              </div>
              {progress !== null && (
                <div className="mt-3 space-y-1.5">
                  <div
                    className={cn(
                      'h-1.5 w-full overflow-hidden rounded-full',
                      isClinician ? 'bg-clinician-cream-2' : 'bg-bg-surface-3'
                    )}
                  >
                    <div
                      className="h-full rounded-full transition-[width]"
                      style={
                        isClinician
                          ? {
                              width: `${progress}%`,
                              background: 'var(--sage)',
                            }
                          : {
                              width: `${progress}%`,
                              backgroundImage:
                                'linear-gradient(90deg,#7C3AED,#A855F7)',
                            }
                      }
                    />
                  </div>
                  <div
                    className={cn(
                      'text-[11px]',
                      isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
                    )}
                  >
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
                className={cn(
                  'flex-none rounded-md p-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
                  isClinician
                    ? 'text-clinician-ink-3 hover:bg-clinician-cream-2 hover:text-clinician-ink-2 focus-visible:ring-clinician-sage focus-visible:ring-offset-clinician-cream'
                    : 'text-text-muted hover:bg-bg-surface-2 hover:text-text-primary focus-visible:ring-violet-500 focus-visible:ring-offset-bg-base'
                )}
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            )}
          </div>
        </div>
      )}

      {uploadError && (
        <p
          role="alert"
          className={cn(
            'mt-3 text-[13px]',
            isClinician ? 'text-clinician-coral-deep' : 'text-danger'
          )}
          style={isClinician ? { color: 'var(--coral-deep)' } : undefined}
        >
          {uploadError}
        </p>
      )}

      <div className="mt-6 flex items-center justify-center">
        <SpecularButton
          onClick={upload}
          variant="primary"
          size="lg"
          disabled={!file || uploading}
          theme={theme}
        >
          <Mic className="h-4 w-4" aria-hidden />
          {uploading ? 'Uploading…' : 'Upload & transcribe'}
          {!uploading && <ArrowRight className="h-4 w-4" aria-hidden />}
        </SpecularButton>
      </div>
    </div>
  );
}
