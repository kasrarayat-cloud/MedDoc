'use client';

import type { CodingOutput } from '@meddoc/types';

interface Props {
  value: CodingOutput;
  onChange: (next: CodingOutput) => void;
  readOnly: boolean;
}

type CodedItemKind = 'icd10' | 'cpt';

export default function CodingTab({ value, onChange, readOnly }: Props) {
  function updateItem(kind: CodedItemKind, idx: number, patch: Partial<CodingOutput['icd10'][number]>) {
    onChange({
      ...value,
      [kind]: value[kind].map((item, i) => (i === idx ? { ...item, ...patch } : item)),
    });
  }
  function removeItem(kind: CodedItemKind, idx: number) {
    onChange({
      ...value,
      [kind]: value[kind].filter((_, i) => i !== idx),
    });
  }
  function addItem(kind: CodedItemKind) {
    onChange({
      ...value,
      [kind]: [
        ...value[kind],
        { code: '', description: '', evidence_quote: '', confidence: 'low' as const },
      ],
    });
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 text-xs">
        <span className="px-2 py-0.5 rounded bg-slate-800 font-mono">
          confidence: {value.confidence}
        </span>
      </div>

      {value.ambiguities.length > 0 && (
        <div className="border border-slate-700 rounded-lg p-3 text-sm bg-slate-900/40">
          <div className="font-medium">Flagged ambiguities</div>
          <ul className="text-slate-300 mt-2 list-disc list-inside space-y-1">
            {value.ambiguities.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </div>
      )}

      {(['icd10', 'cpt'] as const).map((kind) => (
        <section key={kind} className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold uppercase tracking-wide text-slate-300">
              {kind === 'icd10' ? 'ICD-10' : 'CPT'}
            </h3>
            {!readOnly && (
              <button
                type="button"
                onClick={() => addItem(kind)}
                className="text-xs px-2 py-1 rounded bg-slate-800 hover:bg-slate-700"
              >
                + add
              </button>
            )}
          </div>
          {value[kind].length === 0 && (
            <div className="text-sm text-slate-500">No {kind === 'icd10' ? 'ICD-10' : 'CPT'} codes.</div>
          )}
          {value[kind].map((item, i) => (
            <div key={i} className="border border-slate-800 rounded-lg p-3 space-y-2">
              <div className="flex items-start gap-2">
                <input
                  readOnly={readOnly}
                  value={item.code}
                  onChange={(e) => updateItem(kind, i, { code: e.target.value })}
                  className="font-mono bg-slate-900 border border-slate-700 rounded px-2 py-1 w-32 text-sm"
                  placeholder="code"
                />
                <select
                  disabled={readOnly}
                  value={item.confidence}
                  onChange={(e) =>
                    updateItem(kind, i, {
                      confidence: e.target.value as 'low' | 'medium' | 'high',
                    })
                  }
                  className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs disabled:opacity-50"
                >
                  <option value="low">low</option>
                  <option value="medium">medium</option>
                  <option value="high">high</option>
                </select>
                <div className="flex-1" />
                {!readOnly && (
                  <button
                    type="button"
                    onClick={() => removeItem(kind, i)}
                    className="text-xs text-rose-400 hover:text-rose-300"
                  >
                    remove
                  </button>
                )}
              </div>
              <input
                readOnly={readOnly}
                value={item.description}
                onChange={(e) => updateItem(kind, i, { description: e.target.value })}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm"
                placeholder="description"
              />
              <div className="text-xs text-slate-400">Evidence from transcript:</div>
              <blockquote className="text-xs text-slate-300 border-l-2 border-slate-600 pl-3 italic">
                {item.evidence_quote || '(no quote)'}
              </blockquote>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
