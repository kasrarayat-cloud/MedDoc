'use client';

// ============================================================================
// InsuranceStatusToggle — tri-state segmented control
// ----------------------------------------------------------------------------
// Three buttons mapping to the underlying tri-state column:
//   true  → "Verified"  (card on file, eligibility checked)
//   null  → "Pending"   (verification in progress / not yet checked)
//   false → "Self-pay"  (no insurance to bill)
//
// Used by AddPatientModal and EditPatientModal so both flows can set every
// state. Color matches the InsuranceBadge on the patient detail page so the
// doctor sees the same visual semantics in both places.
// ============================================================================

import { ShieldCheck, Shield, ShieldAlert } from 'lucide-react';

type Option = {
  value: boolean | null;
  label: string;
  Icon: typeof Shield;
  /** Tailwind classes for the active state. */
  activeClasses: string;
};

const OPTIONS: Option[] = [
  {
    value: true,
    label: 'Verified',
    Icon: ShieldCheck,
    activeClasses: 'bg-emerald-500/20 border-emerald-500/50 text-emerald-200',
  },
  {
    value: null,
    label: 'Pending',
    Icon: Shield,
    activeClasses: 'bg-slate-500/20 border-slate-400/40 text-slate-100',
  },
  {
    value: false,
    label: 'Self-pay',
    Icon: ShieldAlert,
    activeClasses: 'bg-amber-500/20 border-amber-500/50 text-amber-200',
  },
];

interface InsuranceStatusToggleProps {
  value: boolean | null;
  onChange: (value: boolean | null) => void;
  disabled?: boolean;
}

export default function InsuranceStatusToggle({
  value,
  onChange,
  disabled,
}: InsuranceStatusToggleProps) {
  return (
    <div className="flex flex-col">
      <span className="block text-[11px] font-semibold uppercase tracking-wider mb-1 text-slate-400">
        Insurance
      </span>
      <div
        role="radiogroup"
        aria-label="Insurance status"
        className="inline-flex rounded-lg bg-white/5 border border-white/10 p-0.5 gap-0.5"
      >
        {OPTIONS.map((opt) => {
          const isActive = value === opt.value;
          return (
            <button
              key={String(opt.value)}
              type="button"
              role="radio"
              aria-checked={isActive}
              onClick={() => onChange(opt.value)}
              disabled={disabled}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-semibold border transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                isActive
                  ? opt.activeClasses
                  : 'bg-transparent border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/5'
              }`}
            >
              <opt.Icon className="w-3.5 h-3.5" />
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
