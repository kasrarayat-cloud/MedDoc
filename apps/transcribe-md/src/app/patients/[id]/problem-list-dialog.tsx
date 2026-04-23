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
          className="qm-btn qm-btn-ghost qm-btn-sm"
          aria-label="Manage problem list"
        >
          <Ic.edit width={12} height={12} />
          Manage
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 40,
            background: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(4px)',
          }}
        />
        <Dialog.Content
          className="qm-app"
          style={{
            position: 'fixed',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 50,
            width: 'calc(100% - 40px)',
            maxWidth: 560,
            maxHeight: '85vh',
            overflow: 'auto',
            borderRadius: 20,
            border: '1px solid var(--line)',
            background: 'var(--bg-1)',
            padding: 24,
            outline: 'none',
            boxShadow: 'var(--shadow-2)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: 12,
              marginBottom: 16,
            }}
          >
            <div>
              <Dialog.Title
                className="qm-serif"
                style={{
                  margin: 0,
                  fontSize: 20,
                  fontWeight: 400,
                  letterSpacing: '-0.015em',
                }}
              >
                Problem list
              </Dialog.Title>
              <Dialog.Description
                style={{
                  marginTop: 4,
                  fontSize: 12.5,
                  color: 'var(--fg-3)',
                }}
              >
                Running conditions shown on the patient header. ICD-10 is a
                free-text field for now.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                className="qm-btn qm-btn-icon"
              >
                <Ic.close width={14} height={14} />
              </button>
            </Dialog.Close>
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
              marginBottom: 14,
            }}
          >
            {items.length === 0 && (
              <p
                style={{
                  fontSize: 12.5,
                  color: 'var(--fg-3)',
                  textAlign: 'center',
                  padding: '18px 0',
                  border: '1px dashed var(--line)',
                  borderRadius: 10,
                }}
              >
                No conditions yet. Add one below.
              </p>
            )}
            {items.map((item, i) => (
              <div
                key={i}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 130px 140px 32px',
                  gap: 8,
                  alignItems: 'center',
                }}
              >
                <input
                  type="text"
                  value={item.condition}
                  onChange={(e) =>
                    updateRow(i, { condition: e.target.value })
                  }
                  placeholder="Condition (e.g. HTN, Afib)"
                  maxLength={200}
                  className="qm-input"
                  style={{ padding: '8px 10px' }}
                />
                <select
                  value={item.status}
                  onChange={(e) =>
                    updateRow(i, { status: e.target.value as ProblemStatus })
                  }
                  className="qm-input"
                  style={{ padding: '8px 10px', cursor: 'pointer' }}
                >
                  {ProblemStatusValues.map((s) => (
                    <option key={s} value={s}>
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
                  className="qm-input"
                  style={{ padding: '8px 10px', fontFamily: 'var(--mono)' }}
                />
                <button
                  type="button"
                  onClick={() => removeRow(i)}
                  className="qm-btn qm-btn-icon"
                  aria-label="Remove condition"
                  style={{ width: 32, height: 32 }}
                >
                  <Ic.trash width={13} height={13} />
                </button>
              </div>
            ))}
          </div>

          <button
            type="button"
            onClick={addRow}
            className="qm-btn qm-btn-ghost"
            style={{
              width: '100%',
              justifyContent: 'center',
              padding: 10,
              borderStyle: 'dashed',
            }}
          >
            <Ic.plus width={13} height={13} />
            Add condition
          </button>

          {error && (
            <p
              role="alert"
              style={{
                marginTop: 12,
                fontSize: 12,
                color: 'var(--coral)',
              }}
            >
              {error}
            </p>
          )}

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: 8,
              borderTop: '1px solid var(--line-soft)',
              marginTop: 18,
              paddingTop: 16,
            }}
          >
            <Dialog.Close asChild>
              <button
                type="button"
                className="qm-btn qm-btn-ghost"
                style={{ padding: '8px 14px' }}
              >
                Cancel
              </button>
            </Dialog.Close>
            <button
              type="button"
              disabled={!dirty || submitting}
              onClick={onSave}
              className="qm-btn qm-btn-primary"
              style={{
                padding: '8px 16px',
                opacity: !dirty || submitting ? 0.5 : 1,
                cursor: !dirty || submitting ? 'not-allowed' : 'pointer',
              }}
            >
              {submitting ? 'Saving…' : 'Save problem list'}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
