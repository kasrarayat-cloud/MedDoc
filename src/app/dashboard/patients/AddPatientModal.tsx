'use client';

import { useState, useEffect, useTransition, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Loader2,
  AlertCircle,
  CheckCircle2,
  UserPlus,
  Mic,
  MicOff,
  Sparkles,
} from 'lucide-react';
import {
  createPatientAction,
  getNextChartIdAction,
  listPracticeDoctorsAction,
  type DoctorOption,
} from './actions';
import { useVoiceRecorder } from '@/lib/hooks/useVoiceRecorder';
import {
  emptyPatientProfile,
  profileToPayload,
  type PatientProfileFormState,
  type PatientSex,
} from './patient-form-shared';
import InsuranceStatusToggle from './InsuranceStatusToggle';

// Response shape from /api/patients/extract-from-voice. Every field
// nullable — null means "doctor didn't mention it", leave the form alone.

interface ExtractedFields {
  firstName: string | null;
  lastName: string | null;
  mrn: string | null;
  chartId: string | null;
  birthYear: number | null;
  email: string | null;
  cellPhone: string | null;
  homePhone: string | null;
  insuranceVerified: boolean | null;
  sex: PatientSex | null;
  addressLine1: string | null;
  addressLine2: string | null;
  city: string | null;
  state: string | null;
  postalCode: string | null;
  pharmacyName: string | null;
  pharmacyPhone: string | null;
  assignedDoctorName: string | null;
  tags: string[] | null;
  briefHistory: string[] | null;
}

interface AddPatientModalProps {
  open: boolean;
  onClose: () => void;
}

interface FormState extends PatientProfileFormState {
  // Add-specific extensions on top of the shared profile shape. Any
  // field listed here lives ONLY in the Add flow — if you need it on
  // Edit too, put it in PatientProfileFormState instead.
  assignedDoctorId: string;
  /** Free-text intake note; split on newlines and filtered at submit to
   *  become the first briefHistory[] entries. One line per item. */
  initialHistory: string;
}

const initialState: FormState = {
  ...emptyPatientProfile(),
  assignedDoctorId: '',
  initialHistory: '',
};

// Outer wrapper: AnimatePresence owns the open/close toggle. Form state
// lives in the inner Content component so each open mounts a fresh tree
// (state initialized via useState defaults — no reset effect needed,
// satisfies React 19's set-state-in-effect rule).
export default function AddPatientModal({ open, onClose }: AddPatientModalProps) {
  return (
    <AnimatePresence>
      {open && <AddPatientModalContent onClose={onClose} />}
    </AnimatePresence>
  );
}

function AddPatientModalContent({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [form, setForm] = useState<FormState>(initialState);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [success, setSuccess] = useState(false);
  /** The next auto-generated chart ID for this practice, shown as a
   *  placeholder hint. Empty while loading or on error — we degrade to
   *  the static sample placeholder. If the user leaves the field blank
   *  at submit, the server regenerates (source of truth) so this value
   *  is advisory only. */
  const [suggestedChartId, setSuggestedChartId] = useState('');
  /** Doctors in the caller's practice, loaded once on mount for the
   *  Assigned Provider dropdown. Empty while loading or on error —
   *  the select degrades to a disabled "No doctors available" option. */
  const [doctors, setDoctors] = useState<DoctorOption[]>([]);
  // Ref on the scrollable form body so a voice-fill result can snap the
  // user to the top — otherwise, on a long form that was scrolled down,
  // the result banner lives above the viewport and feels like "nothing
  // happened" or "the form disappeared".
  const formBodyRef = useRef<HTMLFormElement | null>(null);

  // Voice-fill state — separate from createPatient flow so a voice pass
  // in flight doesn't block the Cancel button and vice versa. `voiceNote`
  // shows the transcript as a subtle banner after fill; it clears on
  // close/success.
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [voiceNote, setVoiceNote] = useState<{
    transcript: string;
    filledCount: number;
    /** Form state snapshot from just BEFORE the voice fill applied. The
     *  Undo button restores this so a misheard utterance is one click to
     *  revert. Null after dismiss/submit. */
    previousForm: FormState;
  } | null>(null);

  // Merge helper: only overwrite form fields the model actually extracted
  // (non-null). That way a second voice pass can additively fill blanks
  // without wiping what the first pass got right. Also derives phoneLast4
  // from cellPhone when the model returned one.
  //
  // Returns the count of fields that will change. Count is computed BEFORE
  // the setForm call so the caller gets a truthful number — React's
  // setForm updater runs asynchronously during the next render commit,
  // so reading a counter mutated inside the updater gives 0 every time
  // (root cause of the phantom "nothing matched" banner).
  const applyExtractedFields = useCallback((fields: ExtractedFields): number => {
    // Resolve assignedDoctorName → id against the loaded doctor list.
    // Computed here so we count it correctly AND pass the resolved id
    // into the setForm updater.
    let resolvedDoctorId: string | null = null;
    if (fields.assignedDoctorName) {
      const wanted = fields.assignedDoctorName
        .replace(/^(dr\.?|doctor)\s+/i, '')
        .trim()
        .toLowerCase();
      const match = doctors.find((d) => {
        const n = (d.name ?? '').replace(/^(dr\.?|doctor)\s+/i, '').trim().toLowerCase();
        return n === wanted;
      });
      if (match) resolvedDoctorId = match.id;
    }

    // First: count what we're about to change. Each branch mirrors the
    // guard used in the updater below — keep these in sync.
    let filled = 0;
    if (fields.firstName) filled++;
    if (fields.lastName) filled++;
    if (fields.mrn) filled++;
    if (fields.chartId) filled++;
    if (fields.birthYear) filled++;
    if (fields.email) filled++;
    if (fields.cellPhone) filled++;
    if (fields.homePhone) filled++;
    if (fields.insuranceVerified !== null) filled++;
    if (fields.tags && fields.tags.length > 0) filled++;
    if (fields.sex && fields.sex !== 'UNKNOWN') filled++;
    if (fields.addressLine1) filled++;
    if (fields.addressLine2) filled++;
    if (fields.city) filled++;
    if (fields.state) filled++;
    if (fields.postalCode) filled++;
    if (fields.pharmacyName) filled++;
    if (fields.pharmacyPhone) filled++;
    if (fields.briefHistory && fields.briefHistory.length > 0) filled++;
    if (resolvedDoctorId) filled++;

    setForm((prev) => {
      const next = { ...prev };
      if (fields.firstName) next.firstName = fields.firstName;
      if (fields.lastName) next.lastName = fields.lastName;
      if (fields.mrn) next.mrn = fields.mrn;
      if (fields.chartId) next.chartId = fields.chartId;
      if (fields.birthYear) next.birthYear = String(fields.birthYear);
      if (fields.email) next.email = fields.email;
      if (fields.cellPhone) {
        next.cellPhone = fields.cellPhone;
        const last4 = fields.cellPhone.replace(/\D/g, '').slice(-4);
        if (last4) next.phoneLast4 = last4;
      }
      if (fields.homePhone) next.homePhone = fields.homePhone;
      if (fields.insuranceVerified !== null) next.insuranceVerified = fields.insuranceVerified;
      if (fields.tags && fields.tags.length > 0) next.tags = fields.tags.join(', ');
      if (fields.sex && fields.sex !== 'UNKNOWN') next.sex = fields.sex;
      if (fields.addressLine1) next.addressLine1 = fields.addressLine1;
      if (fields.addressLine2) next.addressLine2 = fields.addressLine2;
      if (fields.city) next.city = fields.city;
      if (fields.state) next.state = fields.state.toUpperCase().slice(0, 2);
      if (fields.postalCode) next.postalCode = fields.postalCode;
      if (fields.pharmacyName) next.pharmacyName = fields.pharmacyName;
      if (fields.pharmacyPhone) next.pharmacyPhone = fields.pharmacyPhone;
      if (fields.briefHistory && fields.briefHistory.length > 0) {
        // Append so a second voice pass adds to what's there.
        const existing = next.initialHistory.trim();
        const joined = fields.briefHistory.filter((s) => s.trim()).join('\n');
        next.initialHistory = existing ? `${existing}\n${joined}` : joined;
      }
      if (resolvedDoctorId) next.assignedDoctorId = resolvedDoctorId;
      return next;
    });

    // Clear any stale field errors on fields we just filled — they'll be
    // re-validated at submit. Batched as one setState to avoid flash.
    setFieldErrors((prev) => {
      const next = { ...prev };
      for (const key of Object.keys(fields) as (keyof ExtractedFields)[]) {
        if (fields[key] !== null) delete next[key];
      }
      return next;
    });
    return filled;
  }, [doctors]);

  // When VAD auto-stops the recorder, post the blob to the extractor.
  // Reads the latest form state via the setter-closure pattern so the
  // snapshot sent to the server is current at the moment of the POST
  // (not whatever was there when the handler was created).
  const handleAudioBlob = useCallback(
    async (blob: Blob | null) => {
      if (!blob || blob.size < 100) {
        setVoiceError('Didn\u2019t catch that. Try again.');
        setVoiceBusy(false);
        return;
      }
      // Snapshot the current form state so the model can compute edits
      // ("change the email to X") against real values. Uses the setter-
      // closure trick to read state without re-declaring the callback
      // every render.
      const snapshot = await new Promise<FormState>((resolve) => {
        setForm((prev) => {
          resolve(prev);
          return prev;
        });
      });
      const currentFields = {
        firstName: snapshot.firstName || null,
        lastName: snapshot.lastName || null,
        mrn: snapshot.mrn || null,
        chartId: snapshot.chartId || null,
        birthYear: snapshot.birthYear ? parseInt(snapshot.birthYear, 10) : null,
        email: snapshot.email || null,
        cellPhone: snapshot.cellPhone || null,
        homePhone: snapshot.homePhone || null,
        insuranceVerified: snapshot.insuranceVerified,
        sex: snapshot.sex === 'UNKNOWN' ? null : snapshot.sex,
        addressLine1: snapshot.addressLine1 || null,
        addressLine2: snapshot.addressLine2 || null,
        city: snapshot.city || null,
        state: snapshot.state || null,
        postalCode: snapshot.postalCode || null,
        pharmacyName: snapshot.pharmacyName || null,
        pharmacyPhone: snapshot.pharmacyPhone || null,
        tags: snapshot.tags
          ? snapshot.tags.split(',').map((t) => t.trim()).filter(Boolean)
          : null,
        briefHistory: snapshot.initialHistory
          ? snapshot.initialHistory.split('\n').map((s) => s.trim()).filter(Boolean)
          : null,
      };
      setVoiceBusy(true);
      setVoiceError(null);
      try {
        const fd = new FormData();
        fd.append('audio', blob, 'intake.webm');
        fd.append('currentFields', JSON.stringify(currentFields));
        // Send doctor display names so the extractor can emit a valid
        // one verbatim. We resolve name → id on the client after the
        // response comes back.
        fd.append(
          'doctors',
          JSON.stringify(doctors.map((d) => d.name || d.email).filter(Boolean))
        );
        const res = await fetch('/api/patients/extract-from-voice', {
          method: 'POST',
          body: fd,
        });
        const data = (await res.json()) as
          | { ok: true; transcript: string; fields: ExtractedFields }
          | { ok: false; error: string };
        if (!data.ok) {
          setVoiceError(data.error || 'Voice extraction failed.');
          return;
        }
        const filled = applyExtractedFields(data.fields);
        if (!data.transcript) {
          setVoiceError('Didn\u2019t catch that. Try again.');
          return;
        }
        // `snapshot` was captured above — stash it so Undo can restore
        // exactly the pre-fill state. Always keep the newest transcript
        // even when filled === 0 so the user sees what the mic heard.
        setVoiceNote({
          transcript: data.transcript,
          filledCount: filled,
          previousForm: snapshot,
        });
        // Scroll the form back to the top so the fill banner is on-screen.
        // Without this, a long form scrolled down shows no visible change
        // after a voice pass and it feels like the modal bugged out.
        requestAnimationFrame(() => {
          formBodyRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Voice extraction failed.';
        setVoiceError(message);
      } finally {
        setVoiceBusy(false);
      }
    },
    [applyExtractedFields, doctors]
  );

  const voice = useVoiceRecorder({
    // Dictation-friendly gap: 1.8s was triggering mid-thought on natural
    // pauses ("birth year is… 1978"). 4s gives the user room to think
    // between fields without losing the "speak the whole form" flow.
    // The Stop chip is still one tap away if they want to end sooner.
    silenceTimeoutMs: 2500,
    // Long enough for a full intake in one breath (name, DOB, address,
    // pharmacy, phones, insurance, history) without the hard cap cutting
    // them off. 2 min is well under Whisper's 25 MB input ceiling at
    // webm bitrates.
    maxDurationMs: 120_000,
    onAutoStop: handleAudioBlob,
  });

  const handleMicClick = useCallback(async () => {
    if (voiceBusy) return;
    setVoiceError(null);
    if (voice.isRecording) {
      // Manual stop — resolve the blob inline since onAutoStop only fires
      // on VAD, not on explicit stop().
      const blob = await voice.stop();
      void handleAudioBlob(blob);
    } else {
      await voice.start();
    }
  }, [voice, voiceBusy, handleAudioBlob]);

  // Fetch the next chart ID for the placeholder on mount. Non-blocking —
  // if it fails the modal still works; server will auto-generate.
  useEffect(() => {
    let cancelled = false;
    getNextChartIdAction()
      .then((r) => {
        if (!cancelled && r.ok) setSuggestedChartId(r.data.chartId);
      })
      .catch(() => { /* swallow; not critical */ });
    return () => { cancelled = true; };
  }, []);

  // Fetch doctors for the assigned-provider dropdown. Same non-blocking
  // contract as chart-ID — if it fails the field is just empty.
  useEffect(() => {
    let cancelled = false;
    listPracticeDoctorsAction()
      .then((r) => {
        if (!cancelled && r.ok) setDoctors(r.data);
      })
      .catch((err) => {
        console.warn('[AddPatientModal] listPracticeDoctors failed:', err);
      });
    return () => { cancelled = true; };
  }, []);

  // Close on ESC
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (fieldErrors[key]) {
      const next = { ...fieldErrors };
      delete next[key];
      setFieldErrors(next);
    }
  };

  // Cell phone changes also auto-derive `phoneLast4` from the last 4 digits
  // (stripping spaces/dashes/parens). Fully clearing the cell phone leaves
  // the existing phoneLast4 alone — supports the "no cell, manual last-4
  // entry" case the field was originally designed for.
  const handleCellPhoneChange = (value: string) => {
    const digits = value.replace(/\D/g, '');
    const derivedLast4 = digits.slice(-4);
    setForm((prev) => ({
      ...prev,
      cellPhone: value,
      phoneLast4: derivedLast4 || prev.phoneLast4,
    }));
    if (fieldErrors.cellPhone || fieldErrors.phoneLast4) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next.cellPhone;
        delete next.phoneLast4;
        return next;
      });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});

    // Build payload — convert empty strings to null so the server sees a
    // clean shape. `insuranceVerified` stays as the boolean checkbox state;
    // we send false explicitly (it's meaningful: "unverified on file")
    // rather than dropping it when unchecked.
    // Profile fields use the shared converter so Edit + Add stay in sync.
    // Add-only fields are spread on after.
    const payload = {
      ...profileToPayload(form),
      assignedDoctorId: form.assignedDoctorId || null,
      briefHistory: form.initialHistory
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean),
    };

    startTransition(async () => {
      const result = await createPatientAction(payload);

      if (!result.ok) {
        setError(result.error);
        if (result.fieldErrors) {
          setFieldErrors(result.fieldErrors);
        }
        return;
      }

      // Success
      setSuccess(true);
      router.refresh();

      // Close after a brief success animation
      setTimeout(() => {
        onClose();
      }, 1000);
    });
  };

  return (
    <>
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm"
      />

      {/* Modal panel */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-patient-title"
            className="fixed inset-0 z-[101] flex items-center justify-center p-4 pointer-events-none"
          >
            <div className="pointer-events-auto w-full max-w-2xl rounded-2xl bg-[#0A192F] border border-white/10 shadow-2xl shadow-black/50 overflow-hidden">
              {/* Header */}
              <div className="relative px-6 py-4 border-b border-white/10 bg-gradient-to-r from-blue-500/10 to-teal-500/10">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-blue-500/20 border border-blue-500/30">
                    <UserPlus className="w-5 h-5 text-blue-300" />
                  </div>
                  <div>
                    <h2 id="add-patient-title" className="text-lg font-bold text-white">
                      Add New Patient
                    </h2>
                    <p className="text-xs text-slate-400">
                      Create a new patient record in the CRM
                    </p>
                  </div>
                </div>
                {/* Voice-fill mic. Docked next to the close button so the
                    user always finds it in the same spot. Label switches
                    by state so screen readers and tooltips tell the story. */}
                <button
                  type="button"
                  onClick={handleMicClick}
                  disabled={voiceBusy || isPending}
                  className={`absolute top-3 right-12 inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                    voice.isRecording
                      ? 'bg-red-500/20 text-red-300 border border-red-500/40 animate-pulse'
                      : voiceBusy
                        ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
                        : 'bg-white/5 text-slate-300 border border-white/10 hover:bg-white/10 hover:text-white'
                  }`}
                  aria-label={
                    voice.isRecording
                      ? 'Stop recording'
                      : voiceBusy
                        ? 'Extracting fields from voice'
                        : 'Dictate patient details'
                  }
                  title={
                    voice.isRecording
                      ? 'Tap to stop'
                      : voiceBusy
                        ? 'Transcribing…'
                        : 'Fill by voice'
                  }
                >
                  {voiceBusy ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Transcribing…</span>
                    </>
                  ) : voice.isRecording ? (
                    <>
                      <MicOff className="w-3.5 h-3.5" />
                      <span>Stop</span>
                    </>
                  ) : (
                    <>
                      <Mic className="w-3.5 h-3.5" />
                      <span>Voice</span>
                    </>
                  )}
                </button>
                <button
                  onClick={onClose}
                  className="absolute top-3 right-3 p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
                  aria-label="Close"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Body / Form */}
              <form ref={formBodyRef} onSubmit={handleSubmit} className="px-6 py-5 space-y-4 max-h-[70vh] overflow-y-auto">
                {/* Error banner */}
                {error && !success && (
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                    <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                    <p className="text-xs text-red-300">{error}</p>
                  </div>
                )}

                {/* Success banner */}
                {success && (
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <p className="text-xs text-emerald-300">
                      Patient created successfully!
                    </p>
                  </div>
                )}

                {/* Voice status banners. Error and fill-note are mutually
                    exclusive — a successful fill clears the error, a new
                    recording clears the old fill note. */}
                {voiceError && !success && (
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
                    <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                    <p className="text-xs text-amber-200">{voiceError}</p>
                  </div>
                )}
                {voiceNote && !voiceError && !success && (
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-500/10 border border-blue-500/30">
                    <Sparkles className="w-4 h-4 text-blue-300 shrink-0 mt-0.5" />
                    <div className="text-xs text-blue-200 min-w-0 flex-1">
                      <p className="font-semibold">
                        {voiceNote.filledCount > 0
                          ? `Voice filled ${voiceNote.filledCount} ${
                              voiceNote.filledCount === 1 ? 'field' : 'fields'
                            } — review below.`
                          : 'Voice: nothing matched — try again.'}
                      </p>
                      <p className="mt-1 text-[11px] text-blue-300/80 italic truncate">
                        “{voiceNote.transcript}”
                      </p>
                    </div>
                    {voiceNote.filledCount > 0 && (
                      <button
                        type="button"
                        onClick={() => {
                          if (voiceNote.previousForm) {
                            setForm(voiceNote.previousForm);
                          }
                          setVoiceNote(null);
                        }}
                        className="text-[11px] font-semibold text-blue-200 hover:text-white bg-blue-500/20 border border-blue-500/40 hover:bg-blue-500/30 px-2 py-0.5 rounded transition-colors"
                        aria-label="Undo voice fill"
                      >
                        Undo
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => setVoiceNote(null)}
                      className="text-blue-300 hover:text-white p-0.5"
                      aria-label="Dismiss"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}

                {/* Name row */}
                <div className="grid grid-cols-2 gap-3">
                  <Field
                    label="First Name *"
                    error={fieldErrors.firstName?.[0]}
                  >
                    <input
                      type="text"
                      value={form.firstName}
                      onChange={(e) => update('firstName', e.target.value)}
                      required
                      disabled={isPending}
                      placeholder="Sarah"
                      className="input-styled"
                    />
                  </Field>
                  <Field
                    label="Last Name *"
                    error={fieldErrors.lastName?.[0]}
                  >
                    <input
                      type="text"
                      value={form.lastName}
                      onChange={(e) => update('lastName', e.target.value)}
                      required
                      disabled={isPending}
                      placeholder="Mitchell"
                      className="input-styled"
                    />
                  </Field>
                </div>

                {/* IDs row — Chart ID + MRN, evenly spanned. */}
                <div className="grid grid-cols-2 gap-3">
                  <Field
                    label="Chart ID"
                    error={fieldErrors.chartId?.[0]}
                    hint={suggestedChartId ? `Leave blank to auto-assign ${suggestedChartId}` : 'Leave blank to auto-assign'}
                  >
                    <input
                      type="text"
                      value={form.chartId}
                      onChange={(e) => update('chartId', e.target.value)}
                      disabled={isPending}
                      placeholder={suggestedChartId || 'C-1001'}
                      className="input-styled font-mono"
                    />
                  </Field>
                  <Field label="MRN" error={fieldErrors.mrn?.[0]} hint="For filings">
                    <input
                      type="text"
                      value={form.mrn}
                      onChange={(e) => update('mrn', e.target.value)}
                      disabled={isPending}
                      placeholder="MRN-440182"
                      className="input-styled font-mono"
                    />
                  </Field>
                </div>

                {/* Birth year + phone (last 4) row */}
                <div className="grid grid-cols-2 gap-3">
                  <Field
                    label="Birth Year"
                    error={fieldErrors.birthYear?.[0]}
                    hint="Year only (HIPAA Safe Harbor)"
                  >
                    <input
                      type="number"
                      value={form.birthYear}
                      onChange={(e) => update('birthYear', e.target.value)}
                      disabled={isPending}
                      placeholder="1978"
                      min="1900"
                      max={new Date().getFullYear()}
                      className="input-styled"
                    />
                  </Field>
                  <Field
                    label="Phone (last 4)"
                    error={fieldErrors.phoneLast4?.[0]}
                    hint="Minimal-PHI fallback"
                  >
                    <input
                      type="text"
                      value={form.phoneLast4}
                      onChange={(e) =>
                        update('phoneLast4', e.target.value.replace(/\D/g, '').slice(0, 4))
                      }
                      disabled={isPending}
                      placeholder="4421"
                      maxLength={4}
                      className="input-styled font-mono"
                    />
                  </Field>
                </div>

                {/* Cell + home phone — two columns */}
                <div className="grid grid-cols-2 gap-3">
                  <Field
                    label="Cell Phone"
                    error={fieldErrors.cellPhone?.[0]}
                    hint="Auto-fills last-4 below"
                  >
                    <input
                      type="tel"
                      value={form.cellPhone}
                      onChange={(e) => handleCellPhoneChange(e.target.value)}
                      disabled={isPending}
                      placeholder="(555) 123-4421"
                      maxLength={32}
                      className="input-styled font-mono"
                    />
                  </Field>
                  <Field label="Home Phone" error={fieldErrors.homePhone?.[0]}>
                    <input
                      type="tel"
                      value={form.homePhone}
                      onChange={(e) => update('homePhone', e.target.value)}
                      disabled={isPending}
                      placeholder="(555) 123-0000"
                      maxLength={32}
                      className="input-styled font-mono"
                    />
                  </Field>
                </div>

                {/* Email */}
                <Field label="Email" error={fieldErrors.email?.[0]}>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => update('email', e.target.value)}
                    disabled={isPending}
                    placeholder="patient@example.com"
                    className="input-styled"
                  />
                </Field>

                {/* Sex + Assigned provider — paired clinical context row. */}
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Sex" hint="Clinical context only">
                    <select
                      value={form.sex}
                      onChange={(e) => update('sex', e.target.value as PatientSex)}
                      disabled={isPending}
                      className="input-styled"
                    >
                      <option value="UNKNOWN">Not specified</option>
                      <option value="FEMALE">Female</option>
                      <option value="MALE">Male</option>
                      <option value="OTHER">Other</option>
                    </select>
                  </Field>
                  <Field
                    label="Assigned Provider"
                    error={fieldErrors.assignedDoctorId?.[0]}
                    hint={doctors.length === 0 ? 'No doctors available' : 'Optional'}
                  >
                    <select
                      value={form.assignedDoctorId}
                      onChange={(e) => update('assignedDoctorId', e.target.value)}
                      disabled={isPending || doctors.length === 0}
                      className="input-styled"
                    >
                      <option value="">Unassigned</option>
                      {doctors.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name || d.email}
                        </option>
                      ))}
                    </select>
                  </Field>
                </div>

                {/* Address. Two lines + city/state/zip on one row. Free-text
                    state (US 2-char); loose regex on the server normalizes. */}
                <Field label="Address Line 1" error={fieldErrors.addressLine1?.[0]}>
                  <input
                    type="text"
                    value={form.addressLine1}
                    onChange={(e) => update('addressLine1', e.target.value)}
                    disabled={isPending}
                    placeholder="123 Main St"
                    className="input-styled"
                  />
                </Field>
                <Field
                  label="Address Line 2"
                  error={fieldErrors.addressLine2?.[0]}
                  hint="Apt / suite (optional)"
                >
                  <input
                    type="text"
                    value={form.addressLine2}
                    onChange={(e) => update('addressLine2', e.target.value)}
                    disabled={isPending}
                    placeholder="Apt 4B"
                    className="input-styled"
                  />
                </Field>
                <div className="grid grid-cols-[1fr_80px_110px] gap-3">
                  <Field label="City" error={fieldErrors.city?.[0]}>
                    <input
                      type="text"
                      value={form.city}
                      onChange={(e) => update('city', e.target.value)}
                      disabled={isPending}
                      placeholder="San Francisco"
                      className="input-styled"
                    />
                  </Field>
                  <Field label="State" error={fieldErrors.state?.[0]}>
                    <input
                      type="text"
                      value={form.state}
                      onChange={(e) =>
                        update(
                          'state',
                          e.target.value
                            .replace(/[^A-Za-z]/g, '')
                            .slice(0, 2)
                            .toUpperCase()
                        )
                      }
                      disabled={isPending}
                      placeholder="CA"
                      maxLength={2}
                      className="input-styled font-mono uppercase"
                    />
                  </Field>
                  <Field label="Postal Code" error={fieldErrors.postalCode?.[0]}>
                    <input
                      type="text"
                      value={form.postalCode}
                      onChange={(e) => update('postalCode', e.target.value)}
                      disabled={isPending}
                      placeholder="94103"
                      maxLength={10}
                      className="input-styled font-mono"
                    />
                  </Field>
                </div>

                {/* Preferred pharmacy — relevant for controlled-substance Rx. */}
                <div className="grid grid-cols-[1fr_180px] gap-3">
                  <Field
                    label="Preferred Pharmacy"
                    error={fieldErrors.pharmacyName?.[0]}
                    hint="For e-prescribing"
                  >
                    <input
                      type="text"
                      value={form.pharmacyName}
                      onChange={(e) => update('pharmacyName', e.target.value)}
                      disabled={isPending}
                      placeholder="CVS on Market St"
                      className="input-styled"
                    />
                  </Field>
                  <Field label="Pharmacy Phone" error={fieldErrors.pharmacyPhone?.[0]}>
                    <input
                      type="tel"
                      value={form.pharmacyPhone}
                      onChange={(e) => update('pharmacyPhone', e.target.value)}
                      disabled={isPending}
                      placeholder="(555) 123-0000"
                      maxLength={32}
                      className="input-styled font-mono"
                    />
                  </Field>
                </div>

                {/* Intake note → first briefHistory[] entries. One line per
                    item at submit time (split + trim + filter empty). */}
                <Field
                  label="Intake Note / Brief History"
                  hint="One line per entry. Chief complaint, referral source, relevant history."
                >
                  <textarea
                    value={form.initialHistory}
                    onChange={(e) => update('initialHistory', e.target.value)}
                    disabled={isPending}
                    placeholder="Referred by Dr. Chen for chronic low back pain&#10;Prior LESI series 2024, partial relief"
                    rows={3}
                    className="input-styled resize-y min-h-[70px]"
                  />
                </Field>

                {/* Insurance + Tags — single compact row. Tri-state toggle
                    matches the contact-strip badge on the patient detail
                    page (Verified / Pending / Self-pay). */}
                <div className="grid grid-cols-[auto_1fr] gap-3 items-start">
                  <InsuranceStatusToggle
                    value={form.insuranceVerified}
                    onChange={(v) => update('insuranceVerified', v)}
                    disabled={isPending}
                  />
                  <Field label="Tags" hint="Comma-separated">
                    <input
                      type="text"
                      value={form.tags}
                      onChange={(e) => update('tags', e.target.value)}
                      disabled={isPending}
                      placeholder="post-op, chronic-pain"
                      className="input-styled"
                    />
                  </Field>
                </div>

                {/* HIPAA notice */}
                <div className="text-[10px] text-slate-500 italic border-t border-white/5 pt-3">
                  <strong className="text-slate-400">HIPAA notice:</strong> This action will be
                  logged with your user ID, IP address, and timestamp in the audit trail.
                </div>

                {/* Footer buttons */}
                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={onClose}
                    disabled={isPending}
                    className="px-4 py-2 rounded-lg text-sm font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isPending || success}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-blue-500 to-teal-500 text-white text-sm font-semibold shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    {isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Creating...
                      </>
                    ) : success ? (
                      <>
                        <CheckCircle2 className="w-4 h-4" />
                        Created!
                      </>
                    ) : (
                      <>
                        <UserPlus className="w-4 h-4" />
                        Create Patient
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </motion.div>

          {/* Inline styles helper for input fields (consistency) */}
          <style jsx>{`
            :global(.input-styled) {
              width: 100%;
              padding: 0.5rem 0.75rem;
              border-radius: 0.5rem;
              background-color: rgba(15, 23, 42, 0.6);
              border: 1px solid rgba(255, 255, 255, 0.08);
              color: white;
              font-size: 0.875rem;
              outline: none;
              transition: border-color 0.2s;
            }
            :global(.input-styled::placeholder) {
              color: rgb(100, 116, 139);
            }
            :global(.input-styled:focus) {
              border-color: rgba(59, 130, 246, 0.5);
            }
            :global(.input-styled:disabled) {
              opacity: 0.5;
              cursor: not-allowed;
            }
          `}</style>
    </>
  );
}

// ----------------------------------------------------------------------------
// Field wrapper — label + hint + optional error
// ----------------------------------------------------------------------------
function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  // Wrap children INSIDE the <label> so clicking the label focuses the
  // control and accessibility tools (Playwright's getByLabel, screen
  // readers) can associate the two without an explicit htmlFor/id pair.
  return (
    <label className="block">
      <span className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
        {label.replace(/\s*\*\s*$/, '')}
      </span>
      {children}
      {error ? (
        <p className="text-[10px] text-red-400 mt-1">{error}</p>
      ) : hint ? (
        <p className="text-[10px] text-slate-500 mt-1">{hint}</p>
      ) : null}
    </label>
  );
}
