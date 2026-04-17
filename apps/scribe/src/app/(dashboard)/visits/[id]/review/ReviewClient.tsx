'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import type {
  SoapNote,
  CodingOutput,
  RxOutput,
  ReferralOutput,
  PatientSummary,
  OutputError,
} from '@meddoc/types';
import {
  saveEditedSoapAction,
  saveEditedCodingAction,
  saveEditedRxAction,
  saveEditedReferralsAction,
  saveEditedPatientSummaryAction,
  signAndSendVisitAction,
} from './actions';
import SoapTab from './tabs/SoapTab';
import CodingTab from './tabs/CodingTab';
import RxTab from './tabs/RxTab';
import ReferralsTab from './tabs/ReferralsTab';
import PatientSummaryTab from './tabs/PatientSummaryTab';
import OutputErrorCard from './tabs/OutputErrorCard';

export type LoadedOutput<T> =
  | { kind: 'ok'; data: T }
  | { kind: 'error'; error: OutputError['_error'] }
  | { kind: 'missing' };

export interface ReviewInitial {
  soap: LoadedOutput<SoapNote>;
  coding: LoadedOutput<CodingOutput>;
  rx: LoadedOutput<RxOutput>;
  referrals: LoadedOutput<ReferralOutput>;
  summary: LoadedOutput<PatientSummary>;
}

interface Props {
  visitId: string;
  initial: ReviewInitial;
  canSign: boolean;
}

type TabKey = 'soap' | 'coding' | 'rx' | 'referrals' | 'summary';

const TAB_LABELS: Record<TabKey, string> = {
  soap: 'SOAP',
  coding: 'Codes',
  rx: 'Rx',
  referrals: 'Referrals',
  summary: 'Patient summary',
};

export default function ReviewClient({ visitId, initial, canSign }: Props) {
  const router = useRouter();
  const [tab, setTab] = useState<TabKey>('soap');
  const [soap, setSoap] = useState(initial.soap);
  const [coding, setCoding] = useState(initial.coding);
  const [rx, setRx] = useState(initial.rx);
  const [referrals, setReferrals] = useState(initial.referrals);
  const [summary, setSummary] = useState(initial.summary);
  const [dirty, setDirty] = useState<Record<TabKey, boolean>>({
    soap: false, coding: false, rx: false, referrals: false, summary: false,
  });
  const [busy, setBusy] = useState<'idle' | 'saving' | 'signing'>('idle');
  const [error, setError] = useState<string | null>(null);

  const anyDirty = Object.values(dirty).some(Boolean);

  function markDirty(key: TabKey, value: boolean): void {
    setDirty((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave(): Promise<void> {
    setError(null);
    setBusy('saving');
    try {
      if (tab === 'soap' && soap.kind === 'ok') {
        await saveEditedSoapAction({ visitId, soap: soap.data });
      } else if (tab === 'coding' && coding.kind === 'ok') {
        await saveEditedCodingAction({ visitId, coding: coding.data });
      } else if (tab === 'rx' && rx.kind === 'ok') {
        await saveEditedRxAction({ visitId, rx: rx.data });
      } else if (tab === 'referrals' && referrals.kind === 'ok') {
        await saveEditedReferralsAction({ visitId, referrals: referrals.data });
      } else if (tab === 'summary' && summary.kind === 'ok') {
        await saveEditedPatientSummaryAction({ visitId, summary: summary.data });
      }
      markDirty(tab, false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy('idle');
    }
  }

  async function handleSign(): Promise<void> {
    setError(null);
    if (anyDirty) {
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

  // Per-tab renderer dispatches on the LoadedOutput.kind.
  function renderTab() {
    switch (tab) {
      case 'soap':
        return soap.kind === 'ok'
          ? <SoapTab value={soap.data} readOnly={!canSign}
              onChange={(v) => { setSoap({ kind: 'ok', data: v }); markDirty('soap', true); }} />
          : soap.kind === 'error'
            ? <OutputErrorCard outputType="SOAP" error={soap.error} />
            : <EmptyTab type="SOAP" />;
      case 'coding':
        return coding.kind === 'ok'
          ? <CodingTab value={coding.data} readOnly={!canSign}
              onChange={(v) => { setCoding({ kind: 'ok', data: v }); markDirty('coding', true); }} />
          : coding.kind === 'error'
            ? <OutputErrorCard outputType="Codes" error={coding.error} />
            : <EmptyTab type="Codes" />;
      case 'rx':
        return rx.kind === 'ok'
          ? <RxTab value={rx.data} readOnly={!canSign}
              onChange={(v) => { setRx({ kind: 'ok', data: v }); markDirty('rx', true); }} />
          : rx.kind === 'error'
            ? <OutputErrorCard outputType="Rx" error={rx.error} />
            : <EmptyTab type="Rx" />;
      case 'referrals':
        return referrals.kind === 'ok'
          ? <ReferralsTab value={referrals.data} readOnly={!canSign}
              onChange={(v) => { setReferrals({ kind: 'ok', data: v }); markDirty('referrals', true); }} />
          : referrals.kind === 'error'
            ? <OutputErrorCard outputType="Referrals" error={referrals.error} />
            : <EmptyTab type="Referrals" />;
      case 'summary':
        return summary.kind === 'ok'
          ? <PatientSummaryTab value={summary.data} readOnly={!canSign}
              onChange={(v) => { setSummary({ kind: 'ok', data: v }); markDirty('summary', true); }} />
          : summary.kind === 'error'
            ? <OutputErrorCard outputType="Patient summary" error={summary.error} />
            : <EmptyTab type="Patient summary" />;
    }
  }

  const activeIsEditable =
    (tab === 'soap' && soap.kind === 'ok') ||
    (tab === 'coding' && coding.kind === 'ok') ||
    (tab === 'rx' && rx.kind === 'ok') ||
    (tab === 'referrals' && referrals.kind === 'ok') ||
    (tab === 'summary' && summary.kind === 'ok');

  const tabState: Record<TabKey, LoadedOutput<unknown>> = { soap, coding, rx, referrals, summary };

  return (
    <div className="space-y-5">
      <nav className="flex gap-1 border-b border-slate-800">
        {(Object.keys(TAB_LABELS) as TabKey[]).map((key) => {
          const state = tabState[key];
          const flagOff = state.kind === 'error' && state.error.code === 'FLAG_OFF';
          const broken = state.kind === 'error' && state.error.code !== 'FLAG_OFF';
          return (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={`px-3 py-2 text-sm border-b-2 -mb-px transition-colors ${
                tab === key
                  ? 'border-blue-500 text-slate-100'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              {TAB_LABELS[key]}
              {dirty[key] && <span className="ml-1 text-amber-300">•</span>}
              {broken && <span className="ml-1 text-rose-400">⚠</span>}
              {flagOff && <span className="ml-1 text-slate-500">◌</span>}
            </button>
          );
        })}
      </nav>

      {renderTab()}

      {error && (
        <div className="text-sm text-amber-400 border border-amber-600/40 rounded-lg p-3 bg-amber-500/5">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 pt-2 border-t border-slate-800">
        <button
          type="button"
          onClick={handleSave}
          disabled={!activeIsEditable || !dirty[tab] || busy !== 'idle'}
          className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-sm font-semibold"
        >
          {busy === 'saving' ? 'Saving…' : `Save ${TAB_LABELS[tab]} draft`}
        </button>
        <button
          type="button"
          onClick={handleSign}
          disabled={!canSign || anyDirty || busy !== 'idle'}
          className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-sm font-semibold"
        >
          {busy === 'signing' ? 'Signing…' : 'Sign & send to MedDoc Pro'}
        </button>
        {anyDirty && (
          <span className="text-xs text-amber-300">
            Unsaved changes in{' '}
            {(Object.keys(dirty) as TabKey[]).filter((k) => dirty[k]).map((k) => TAB_LABELS[k]).join(', ')}
          </span>
        )}
      </div>
    </div>
  );
}

function EmptyTab({ type }: { type: string }) {
  return (
    <div className="border border-slate-800 rounded-xl p-6 bg-slate-900/40 text-sm text-slate-400">
      No {type} output yet. The pipeline may still be running, or this
      output type wasn&apos;t generated for this visit.
    </div>
  );
}
