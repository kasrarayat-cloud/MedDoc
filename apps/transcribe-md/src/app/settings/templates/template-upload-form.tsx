'use client';

import { useCallback, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { UploadCloud, File as FileIcon, X } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import { SpecularButton } from '@/components/specular-button';

const ACCEPT_ATTR =
  '.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document';
const MAX_BYTES = 5 * 1024 * 1024;

interface Props {
  supportedTokens: string[];
}

interface UploadSuccess {
  id: string;
  name: string;
  originalFileName: string;
  tokens: string[];
  unsupportedTokens: string[];
}

export function TemplateUploadForm({ supportedTokens }: Props) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpload, setLastUpload] = useState<UploadSuccess | null>(null);

  const pickFile = useCallback((f: File | null) => {
    if (!f) return;
    if (f.size === 0) {
      setError('That file is empty.');
      return;
    }
    if (f.size > MAX_BYTES) {
      setError(
        `File is ${(f.size / 1024 / 1024).toFixed(1)} MB — limit is 5 MB.`
      );
      return;
    }
    if (!/\.docx$/i.test(f.name)) {
      setError('Please upload a .docx file (Word / Pages / Google Docs export).');
      return;
    }
    setError(null);
    setFile(f);
    // Auto-fill the name from the filename if the doctor hasn't set one.
    if (!name) {
      setName(f.name.replace(/\.docx$/i, ''));
    }
  }, [name]);

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      pickFile(e.dataTransfer.files?.[0] ?? null);
    },
    [pickFile]
  );

  const clearFile = useCallback(() => {
    setFile(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = '';
  }, []);

  const upload = useCallback(async () => {
    if (!file) return;
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Give the template a name.');
      return;
    }
    if (trimmedName.length > 80) {
      setError('Template name must be 80 characters or fewer.');
      return;
    }

    setError(null);
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('name', trimmedName);

      const res = await fetch('/api/templates', {
        method: 'POST',
        body: form,
      });
      const body = await res.json().catch(() => ({}));

      if (!res.ok) {
        const msg = body?.error ?? `Upload failed (${res.status}).`;
        setError(msg);
        toast.error('Could not upload template', { description: msg });
        return;
      }

      const success = body as UploadSuccess;
      setLastUpload(success);
      setFile(null);
      setName('');
      if (inputRef.current) inputRef.current.value = '';

      toast.success('Template uploaded', {
        description:
          success.tokens.length === 0
            ? 'No placeholders detected — the template will produce a blank copy per visit.'
            : `${success.tokens.length} placeholder${success.tokens.length === 1 ? '' : 's'} ready.`,
      });

      router.refresh();
    } catch {
      const msg = 'Network error during upload.';
      setError(msg);
      toast.error('Could not upload template', { description: msg });
    } finally {
      setUploading(false);
    }
  }, [file, name, router]);

  return (
    <div className="space-y-4">
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
        aria-label="Upload template file"
        className={cn(
          'relative flex cursor-pointer flex-col items-center justify-center',
          'rounded-xl border-2 border-dashed px-6 py-10 text-center',
          'transition-colors duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base',
          dragging
            ? 'border-violet-400 bg-violet-500/8'
            : 'border-border-default hover:border-violet-500/50 hover:bg-bg-surface-1/40'
        )}
      >
        <div
          aria-hidden
          className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_100%)] shadow-[0_0_0_1px_rgba(167,139,250,0.3)]"
        >
          <UploadCloud className="h-5 w-5 text-white" aria-hidden />
        </div>
        <div className="text-[14px] font-medium text-text-primary">
          Drop a .docx template here, or click to browse
        </div>
        <div className="mt-1 text-[12px] text-text-muted">
          Use placeholders like <code className="text-text-secondary">{'{{hpi}}'}</code>{' '}
          and <code className="text-text-secondary">{'{{plan}}'}</code> — up to 5 MB.
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT_ATTR}
          className="hidden"
          onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
        />
      </div>

      {file && (
        <div className="rounded-lg border border-border-default bg-bg-surface-1/60 p-4">
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
                {(file.size / 1024).toFixed(0)} KB
              </div>
            </div>
            <button
              type="button"
              onClick={clearFile}
              aria-label="Remove file"
              disabled={uploading}
              className="flex-none rounded-md p-1 text-text-muted transition-colors hover:bg-bg-surface-2 hover:text-text-primary disabled:opacity-50"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>
      )}

      <div>
        <label
          htmlFor="template-name"
          className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary"
        >
          Template name
        </label>
        <input
          id="template-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Family medicine SOAP"
          disabled={uploading}
          maxLength={80}
          className="block w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30 disabled:opacity-50"
        />
      </div>

      {error && (
        <p role="alert" className="text-[12px] text-danger">
          {error}
        </p>
      )}

      <div className="flex items-center justify-end gap-3 pt-1">
        <SpecularButton
          onClick={upload}
          variant="primary"
          size="md"
          disabled={!file || uploading}
        >
          {uploading ? 'Uploading…' : 'Upload template'}
        </SpecularButton>
      </div>

      {lastUpload && (
        <UploadSummary result={lastUpload} supportedTokens={supportedTokens} />
      )}
    </div>
  );
}

function UploadSummary({
  result,
  supportedTokens,
}: {
  result: UploadSuccess;
  supportedTokens: string[];
}) {
  const supportedSet = new Set(supportedTokens);
  const supported = result.tokens.filter((t) => supportedSet.has(t));
  return (
    <div className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-4 text-[13px]">
      <div className="font-medium text-text-primary">
        “{result.name}” is ready.
      </div>
      {supported.length > 0 && (
        <div className="mt-2">
          <div className="text-[11px] uppercase tracking-wider text-text-muted">
            Placeholders we&apos;ll fill
          </div>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {supported.map((t) => (
              <TokenChip key={t} token={t} supported />
            ))}
          </div>
        </div>
      )}
      {result.unsupportedTokens.length > 0 && (
        <div className="mt-3">
          <div className="text-[11px] uppercase tracking-wider text-warning/90">
            Unsupported placeholders (will render empty)
          </div>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {result.unsupportedTokens.map((t) => (
              <TokenChip key={t} token={t} supported={false} />
            ))}
          </div>
          <p className="mt-2 text-[11px] text-text-tertiary">
            These aren&apos;t in our supported token list yet. The template
            still uploads — those slots just fill with blank content. See the
            Template Guide for the full list.
          </p>
        </div>
      )}
    </div>
  );
}

function TokenChip({
  token,
  supported,
}: {
  token: string;
  supported: boolean;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 font-mono text-[11px]',
        supported
          ? 'border border-violet-500/40 bg-violet-500/10 text-violet-200'
          : 'border border-warning/40 bg-warning/10 text-warning'
      )}
    >
      {'{{'}
      {token}
      {'}}'}
    </span>
  );
}
