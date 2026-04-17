'use client';

import { useMemo } from 'react';
import type { PatientSummary } from '@meddoc/types';
import { fleschKincaidGrade } from '@/lib/flesch-kincaid';

interface Props {
  value: PatientSummary;
  onChange: (next: PatientSummary) => void;
  readOnly: boolean;
}

type ListKey = 'what_we_talked_about' | 'your_plan' | 'medications' | 'when_to_call_us';

/**
 * Concatenate every user-facing string in the summary for the
 * Flesch-Kincaid check. Excludes the reading_level_target marker.
 */
function summaryBody(s: PatientSummary): string {
  return [
    s.greeting,
    ...s.what_we_talked_about,
    ...s.your_plan,
    ...s.medications,
    s.follow_up,
    ...s.when_to_call_us,
  ]
    .filter(Boolean)
    .join(' ');
}

export default function PatientSummaryTab({ value, onChange, readOnly }: Props) {
  const grade = useMemo(() => fleschKincaidGrade(summaryBody(value)), [value]);
  const tooHigh = grade > 6.0;

  function updateList(key: ListKey, idx: number, v: string) {
    onChange({ ...value, [key]: value[key].map((s, i) => (i === idx ? v : s)) });
  }
  function addListItem(key: ListKey) {
    onChange({ ...value, [key]: [...value[key], ''] });
  }
  function removeListItem(key: ListKey, idx: number) {
    onChange({ ...value, [key]: value[key].filter((_, i) => i !== idx) });
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 text-xs">
        <span className="px-2 py-0.5 rounded bg-slate-800 font-mono">
          confidence: {value.confidence}
        </span>
        <span
          className={`px-2 py-0.5 rounded font-mono ${
            tooHigh ? 'bg-amber-500/20 text-amber-200' : 'bg-emerald-500/20 text-emerald-200'
          }`}
          title="Flesch-Kincaid grade of the combined summary body. Target is 6.0 or lower."
        >
          reading level: grade {grade.toFixed(1)}
          {tooHigh && ' — above 6.0'}
        </span>
      </div>

      {tooHigh && (
        <div className="border border-amber-600/40 bg-amber-500/5 rounded-lg p-3 text-xs text-amber-200">
          Reading level is above 6th grade. Shorter sentences and simpler words
          will help the patient understand. This is a warning, not a block —
          you can still save and sign.
        </div>
      )}

      {value.ambiguities.length > 0 && (
        <div className="border border-slate-700 rounded-lg p-3 text-sm bg-slate-900/40">
          <div className="font-medium">Flagged ambiguities</div>
          <ul className="text-slate-300 mt-2 list-disc list-inside space-y-1">
            {value.ambiguities.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </div>
      )}

      <label className="block text-xs">
        <span className="text-slate-400">greeting</span>
        <input readOnly={readOnly} value={value.greeting}
          onChange={(e) => onChange({ ...value, greeting: e.target.value })}
          className="mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm"
        />
      </label>

      <ListEditor label="what we talked about" readOnly={readOnly} items={value.what_we_talked_about}
        onUpdate={(i, v) => updateList('what_we_talked_about', i, v)}
        onAdd={() => addListItem('what_we_talked_about')}
        onRemove={(i) => removeListItem('what_we_talked_about', i)} />

      <ListEditor label="your plan" readOnly={readOnly} items={value.your_plan}
        onUpdate={(i, v) => updateList('your_plan', i, v)}
        onAdd={() => addListItem('your_plan')}
        onRemove={(i) => removeListItem('your_plan', i)} />

      <ListEditor label="medications" readOnly={readOnly} items={value.medications}
        onUpdate={(i, v) => updateList('medications', i, v)}
        onAdd={() => addListItem('medications')}
        onRemove={(i) => removeListItem('medications', i)} />

      <label className="block text-xs">
        <span className="text-slate-400">follow-up</span>
        <input readOnly={readOnly} value={value.follow_up}
          onChange={(e) => onChange({ ...value, follow_up: e.target.value })}
          className="mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm"
        />
      </label>

      <ListEditor label="when to call us" readOnly={readOnly} items={value.when_to_call_us}
        onUpdate={(i, v) => updateList('when_to_call_us', i, v)}
        onAdd={() => addListItem('when_to_call_us')}
        onRemove={(i) => removeListItem('when_to_call_us', i)} />
    </div>
  );
}

function ListEditor({
  label,
  items,
  onUpdate,
  onAdd,
  onRemove,
  readOnly,
}: {
  label: string;
  items: string[];
  onUpdate: (idx: number, v: string) => void;
  onAdd: () => void;
  onRemove: (idx: number) => void;
  readOnly: boolean;
}) {
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono text-slate-400">{label}</span>
        {!readOnly && (
          <button
            type="button"
            onClick={onAdd}
            className="text-xs px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700"
          >
            + add
          </button>
        )}
      </div>
      {items.length === 0 && <div className="text-xs text-slate-500">(none)</div>}
      {items.map((item, i) => (
        <div key={i} className="flex gap-2 items-start">
          <textarea
            readOnly={readOnly}
            rows={2}
            value={item}
            onChange={(e) => onUpdate(i, e.target.value)}
            className="flex-1 bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm"
          />
          {!readOnly && (
            <button
              type="button"
              onClick={() => onRemove(i)}
              className="text-xs text-rose-400 hover:text-rose-300 mt-1"
            >
              remove
            </button>
          )}
        </div>
      ))}
    </section>
  );
}
