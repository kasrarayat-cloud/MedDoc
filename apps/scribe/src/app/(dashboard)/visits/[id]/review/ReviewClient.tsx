'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import type { SoapNote } from '@meddoc/types';
import { saveEditedSoapAction, signAndSendVisitAction } from './actions';

interface Props {
  visitId: string;
  initial: SoapNote;
  canSign: boolean;
}

export default function ReviewClient({ visitId, initial, canSign }: Props) {
  const router = useRouter();
  const [soap, setSoap] = useState<SoapNote>(initial);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<'idle' | 'saving' | 'signing'>('idle');
  const [error, setError] = useState<string | null>(null);

  const subjectiveKeys = useMemo(() => Object.keys(soap.subjective), [soap.subjective]);
  const objectiveKeys = useMemo(() => Object.keys(soap.objective), [soap.objective]);
  const planKeys = useMemo(() => Object.keys(soap.plan), [soap.plan]);

  function updateRecord(section: 'subjective' | 'objective' | 'plan', key: string, value: string) {
    setSoap((prev) => ({ ...prev, [section]: { ...prev[section], [key]: value } }));
    setDirty(true);
  }

  function updateAssessment(idx: number, patch: Partial<SoapNote['assessment'][number]>) {
    setSoap((prev) => ({
      ...prev,
      assessment: prev.assessment.map((a, i) => (i === idx ? { ...a, ...patch } : a)),
    }));
    setDirty(true);
  }

  async function handleSave() {
    setError(null);
    setBusy('saving');
    try {
      await saveEditedSoapAction({ visitId, soap });
      setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy('idle');
    }
  }

  async function handleSign() {
    setError(null);
    if (dirty) {
      setError('Save your edits before signing.');
      return;
    }
    setBusy('signing');
    try {
      await signAndSendVisitAction({ visitId });
      router.replace(`/visits/${visitId}`);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy('idle');
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 text-sm">
        <span className="px-2 py-0.5 rounded bg-slate-800 font-mono">
          confidence: {soap.confidence}
        </span>
        {dirty && <span className="text-amber-300">Unsaved edits</span>}
      </div>

      {soap.missing_required_elements.length > 0 && (
        <div className="border border-amber-600/50 bg-amber-500/5 rounded-lg p-4 text-sm">
          <div className="font-medium text-amber-300">Missing required elements</div>
          <div className="text-slate-300 mt-1">
            {soap.missing_required_elements.join(', ')}
          </div>
        </div>
      )}

      {soap.ambiguities.length > 0 && (
        <div className="border border-slate-700 rounded-lg p-4 text-sm bg-slate-900/40">
          <div className="font-medium">Model flagged ambiguities</div>
          <ul className="text-slate-300 mt-2 list-disc list-inside space-y-1">
            {soap.ambiguities.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Subjective</h2>
        {subjectiveKeys.map((k) => (
          <SectionField
            key={k}
            label={k}
            value={soap.subjective[k]}
            onChange={(v) => updateRecord('subjective', k, v)}
          />
        ))}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Objective</h2>
        {objectiveKeys.map((k) => (
          <SectionField
            key={k}
            label={k}
            value={soap.objective[k]}
            onChange={(v) => updateRecord('objective', k, v)}
          />
        ))}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Assessment</h2>
        {soap.assessment.length === 0 && (
          <div className="text-sm text-slate-500">No assessment items.</div>
        )}
        {soap.assessment.map((item, i) => (
          <div key={i} className="border border-slate-800 rounded-lg p-3 space-y-2">
            <div className="flex gap-2 items-center text-xs">
              <input
                value={item.icd10_candidate}
                onChange={(e) => updateAssessment(i, { icd10_candidate: e.target.value })}
                className="font-mono bg-slate-900 border border-slate-700 rounded px-2 py-1 w-32"
              />
              <select
                value={item.confidence}
                onChange={(e) =>
                  updateAssessment(i, {
                    confidence: e.target.value as 'low' | 'medium' | 'high',
                  })
                }
                className="bg-slate-900 border border-slate-700 rounded px-2 py-1"
              >
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
            </div>
            <textarea
              value={item.description}
              onChange={(e) => updateAssessment(i, { description: e.target.value })}
              rows={2}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm"
            />
            <div className="text-xs text-slate-400">Evidence from transcript:</div>
            <blockquote className="text-xs text-slate-300 border-l-2 border-slate-600 pl-3 italic">
              {item.evidence_quote}
            </blockquote>
          </div>
        ))}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Plan</h2>
        {planKeys.map((k) => (
          <SectionField
            key={k}
            label={k}
            value={soap.plan[k]}
            onChange={(v) => updateRecord('plan', k, v)}
          />
        ))}
      </section>

      {error && (
        <div className="text-sm text-amber-400 border border-amber-600/40 rounded-lg p-3 bg-amber-500/5">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 pt-2 border-t border-slate-800">
        <button
          type="button"
          onClick={handleSave}
          disabled={!dirty || busy !== 'idle'}
          className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-sm font-semibold"
        >
          {busy === 'saving' ? 'Saving…' : 'Save draft'}
        </button>
        <button
          type="button"
          onClick={handleSign}
          disabled={!canSign || dirty || busy !== 'idle'}
          className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-sm font-semibold"
        >
          {busy === 'signing' ? 'Signing…' : 'Sign & send to MedDoc Pro'}
        </button>
      </div>
    </div>
  );
}

function SectionField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs font-mono text-slate-400">{label}</span>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        className="mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm"
      />
    </label>
  );
}
