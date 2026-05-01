'use client';

// ============================================================================
// Problem list dialog (app-redesign-v1, Gate 7).
// ----------------------------------------------------------------------------
// Manage TranscribeMdPatient.problemList — the running condition list
// shown as chips on the patient header. Full-array replace semantics:
// the dialog's local state is the source of truth and gets PATCHed to
// /api/patients/[id] on save, same endpoint as EditPatientDialog.
//
// ICD-10 is a plain text field for Phase 1 per Gate 7 brief — a
// proper lookup lands in a later pass.
// ============================================================================

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import { toast } from 'sonner';

import { Ic } from '@/components/ui/icon';
import {
  ProblemStatusValues,
  parseProblemList,
  type ProblemListItem,
  type ProblemStatus,
} from '@/lib/problem-list';

export function ProblemListDialog({
  patientId,
  initialProblemList,
}: {
  patientId: string;
  /** Raw `Json?` from the server. Parsed client-side with the zod
   *  schema so a corrupted row still opens the editor with []. */
  initialProblemList: unknown;
}) {
  const router = useRouter();
  const initialItems = useMemo(
    () => parseProblemList(initialProblemList),
    [initialProblemList]
  );
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<ProblemListItem[]>(initialItems);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dirty = useMemo(
    () => JSON.stringify(items) !== JSON.stringify(initialItems),
    [items, initialItems]
  );

  function resetToInitial() {
    setItems(initialItems);
    setError(null);
    setSubmitting(false);
  }

  function addRow() {
    const empty: ProblemListItem = {
      condition: '',
      status: 'active',
      icd10: undefined,
    };
    setItems((prev) => [...prev, empty]);
  }

  function updateRow(index: number, patch: Partial<ProblemListItem>) {
    setItems((prev) =>
      prev.map((it, i) => (i === index ? { ...it, ...patch } : it))
    );
  }

  function removeRow(index: number) {
    setItems((prev) => prev.filter((_, i) => i !== index));
  }

  async function onSave() {
    setError(null);
    // Drop empty rows silently — the user probably added and didn't fill.
    const normalized: ProblemListItem[] = items
      .map((it) => ({
        condition: it.condition.trim(),
        status: it.status,
        icd10: it.icd10?.trim() ? it.icd10.trim() : undefined,
      }))
      .filter((it): it is ProblemListItem => it.condition.length > 0);

    setSubmitting(true);
    try {
      const res = await fetch(`/api/patients/${patientId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          problemList: normalized.length === 0 ? null : normalized,
        }),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { error?: string };
        setError(data.error ?? 'Could not save the problem list.');
        return;
      }
      toast.success('Problem list updated');
      setOpen(false);
      router.refresh();
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  const inputCls =
    'block w-full rounded-md border border-linear-border bg-linear-surface-1 px-2.5 py-2 text-[13px] text-linear-text placeholder:text-linear-text-3 outline-none transition-colors focus:border-linear-border-strong focus:ring-2 focus:ring-linear-sage/40';

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) resetToInitial();
      }}
    >
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="qm-lin-btn"
          aria-label="Manage problem list"
        >
          <Ic.edit width={12} height={12} />
          Manage
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[85vh] w-[calc(100%-40px)] max-w-[560px] -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-lg border border-linear-border-strong bg-linear-surface-2 p-6 shadow-[0_30px_80px_rgba(0,0,0,0.6)] outline-none">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <Dialog.Title className="m-0 text-[18px] font-semibold tracking-tight text-linear-text">
                Problem list
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-[12.5px] text-linear-text-3">
                Running conditions shown on the patient header. ICD-10 is a
                free-text field for now.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                className="flex-none rounded-md p-1 text-linear-text-3 hover:text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage/40"
              >
                <Ic.close width={14} height={14} />
              </button>
            </Dialog.Close>
          </div>

          <div className="mb-3.5 flex flex-col gap-2.5">
            {items.length === 0 && (
              <p className="rounded-md border border-dashed border-linear-border px-4 py-4 text-center text-[12.5px] text-linear-text-3">
                No conditions yet. Add one below.
              </p>
            )}
            {items.map((item, i) => (
              <div
                key={i}
                className="grid items-center gap-2"
                style={{ gridTemplateColumns: '1fr 130px 140px 32px' }}
              >
                <input
                  type="text"
                  value={item.condition}
                  onChange={(e) =>
                    updateRow(i, { condition: e.target.value })
                  }
                  placeholder="Condition (e.g. HTN, Afib)"
                  maxLength={200}
                  className={inputCls}
                />
                <select
                  value={item.status}
                  onChange={(e) =>
                    updateRow(i, { status: e.target.value as ProblemStatus })
                  }
                  className={`${inputCls} cursor-pointer appearance-none`}
                >
                  {ProblemStatusValues.map((s) => (
                    <option key={s} value={s} className="bg-linear-surface-1 text-linear-text">
                      {s[0].toUpperCase() + s.slice(1)}
                    </option>
                  ))}
                </select>
                <input
                  type="text"
                  value={item.icd10 ?? ''}
                  onChange={(e) => updateRow(i, { icd10: e.target.value })}
                  placeholder="ICD-10"
                  maxLength={20}
                  className={`${inputCls} font-mono`}
                />
                <button
                  type="button"
                  onClick={() => removeRow(i)}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-linear-border bg-transparent text-linear-text-3 hover:border-linear-danger/40 hover:text-linear-danger"
                  aria-label="Remove condition"
                >
                  <Ic.trash width={13} height={13} />
                </button>
              </div>
            ))}
          </div>

          <button
            type="button"
            onClick={addRow}
            className="inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-linear-border bg-transparent px-3 py-2.5 text-[12px] font-medium text-linear-text-2 hover:border-linear-border-strong hover:text-linear-text"
          >
            <Ic.plus width={13} height={13} />
            Add condition
          </button>

          {error && (
            <p role="alert" className="mt-3 text-[12px] text-linear-danger">
              {error}
            </p>
          )}

          <div className="mt-5 flex items-center justify-end gap-2 border-t border-linear-border pt-4">
            <Dialog.Close asChild>
              <button type="button" className="qm-lin-btn">
                Cancel
              </button>
            </Dialog.Close>
            <button
              type="button"
              disabled={!dirty || submitting}
              onClick={onSave}
              className="qm-lin-btn-primary disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? 'Saving…' : 'Save problem list'}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
