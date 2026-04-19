'use client';

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

interface AudioUploaderProps {
  visitId: string;
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
        // The parent page polls /status — a refresh flips the UI to
        // the Processing state. Refresh() is sufficient; the visit
        // page re-reads status and renders <ProcessingState/>.
        router.refresh();
        return;
      }
      let msg = `Upload failed (${xhr.status}).`;
      try {
        const body = JSON.parse(xhr.responseText);
        if (body?.error) msg = `Upload failed: ${body.error}`;
      } catch {
        /* ignore */
      }
      setProgress(null);
      setUploadError(msg);
      toast.error('Upload failed', { description: msg });
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
        <h2 className="type-h1 text-text-primary">Upload your visit audio</h2>
        <p className="mt-2 text-[14px] text-text-tertiary">
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
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base',
          dragging
            ? 'border-violet-400 bg-violet-500/8'
            : 'border-border-default hover:border-violet-500/50 hover:bg-bg-surface-1/40'
        )}
      >
        <div
          aria-hidden
          className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_100%)] shadow-[0_0_0_1px_rgba(167,139,250,0.3)]"
        >
          <UploadCloud className="h-6 w-6 text-white" aria-hidden />
        </div>
        <div className="text-[15px] font-medium text-text-primary">
          Drop an audio file here, or click to browse
        </div>
        <div className="mt-1.5 text-[12px] text-text-muted">
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
        <div className="mt-5 rounded-xl border border-border-default bg-bg-surface-1/60 p-4">
          <div className="flex items-start gap-3">
            <div
              aria-hidden
              className="flex h-9 w-9 flex-none items-center justify-center rounded-lg bg-bg-surface-3"
            >
              <FileIcon className="h-4 w-4 text-text-tertiary" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium text-text-primary">
                {file.name}
              </div>
              <div className="mt-0.5 text-[11px] text-text-muted">
                {(file.size / 1024 / 1024).toFixed(1)} MB · {file.type || 'audio'}
              </div>
              {progress !== null && (
                <div className="mt-3 space-y-1.5">
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-surface-3">
                    <div
                      className="h-full rounded-full bg-[linear-gradient(90deg,#7C3AED,#A855F7)] transition-[width]"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <div className="text-[11px] text-text-muted">
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
                className="flex-none rounded-md p-1 text-text-muted transition-colors hover:bg-bg-surface-2 hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            )}
          </div>
        </div>
      )}

      {uploadError && (
        <p role="alert" className="mt-3 text-[13px] text-danger">
          {uploadError}
        </p>
      )}

      <div className="mt-6 flex items-center justify-center">
        <SpecularButton
          onClick={upload}
          variant="primary"
          size="lg"
          disabled={!file || uploading}
        >
          <Mic className="h-4 w-4" aria-hidden />
          {uploading ? 'Uploading…' : 'Upload & transcribe'}
          {!uploading && <ArrowRight className="h-4 w-4" aria-hidden />}
        </SpecularButton>
      </div>
    </div>
  );
}
