'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { createPresignedUploadUrlAction } from './actions';

type Phase = 'idle' | 'presigning' | 'uploading' | 'finalizing' | 'done' | 'error';

interface Props {
  visitId: string;
}

const ACCEPTED = 'audio/mpeg,audio/mp4,audio/wav,audio/x-wav,audio/webm,audio/m4a,audio/ogg,video/mp4';
const MAX_MB = 240; // ~2 hours of 256kbps mp3

export default function UploadClient({ visitId }: Props) {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload() {
    if (!file) return;
    setError(null);
    setPhase('presigning');
    try {
      const { uploadUrl } = await createPresignedUploadUrlAction({
        visitId,
        fileName: file.name,
        contentType: file.type || 'audio/mpeg',
      });

      setPhase('uploading');
      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('PUT', uploadUrl);
        xhr.setRequestHeader('Content-Type', file.type || 'audio/mpeg');
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) setProgress(Math.round((e.loaded / e.total) * 100));
        };
        xhr.onload = () =>
          xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`Upload failed: ${xhr.status}`));
        xhr.onerror = () => reject(new Error('Network error during upload.'));
        xhr.send(file);
      });

      setPhase('finalizing');
      const res = await fetch(`/api/uploads/${visitId}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fileName: file.name }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        throw new Error(body.error || `Finalize failed: ${res.status}`);
      }
      setPhase('done');
      router.replace(`/visits/${visitId}`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setPhase('error');
    }
  }

  return (
    <div className="space-y-5">
      <label className="block border border-dashed border-slate-700 rounded-xl p-6 text-center cursor-pointer hover:border-slate-500">
        <input
          type="file"
          accept={ACCEPTED}
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0] ?? null;
            if (f && f.size > MAX_MB * 1024 * 1024) {
              setError(`File is larger than ${MAX_MB} MB. Split it or re-encode.`);
              return;
            }
            setFile(f);
            setError(null);
          }}
        />
        <div className="text-sm">
          {file ? (
            <>
              <div className="font-medium">{file.name}</div>
              <div className="text-slate-400 mt-1">
                {(file.size / (1024 * 1024)).toFixed(1)} MB · {file.type || 'audio'}
              </div>
            </>
          ) : (
            <>
              <div className="font-medium">Click to choose an audio file</div>
              <div className="text-slate-500 mt-1">mp3 / m4a / wav / webm — up to {MAX_MB} MB, ~2 hours</div>
            </>
          )}
        </div>
      </label>

      {phase === 'uploading' && (
        <div className="text-sm text-slate-300">
          Uploading… {progress}%
          <div className="w-full h-1.5 bg-slate-800 rounded mt-2 overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}
      {phase === 'finalizing' && (
        <div className="text-sm text-slate-300">Finalizing — enqueueing transcription…</div>
      )}
      {error && (
        <div className="text-sm text-amber-400 border border-amber-600/40 rounded-lg p-3 bg-amber-500/5">
          {error}
        </div>
      )}

      <button
        type="button"
        onClick={handleUpload}
        disabled={!file || phase === 'presigning' || phase === 'uploading' || phase === 'finalizing'}
        className="w-full py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-sm font-semibold"
      >
        {phase === 'idle' || phase === 'error' ? 'Upload and transcribe' : phase}
      </button>
    </div>
  );
}
