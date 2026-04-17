'use client';

import type { OutputError } from '@meddoc/types';

interface Props {
  outputType: string;
  error: OutputError['_error'];
}

/**
 * Shared renderer for ScribeOutput rows that carry the `{_error: {...}}`
 * sentinel (M4 D2). FLAG_OFF is a configuration choice, rendered neutrally;
 * everything else is a pipeline failure surfaced in amber.
 */
export default function OutputErrorCard({ outputType, error }: Props) {
  if (error.code === 'FLAG_OFF') {
    return (
      <div className="border border-slate-700 rounded-xl p-6 bg-slate-900/40 text-sm">
        <div className="font-medium text-slate-200">
          {outputType} is disabled by configuration
        </div>
        <div className="text-slate-400 mt-1">
          Your admin has turned off this extraction via the{' '}
          <span className="font-mono">SCRIBE_EXTRACT_*</span> feature flag.
          Re-enable it in the environment and re-run the visit.
        </div>
      </div>
    );
  }
  return (
    <div className="border border-amber-600/40 rounded-xl p-4 bg-amber-500/5 text-sm space-y-2">
      <div className="font-medium text-amber-300">
        {outputType} extraction failed after {error.attempts} attempt(s)
      </div>
      <div className="text-slate-300">
        <span className="font-mono text-xs text-amber-200">{error.code}</span>{' '}
        · {error.message}
      </div>
      <div className="text-xs text-slate-500">
        Occurred at {new Date(error.occurredAt).toLocaleString()}. Ask ops to
        rerun the finalize job, or continue to sign without this output.
      </div>
    </div>
  );
}
