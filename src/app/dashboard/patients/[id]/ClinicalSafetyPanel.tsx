'use client';

// ============================================================================
// Clinical Safety Panel — allergies + medications
// ----------------------------------------------------------------------------
// Sits at the top of the clinical column (above Profile Details). EHR
// convention is allergies-first: the doctor sees them before any prescribing
// decision. SEVERE rows trigger a red banner above both lists.
//
// Edit flow is intentionally minimal for MVP: add + delete + (for meds)
// toggle active. To "edit" an entry the doctor deletes and re-adds — keeps
// the audit trail honest (each correction is a separate row) and saves
// us a per-row inline-edit form.
// ============================================================================

import React, { useState, useTransition } from 'react';
import {
  AlertTriangle,
  Pill,
  Plus,
  Trash2,
  ShieldCheck,
  Loader2,
  Eye,
  EyeOff,
  Pause,
  Play,
} from 'lucide-react';

import {
  addAllergyAction,
  deleteAllergyAction,
  setNoKnownAllergiesAction,
  addMedicationAction,
  deleteMedicationAction,
  updateMedicationAction,
  listMedicationsAction,
} from '../actions';
import type {
  AllergyView,
  MedicationView,
} from '@/lib/data/clinical-safety';

type Severity = 'UNKNOWN' | 'MILD' | 'MODERATE' | 'SEVERE';

interface ClinicalSafetyPanelProps {
  patientId: string;
  initialAllergies: AllergyView[];
  initialMedications: MedicationView[];
  initialNoKnownAllergies: boolean;
}

export default function ClinicalSafetyPanel({
  patientId,
  initialAllergies,
  initialMedications,
  initialNoKnownAllergies,
}: ClinicalSafetyPanelProps) {
  const [allergies, setAllergies] = useState(initialAllergies);
  const [meds, setMeds] = useState(initialMedications);
  const [nka, setNka] = useState(initialNoKnownAllergies);

  const severeAllergies = allergies.filter((a) => a.severity === 'SEVERE');
  const allergyCount = allergies.length;
  const activeMedsCount = meds.filter((m) => m.isActive).length;
  const inactiveMedsCount = meds.filter((m) => !m.isActive).length;

  return (
    <div className="space-y-3">
      {/* Top-of-chart SEVERE banner — only shows when at least one SEVERE
          allergy exists. Doctors should never miss this, hence red. */}
      {severeAllergies.length > 0 && (
        <div className="rounded-xl bg-red-500/15 border border-red-500/40 p-3 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-300 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-red-200 uppercase tracking-wide">
              Severe Allergy Alert
            </p>
            <ul className="mt-1 space-y-0.5">
              {severeAllergies.map((a) => (
                <li key={a.id} className="text-sm text-red-100">
                  <span className="font-semibold">{a.allergen}</span>
                  {a.reaction ? <span className="text-red-200/80"> — {a.reaction}</span> : null}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <AllergiesCard
        patientId={patientId}
        allergies={allergies}
        setAllergies={setAllergies}
        nka={nka}
        setNka={setNka}
        count={allergyCount}
      />

      <MedicationsCard
        patientId={patientId}
        meds={meds}
        setMeds={setMeds}
        activeCount={activeMedsCount}
        inactiveCount={inactiveMedsCount}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// ALLERGIES CARD
// ---------------------------------------------------------------------------

function AllergiesCard({
  patientId,
  allergies,
  setAllergies,
  nka,
  setNka,
  count,
}: {
  patientId: string;
  allergies: AllergyView[];
  setAllergies: React.Dispatch<React.SetStateAction<AllergyView[]>>;
  nka: boolean;
  setNka: React.Dispatch<React.SetStateAction<boolean>>;
  count: number;
}) {
  const [isAdding, setIsAdding] = useState(false);
  const [allergen, setAllergen] = useState('');
  const [reaction, setReaction] = useState('');
  const [severity, setSeverity] = useState<Severity>('UNKNOWN');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const reset = () => {
    setAllergen('');
    setReaction('');
    setSeverity('UNKNOWN');
    setNotes('');
    setError(null);
  };

  const handleAdd = () => {
    if (!allergen.trim()) {
      setError('Allergen is required');
      return;
    }
    startTransition(async () => {
      const result = await addAllergyAction({
        patientId,
        allergen: allergen.trim(),
        reaction: reaction.trim() || null,
        severity,
        notes: notes.trim() || null,
      });
      if (!result.ok) {
        setError(result.error);
        return;
      }
      // Adding any allergy invalidates an NKA flag — it's a contradiction.
      if (nka) setNka(false);
      setAllergies((prev) => [result.data, ...prev]);
      reset();
      setIsAdding(false);
    });
  };

  const handleDelete = (id: string) => {
    if (!confirm('Delete this allergy? This is recorded in the audit log.')) return;
    startTransition(async () => {
      const result = await deleteAllergyAction(id, patientId);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setAllergies((prev) => prev.filter((a) => a.id !== id));
    });
  };

  const handleToggleNka = () => {
    if (allergies.length > 0 && !nka) {
      // Can't claim NKA while allergies are listed.
      setError('Delete listed allergies before marking No Known Allergies.');
      return;
    }
    const newValue = !nka;
    startTransition(async () => {
      const result = await setNoKnownAllergiesAction(patientId, newValue);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setNka(newValue);
    });
  };

  return (
    <div className="rounded-xl bg-white/5 backdrop-blur-md border border-white/10 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-red-500/15 border border-red-500/30">
            <AlertTriangle className="w-4 h-4 text-red-300" />
          </div>
          <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
            Allergies
          </h2>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10">
            {count}
          </span>
        </div>
        {!isAdding && (
          <button
            onClick={() => setIsAdding(true)}
            className="text-[11px] text-slate-300 hover:text-white flex items-center gap-1 px-2 py-1 rounded hover:bg-white/5 transition-colors cursor-pointer"
          >
            <Plus className="w-3 h-3" /> Add
          </button>
        )}
      </div>

      {/* NKA badge — green = explicitly confirmed clear */}
      {nka && allergies.length === 0 && (
        <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 px-3 py-2 mb-2 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-300" />
          <p className="text-xs text-emerald-200 font-semibold">
            No Known Allergies (confirmed)
          </p>
        </div>
      )}

      {/* Allergy list */}
      {allergies.length > 0 ? (
        <ul className="space-y-1.5">
          {allergies.map((a) => (
            <AllergyRow key={a.id} allergy={a} onDelete={handleDelete} pending={pending} />
          ))}
        </ul>
      ) : !nka ? (
        <p className="text-xs text-slate-500 italic">
          Not yet recorded. Click Add or mark No Known Allergies.
        </p>
      ) : null}

      {/* Add form */}
      {isAdding && (
        <div className="mt-3 rounded-lg bg-slate-900/50 border border-blue-400/30 p-3 space-y-2">
          <input
            value={allergen}
            onChange={(e) => setAllergen(e.target.value)}
            placeholder="Allergen (e.g. Penicillin, Latex, NSAIDs)"
            className="w-full bg-slate-800/60 text-white text-sm px-2.5 py-1.5 rounded border border-white/10 focus:border-blue-400 outline-none"
            autoFocus
          />
          <input
            value={reaction}
            onChange={(e) => setReaction(e.target.value)}
            placeholder="Reaction (optional, e.g. anaphylaxis, hives)"
            className="w-full bg-slate-800/60 text-white text-sm px-2.5 py-1.5 rounded border border-white/10 focus:border-blue-400 outline-none"
          />
          <div className="flex gap-2">
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value as Severity)}
              className="bg-slate-800/60 text-white text-sm px-2.5 py-1.5 rounded border border-white/10 focus:border-blue-400 outline-none"
            >
              <option value="UNKNOWN">Severity: unknown</option>
              <option value="MILD">Mild</option>
              <option value="MODERATE">Moderate</option>
              <option value="SEVERE">Severe</option>
            </select>
            <input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Notes (optional)"
              className="flex-1 bg-slate-800/60 text-white text-sm px-2.5 py-1.5 rounded border border-white/10 focus:border-blue-400 outline-none"
            />
          </div>
          {error && <p className="text-xs text-red-400">{error}</p>}
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => {
                reset();
                setIsAdding(false);
              }}
              disabled={pending}
              className="px-3 py-1.5 rounded text-xs text-slate-300 hover:bg-white/5 cursor-pointer disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleAdd}
              disabled={pending}
              className="px-3 py-1.5 rounded text-xs font-semibold bg-gradient-to-r from-red-500 to-red-600 hover:from-red-400 hover:to-red-500 text-white cursor-pointer disabled:opacity-50"
            >
              {pending ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Add allergy'}
            </button>
          </div>
        </div>
      )}

      {/* NKA toggle (only when no allergies are listed) */}
      {!isAdding && allergies.length === 0 && (
        <button
          onClick={handleToggleNka}
          disabled={pending}
          className="mt-2 w-full px-3 py-1.5 rounded text-xs text-slate-300 border border-white/10 hover:border-emerald-500/40 hover:text-emerald-300 hover:bg-emerald-500/5 transition-colors cursor-pointer disabled:opacity-50"
        >
          {nka ? '✗ Unmark No Known Allergies' : '✓ Mark No Known Allergies'}
        </button>
      )}

      {error && !isAdding && <p className="text-xs text-red-400 mt-2">{error}</p>}
    </div>
  );
}

const SEVERITY_STYLE: Record<Severity, { bg: string; text: string; label: string }> = {
  SEVERE:   { bg: 'bg-red-500/20',     text: 'text-red-200',     label: 'SEVERE' },
  MODERATE: { bg: 'bg-amber-500/20',   text: 'text-amber-200',   label: 'Moderate' },
  MILD:     { bg: 'bg-yellow-500/15',  text: 'text-yellow-200',  label: 'Mild' },
  UNKNOWN:  { bg: 'bg-slate-500/15',   text: 'text-slate-300',   label: 'Unknown' },
};

function AllergyRow({
  allergy,
  onDelete,
  pending,
}: {
  allergy: AllergyView;
  onDelete: (id: string) => void;
  pending: boolean;
}) {
  const sev = SEVERITY_STYLE[allergy.severity as Severity] ?? SEVERITY_STYLE.UNKNOWN;
  return (
    <li className="flex items-start gap-2 py-1.5 px-2 rounded hover:bg-white/5 group">
      <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold mt-0.5 shrink-0 ${sev.bg} ${sev.text}`}>
        {sev.label}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-white font-medium leading-tight">{allergy.allergen}</p>
        {allergy.reaction && (
          <p className="text-xs text-slate-400 leading-tight mt-0.5">→ {allergy.reaction}</p>
        )}
        {allergy.notes && (
          <p className="text-[11px] text-slate-500 italic mt-0.5">{allergy.notes}</p>
        )}
      </div>
      <button
        onClick={() => onDelete(allergy.id)}
        disabled={pending}
        className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 transition-all p-1 cursor-pointer disabled:cursor-not-allowed"
        title="Delete allergy"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </li>
  );
}

// ---------------------------------------------------------------------------
// MEDICATIONS CARD
// ---------------------------------------------------------------------------

function MedicationsCard({
  patientId,
  meds,
  setMeds,
  activeCount,
  inactiveCount,
}: {
  patientId: string;
  meds: MedicationView[];
  setMeds: React.Dispatch<React.SetStateAction<MedicationView[]>>;
  activeCount: number;
  inactiveCount: number;
}) {
  const [isAdding, setIsAdding] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  const [name, setName] = useState('');
  const [dosage, setDosage] = useState('');
  const [frequency, setFrequency] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const reset = () => {
    setName('');
    setDosage('');
    setFrequency('');
    setNotes('');
    setError(null);
  };

  const visible = showInactive ? meds : meds.filter((m) => m.isActive);

  const handleAdd = () => {
    if (!name.trim()) {
      setError('Medication name is required');
      return;
    }
    startTransition(async () => {
      const result = await addMedicationAction({
        patientId,
        name: name.trim(),
        dosage: dosage.trim() || null,
        frequency: frequency.trim() || null,
        notes: notes.trim() || null,
      });
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setMeds((prev) => [result.data, ...prev]);
      reset();
      setIsAdding(false);
    });
  };

  const handleDelete = (id: string) => {
    if (!confirm('Delete this medication? This is recorded in the audit log.')) return;
    startTransition(async () => {
      const result = await deleteMedicationAction(id, patientId);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setMeds((prev) => prev.filter((m) => m.id !== id));
    });
  };

  const handleToggleActive = (med: MedicationView) => {
    startTransition(async () => {
      const result = await updateMedicationAction(med.id, patientId, {
        isActive: !med.isActive,
      });
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setMeds((prev) => prev.map((m) => (m.id === med.id ? result.data : m)));
    });
  };

  // When toggling inactive view, fetch fresh inactive meds if we don't have
  // them in local state yet.
  const handleToggleShowInactive = async () => {
    const next = !showInactive;
    setShowInactive(next);
    if (next && inactiveCount > 0) {
      const result = await listMedicationsAction(patientId, true);
      if (result.ok) setMeds(result.data);
    }
  };

  return (
    <div className="rounded-xl bg-white/5 backdrop-blur-md border border-white/10 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-blue-500/15 border border-blue-500/30">
            <Pill className="w-4 h-4 text-blue-300" />
          </div>
          <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
            Medications
          </h2>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10">
            {activeCount} active
          </span>
        </div>
        {!isAdding && (
          <button
            onClick={() => setIsAdding(true)}
            className="text-[11px] text-slate-300 hover:text-white flex items-center gap-1 px-2 py-1 rounded hover:bg-white/5 transition-colors cursor-pointer"
          >
            <Plus className="w-3 h-3" /> Add
          </button>
        )}
      </div>

      {visible.length > 0 ? (
        <ul className="space-y-1.5">
          {visible.map((m) => (
            <MedicationRow
              key={m.id}
              med={m}
              onDelete={handleDelete}
              onToggleActive={handleToggleActive}
              pending={pending}
            />
          ))}
        </ul>
      ) : (
        <p className="text-xs text-slate-500 italic">No active medications recorded.</p>
      )}

      {/* Add form */}
      {isAdding && (
        <div className="mt-3 rounded-lg bg-slate-900/50 border border-blue-400/30 p-3 space-y-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Medication name (e.g. Oxycodone, Gabapentin)"
            className="w-full bg-slate-800/60 text-white text-sm px-2.5 py-1.5 rounded border border-white/10 focus:border-blue-400 outline-none"
            autoFocus
          />
          <div className="flex gap-2">
            <input
              value={dosage}
              onChange={(e) => setDosage(e.target.value)}
              placeholder="Dosage (e.g. 5mg)"
              className="flex-1 bg-slate-800/60 text-white text-sm px-2.5 py-1.5 rounded border border-white/10 focus:border-blue-400 outline-none"
            />
            <input
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              placeholder="Frequency (e.g. twice daily, PRN)"
              className="flex-1 bg-slate-800/60 text-white text-sm px-2.5 py-1.5 rounded border border-white/10 focus:border-blue-400 outline-none"
            />
          </div>
          <input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Notes (optional, e.g. prescriber, indication)"
            className="w-full bg-slate-800/60 text-white text-sm px-2.5 py-1.5 rounded border border-white/10 focus:border-blue-400 outline-none"
          />
          {error && <p className="text-xs text-red-400">{error}</p>}
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => {
                reset();
                setIsAdding(false);
              }}
              disabled={pending}
              className="px-3 py-1.5 rounded text-xs text-slate-300 hover:bg-white/5 cursor-pointer disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleAdd}
              disabled={pending}
              className="px-3 py-1.5 rounded text-xs font-semibold bg-gradient-to-r from-blue-500 to-teal-500 hover:from-blue-400 hover:to-teal-400 text-white cursor-pointer disabled:opacity-50"
            >
              {pending ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Add medication'}
            </button>
          </div>
        </div>
      )}

      {/* Inactive toggle */}
      {inactiveCount > 0 && !isAdding && (
        <button
          onClick={handleToggleShowInactive}
          className="mt-2 w-full text-[11px] text-slate-400 hover:text-white flex items-center justify-center gap-1.5 py-1 rounded hover:bg-white/5 transition-colors cursor-pointer"
        >
          {showInactive ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
          {showInactive ? 'Hide inactive' : `Show inactive (${inactiveCount})`}
        </button>
      )}

      {error && !isAdding && <p className="text-xs text-red-400 mt-2">{error}</p>}
    </div>
  );
}

function MedicationRow({
  med,
  onDelete,
  onToggleActive,
  pending,
}: {
  med: MedicationView;
  onDelete: (id: string) => void;
  onToggleActive: (med: MedicationView) => void;
  pending: boolean;
}) {
  const isInactive = !med.isActive;
  return (
    <li
      className={`flex items-start gap-2 py-1.5 px-2 rounded hover:bg-white/5 group ${
        isInactive ? 'opacity-50' : ''
      }`}
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm text-white font-medium leading-tight">
          {med.name}
          {med.dosage && <span className="text-slate-400 font-normal"> {med.dosage}</span>}
          {isInactive && (
            <span className="ml-2 text-[10px] text-slate-500 uppercase tracking-wider">stopped</span>
          )}
        </p>
        {med.frequency && (
          <p className="text-xs text-slate-400 leading-tight mt-0.5">{med.frequency}</p>
        )}
        {med.notes && (
          <p className="text-[11px] text-slate-500 italic mt-0.5">{med.notes}</p>
        )}
      </div>
      <div className="opacity-0 group-hover:opacity-100 transition-all flex items-center gap-1">
        <button
          onClick={() => onToggleActive(med)}
          disabled={pending}
          className="text-slate-500 hover:text-blue-300 p-1 cursor-pointer disabled:cursor-not-allowed"
          title={med.isActive ? 'Mark as stopped' : 'Resume as active'}
        >
          {med.isActive ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
        </button>
        <button
          onClick={() => onDelete(med.id)}
          disabled={pending}
          className="text-slate-500 hover:text-red-400 p-1 cursor-pointer disabled:cursor-not-allowed"
          title="Delete medication"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </li>
  );
}
