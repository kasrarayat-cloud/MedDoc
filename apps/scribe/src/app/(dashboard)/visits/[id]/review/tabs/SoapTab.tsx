'use client';

import { useMemo } from 'react';
import type { SoapNote } from '@meddoc/types';

interface Props {
  value: SoapNote;
  onChange: (next: SoapNote) => void;
  readOnly: boolean;
}

/**
 * SOAP editor — lifted from the M2 monolithic ReviewClient so it sits
 * alongside the other M4 tabs. Shape and interactions are unchanged.
 */
export default function SoapTab({ value, onChange, readOnly }: Props) {
  const subjectiveKeys = useMemo(() => Object.keys(value.subjective), [value.subjective]);
  const objectiveKeys = useMemo(() => Object.keys(value.objective), [value.objective]);
  const planKeys = useMemo(() => Object.keys(value.plan), [value.plan]);

  function updateRecord(section: 'subjective' | 'objective' | 'plan', key: string, v: string) {
    onChange({ ...value, [section]: { ...value[section], [key]: v } });
  }

  function updateAssessment(idx: number, patch: Partial<SoapNote['assessment'][number]>) {
    onChange({
      ...value,
      assessment: value.assessment.map((a, i) => (i === idx ? { ...a, ...patch } : a)),
    });
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 text-xs">
        <span className="px-2 py-0.5 rounded bg-slate-800 font-mono">
          confidence: {value.confidence}
        </span>
      </div>

      {value.requires_immediate_follow_up && (
        <div className="border-2 border-rose-500/60 bg-rose-500/10 rounded-lg p-3 text-sm">
          <div className="font-semibold text-rose-200">
            🚨 Requires immediate clinical follow-up
          </div>
          <div className="text-slate-200 mt-1">
            The generator flagged an acute safety concern in this visit.
            Review the safety plan and document the follow-up before signing.
            The patient-facing summary auto-appends 988 and 911 resources.
          </div>
          {!readOnly && (
            <label className="flex items-center gap-2 mt-2 text-xs text-slate-300">
              <input
                type="checkbox"
                checked={Boolean(value.requires_immediate_follow_up)}
                onChange={(e) =>
                  onChange({ ...value, requires_immediate_follow_up: e.target.checked || undefined })
                }
              />
              Keep this flag set
            </label>
          )}
        </div>
      )}

      {value.missing_required_elements.length > 0 && (
        <div className="border border-amber-600/50 bg-amber-500/5 rounded-lg p-3 text-sm">
          <div className="font-medium text-amber-300">Missing required elements</div>
          <div className="text-slate-300 mt-1">
            {value.missing_required_elements.join(', ')}
          </div>
        </div>
      )}

      {value.ambiguities.length > 0 && (
        <div className="border border-slate-700 rounded-lg p-3 text-sm bg-slate-900/40">
          <div className="font-medium">Model flagged ambiguities</div>
          <ul className="text-slate-300 mt-2 list-disc list-inside space-y-1">
            {value.ambiguities.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </div>
      )}

      <section className="space-y-3">
        <h3 className="text-base font-semibold">Subjective</h3>
        {subjectiveKeys.map((k) => (
          <Field key={k} label={k} readOnly={readOnly} value={value.subjective[k]}
            onChange={(v) => updateRecord('subjective', k, v)} />
        ))}
      </section>

      <section className="space-y-3">
        <h3 className="text-base font-semibold">Objective</h3>
        {objectiveKeys.map((k) => (
          <Field key={k} label={k} readOnly={readOnly} value={value.objective[k]}
            onChange={(v) => updateRecord('objective', k, v)} />
        ))}
      </section>

      <section className="space-y-3">
        <h3 className="text-base font-semibold">Assessment</h3>
        {value.assessment.length === 0 && (
          <div className="text-sm text-slate-500">No assessment items.</div>
        )}
        {value.assessment.map((item, i) => (
          <div key={i} className="border border-slate-800 rounded-lg p-3 space-y-2">
            <div className="flex gap-2 items-center text-xs">
              <input readOnly={readOnly} value={item.icd10_candidate}
                onChange={(e) => updateAssessment(i, { icd10_candidate: e.target.value })}
                className="font-mono bg-slate-900 border border-slate-700 rounded px-2 py-1 w-32 disabled:opacity-50"
              />
              <select disabled={readOnly} value={item.confidence}
                onChange={(e) => updateAssessment(i, { confidence: e.target.value as 'low' | 'medium' | 'high' })}
                className="bg-slate-900 border border-slate-700 rounded px-2 py-1 disabled:opacity-50"
              >
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
            </div>
            <textarea readOnly={readOnly} rows={2} value={item.description}
              onChange={(e) => updateAssessment(i, { description: e.target.value })}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm disabled:opacity-50"
            />
            <div className="text-xs text-slate-400">Evidence from transcript:</div>
            <blockquote className="text-xs text-slate-300 border-l-2 border-slate-600 pl-3 italic">
              {item.evidence_quote}
            </blockquote>
          </div>
        ))}
      </section>

      <section className="space-y-3">
        <h3 className="text-base font-semibold">Plan</h3>
        {planKeys.map((k) => (
          <Field key={k} label={k} readOnly={readOnly} value={value.plan[k]}
            onChange={(v) => updateRecord('plan', k, v)} />
        ))}
      </section>
    </div>
  );
}

function Field({
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
      <span className="text-xs font-mono text-slate-400">{label}</span>
      <textarea
        value={value}
        readOnly={readOnly}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        className="mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm disabled:opacity-50"
      />
    </label>
  );
}
