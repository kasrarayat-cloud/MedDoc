'use client';

import type { RxOutput, RxDraft, RxWarning } from '@meddoc/types';

interface Props {
  value: RxOutput;
  onChange: (next: RxOutput) => void;
  readOnly: boolean;
}

const DEFAULT_RX: RxDraft = {
  drug: '',
  dose: '',
  route: 'PO',
  frequency: '',
  duration: '',
  quantity: '',
  refills: 0,
  sig: '',
  is_controlled: false,
  clinician_requested: false,
  evidence_quote: '',
  warnings: [],
  confidence: 'low',
};

export default function RxTab({ value, onChange, readOnly }: Props) {
  function updateRx(idx: number, patch: Partial<RxDraft>) {
    onChange({
      ...value,
      prescriptions: value.prescriptions.map((p, i) => (i === idx ? { ...p, ...patch } : p)),
    });
  }
  function removeRx(idx: number) {
    onChange({
      ...value,
      prescriptions: value.prescriptions.filter((_, i) => i !== idx),
    });
  }
  function addRx() {
    onChange({ ...value, prescriptions: [...value.prescriptions, DEFAULT_RX] });
  }

  return (
    <div className="space-y-5">
      <div className="border border-sky-700/40 bg-sky-500/10 rounded-lg p-3 text-xs text-sky-200">
        AI-generated interaction check — clinician must verify against the
        patient&apos;s chart, allergies, and current medications before prescribing.
      </div>

      <div className="flex items-center gap-3 text-xs">
        <span className="px-2 py-0.5 rounded bg-slate-800 font-mono">
          confidence: {value.confidence}
        </span>
        {!readOnly && (
          <button
            type="button"
            onClick={addRx}
            className="ml-auto text-xs px-2 py-1 rounded bg-slate-800 hover:bg-slate-700"
          >
            + add prescription
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

      {value.prescriptions.length === 0 && (
        <div className="text-sm text-slate-500">No prescriptions drafted.</div>
      )}

      {value.prescriptions.map((rx, i) => (
        <article key={i} className="border border-slate-800 rounded-lg p-4 space-y-3 bg-slate-900/30">
          <div className="flex items-start gap-2">
            <input
              readOnly={readOnly}
              value={rx.drug}
              onChange={(e) => updateRx(i, { drug: e.target.value })}
              placeholder="drug"
              className="flex-1 bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm font-medium"
            />
            {!readOnly && (
              <button
                type="button"
                onClick={() => removeRx(i)}
                className="text-xs text-rose-400 hover:text-rose-300"
              >
                remove
              </button>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <LabeledInput label="dose" value={rx.dose} readOnly={readOnly}
              onChange={(v) => updateRx(i, { dose: v })} />
            <LabeledInput label="route" value={rx.route} readOnly={readOnly}
              onChange={(v) => updateRx(i, { route: v })} />
            <LabeledInput label="frequency" value={rx.frequency} readOnly={readOnly}
              onChange={(v) => updateRx(i, { frequency: v })} />
            <LabeledInput label="duration" value={rx.duration} readOnly={readOnly}
              onChange={(v) => updateRx(i, { duration: v })} />
            <LabeledInput label="quantity" value={rx.quantity} readOnly={readOnly}
              onChange={(v) => updateRx(i, { quantity: v })} />
            <label className="block">
              <span className="text-slate-400">refills</span>
              <input type="number" min={0} max={11} readOnly={readOnly} value={rx.refills}
                onChange={(e) => updateRx(i, { refills: Number(e.target.value) || 0 })}
                className="mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1"
              />
            </label>
          </div>

          <label className="block text-xs">
            <span className="text-slate-400">sig</span>
            <textarea readOnly={readOnly} rows={2} value={rx.sig}
              onChange={(e) => updateRx(i, { sig: e.target.value })}
              className="mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm"
            />
          </label>

          <div className="flex gap-4 text-xs">
            <label className="flex items-center gap-1">
              <input type="checkbox" disabled={readOnly} checked={rx.is_controlled}
                onChange={(e) => updateRx(i, { is_controlled: e.target.checked })} />
              Controlled substance
            </label>
            <label className="flex items-center gap-1">
              <input type="checkbox" disabled={readOnly} checked={rx.clinician_requested}
                onChange={(e) => updateRx(i, { clinician_requested: e.target.checked })} />
              Clinician explicitly requested
            </label>
            {rx.is_controlled && !rx.clinician_requested && (
              <span className="text-rose-300 font-medium">
                ⚠ Controlled without explicit request
              </span>
            )}
          </div>

          {rx.warnings.length > 0 && (
            <div className="space-y-1">
              <div className="text-xs text-slate-400">AI safety warnings</div>
              {rx.warnings.map((w, wi) => (
                <WarningRow key={wi} warning={w} />
              ))}
            </div>
          )}

          <div className="text-xs text-slate-400">Evidence:</div>
          <blockquote className="text-xs text-slate-300 border-l-2 border-slate-600 pl-3 italic">
            {rx.evidence_quote || '(no quote)'}
          </blockquote>
        </article>
      ))}
    </div>
  );
}

function LabeledInput({
  label,
  value,
  onChange,
  readOnly,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  readOnly: boolean;
}) {
  return (
    <label className="block">
      <span className="text-slate-400">{label}</span>
      <input
        readOnly={readOnly}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1"
      />
    </label>
  );
}

function WarningRow({ warning }: { warning: RxWarning }) {
  const color =
    warning.severity === 'critical'
      ? 'border-rose-500/50 bg-rose-500/10 text-rose-200'
      : warning.severity === 'warning'
        ? 'border-amber-500/50 bg-amber-500/10 text-amber-200'
        : 'border-slate-600/50 bg-slate-700/10 text-slate-300';
  return (
    <div className={`text-xs border rounded px-2 py-1 ${color}`}>
      <span className="font-mono uppercase">{warning.kind}</span> · {warning.message}
      {warning.related_drugs.length > 0 && (
        <span className="text-slate-400"> — related: {warning.related_drugs.join(', ')}</span>
      )}
    </div>
  );
}
