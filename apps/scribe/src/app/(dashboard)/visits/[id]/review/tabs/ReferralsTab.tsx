'use client';

import type { ReferralOutput, ReferralLetter } from '@meddoc/types';

interface Props {
  value: ReferralOutput;
  onChange: (next: ReferralOutput) => void;
  readOnly: boolean;
}

const DEFAULT_REF: ReferralLetter = {
  specialty: '',
  urgency: 'routine',
  clinical_summary: '',
  reason_for_referral: '',
  relevant_history: '',
  evidence_quote: '',
  confidence: 'low',
};

export default function ReferralsTab({ value, onChange, readOnly }: Props) {
  function update(idx: number, patch: Partial<ReferralLetter>) {
    onChange({
      ...value,
      referrals: value.referrals.map((r, i) => (i === idx ? { ...r, ...patch } : r)),
    });
  }
  function remove(idx: number) {
    onChange({ ...value, referrals: value.referrals.filter((_, i) => i !== idx) });
  }
  function add() {
    onChange({ ...value, referrals: [...value.referrals, DEFAULT_REF] });
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 text-xs">
        <span className="px-2 py-0.5 rounded bg-slate-800 font-mono">
          confidence: {value.confidence}
        </span>
        {!readOnly && (
          <button
            type="button"
            onClick={add}
            className="ml-auto text-xs px-2 py-1 rounded bg-slate-800 hover:bg-slate-700"
          >
            + add referral
          </button>
        )}
      </div>

      {value.ambiguities.length > 0 && (
        <div className="border border-slate-700 rounded-lg p-3 text-sm bg-slate-900/40">
          <div className="font-medium">Flagged ambiguities</div>
          <ul className="text-slate-300 mt-2 list-disc list-inside space-y-1">
            {value.ambiguities.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </div>
      )}

      {value.referrals.length === 0 && (
        <div className="text-sm text-slate-500">No referrals drafted.</div>
      )}

      {value.referrals.map((ref, i) => (
        <article key={i} className="border border-slate-800 rounded-lg p-4 space-y-3 bg-slate-900/30">
          <div className="flex items-start gap-2">
            <input
              readOnly={readOnly}
              value={ref.specialty}
              onChange={(e) => update(i, { specialty: e.target.value })}
              placeholder="specialty"
              className="flex-1 bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm font-medium"
            />
            <select
              disabled={readOnly}
              value={ref.urgency}
              onChange={(e) =>
                update(i, { urgency: e.target.value as ReferralLetter['urgency'] })
              }
              className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs disabled:opacity-50"
            >
              <option value="routine">routine</option>
              <option value="urgent">urgent</option>
              <option value="stat">stat</option>
            </select>
            {!readOnly && (
              <button
                type="button"
                onClick={() => remove(i)}
                className="text-xs text-rose-400 hover:text-rose-300"
              >
                remove
              </button>
            )}
          </div>

          <LabeledArea label="reason for referral" readOnly={readOnly} value={ref.reason_for_referral}
            onChange={(v) => update(i, { reason_for_referral: v })} rows={2} />
          <LabeledArea label="clinical summary" readOnly={readOnly} value={ref.clinical_summary}
            onChange={(v) => update(i, { clinical_summary: v })} rows={3} />
          <LabeledArea label="relevant history" readOnly={readOnly} value={ref.relevant_history}
            onChange={(v) => update(i, { relevant_history: v })} rows={2} />

          <div className="text-xs text-slate-400">Evidence:</div>
          <blockquote className="text-xs text-slate-300 border-l-2 border-slate-600 pl-3 italic">
            {ref.evidence_quote || '(no quote)'}
          </blockquote>
        </article>
      ))}
    </div>
  );
}

function LabeledArea({
  label,
  value,
  onChange,
  readOnly,
  rows,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  readOnly: boolean;
  rows: number;
}) {
  return (
    <label className="block text-xs">
      <span className="text-slate-400">{label}</span>
      <textarea readOnly={readOnly} rows={rows} value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm"
      />
    </label>
  );
}
