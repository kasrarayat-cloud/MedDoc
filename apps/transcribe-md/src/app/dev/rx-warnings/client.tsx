'use client';

// Dev preview client — hardcoded fixtures for RxWarningCard variants.
// All fixtures use stable `dev-preview-*` IDs per the Phase-1 brief.

import { useState } from 'react';
import { toast } from 'sonner';

import {
  RxWarningCard,
  type RxWarning,
} from '@/components/rx/rx-warning-card';

const CRITICAL_FIXTURE: RxWarning = {
  id: 'dev-preview-critical-1',
  rxLineNumber: 2,
  sev: 'critical',
  headline: 'Cannot verify medication.',
  action: 'Do NOT prescribe until confirmed.',
  actionKind: 'ban',
  heard: 'abirrobing',
  guess: 'possibly ibuprofen?',
  transcriberConfidence: 0.42,
  confidenceThreshold: 0.7,
  risks: [
    {
      parts: [
        { t: 'Patient is on ' },
        { t: 'Valsartan + HCTZ', b: true },
        { t: ' (ACE-I + thiazide).' },
      ],
      outcome: [
        { t: 'Adding an NSAID risks ' },
        { t: 'acute kidney injury', b: true },
        { t: ' ("triple whammy").' },
      ],
    },
    {
      parts: [
        { t: 'Patient is on ' },
        { t: 'Omeprazole', b: true },
        { t: ' — active GI prophylaxis.' },
      ],
      outcome: [
        { t: 'NSAIDs may ' },
        { t: 'aggravate gastric irritation', b: true },
        { t: '.' },
      ],
    },
  ],
  nextStep:
    'Confirm medication name verbally with the prescribing provider before signing.',
  details: [
    'Deepgram returned the token "abirrobing" with low confidence (0.42, below the 0.70 threshold for prescription names).',
    'Two concurrent medications on the patient chart flag kidney + GI pathways that interact with NSAIDs. Rule set v2.1 lines 81–94.',
  ],
  source: 'Transcript 14:22',
};

const WARNING_FIXTURE: RxWarning = {
  id: 'dev-preview-warning-1',
  rxLineNumber: 4,
  sev: 'warning',
  headline: 'Dose outside typical range.',
  action: 'Double-check dose with patient weight.',
  actionKind: 'alert',
  risks: [
    {
      parts: [
        { t: 'Prescribed ' },
        { t: '600 mg q6h', b: true },
        { t: ' exceeds the typical adult maximum of 400 mg q6h.' },
      ],
    },
  ],
  nextStep:
    'Verify weight-based dosing if patient is >100 kg; otherwise reduce to 400 mg.',
  details: [
    'Dose exceeds the upper bound of the standard adult range for this medication by 50%.',
  ],
  source: 'Transcript 14:31',
};

const INFO_FIXTURE: RxWarning = {
  id: 'dev-preview-info-1',
  rxLineNumber: 7,
  sev: 'info',
  headline: 'Prescriber preference applied.',
  action: 'Using brand-name Tylenol per your default style.',
  actionKind: 'info',
};

interface Props {
  variant:
    | 'critical'
    | 'warning'
    | 'info'
    | 'collapsed'
    | 'expanded'
    | 'in-context';
}

export function DevRxWarningsClient({ variant }: Props) {
  const [dismissed, setDismissed] = useState<Record<string, boolean>>({});

  const notify = (msg: string) => toast.message(msg);

  if (variant === 'critical') {
    return (
      <RxWarningCard
        warning={CRITICAL_FIXTURE}
        visitId="dev-preview"
        onEdit={() => notify('onEdit fired')}
        onCall={() => notify('onCall fired')}
        onOverridden={(auditId) => notify(`Override recorded (audit ${auditId})`)}
      />
    );
  }

  if (variant === 'warning') {
    if (dismissed.warning) return <p>Warning dismissed. Reload to reset.</p>;
    return (
      <RxWarningCard
        warning={WARNING_FIXTURE}
        visitId="dev-preview"
        onEdit={() => notify('onEdit fired')}
        onCall={() => notify('onCall fired')}
        onAcknowledge={() => notify('onAcknowledge fired')}
        onDismiss={() => setDismissed((p) => ({ ...p, warning: true }))}
      />
    );
  }

  if (variant === 'info') {
    if (dismissed.info) return <p>Info dismissed. Reload to reset.</p>;
    return (
      <RxWarningCard
        warning={INFO_FIXTURE}
        visitId="dev-preview"
        onDismiss={() => setDismissed((p) => ({ ...p, info: true }))}
      />
    );
  }

  if (variant === 'collapsed') {
    return (
      <RxWarningCard
        warning={CRITICAL_FIXTURE}
        visitId="dev-preview"
        defaultOpen={false}
        onEdit={() => notify('onEdit fired')}
        onCall={() => notify('onCall fired')}
      />
    );
  }

  if (variant === 'expanded') {
    return (
      <RxWarningCard
        warning={CRITICAL_FIXTURE}
        visitId="dev-preview"
        defaultOpen
        onEdit={() => notify('onEdit fired')}
        onCall={() => notify('onCall fired')}
      />
    );
  }

  // in-context — stack all three to simulate a multi-warning Rx slip
  return (
    <>
      <RxWarningCard
        warning={CRITICAL_FIXTURE}
        visitId="dev-preview"
        onEdit={() => notify('onEdit fired')}
        onCall={() => notify('onCall fired')}
      />
      <RxWarningCard
        warning={WARNING_FIXTURE}
        visitId="dev-preview"
        onEdit={() => notify('onEdit fired')}
        onCall={() => notify('onCall fired')}
        onAcknowledge={() => notify('onAcknowledge fired')}
      />
      <RxWarningCard warning={INFO_FIXTURE} visitId="dev-preview" />
    </>
  );
}
