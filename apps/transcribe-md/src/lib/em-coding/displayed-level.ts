// ============================================================================
// Displayed E/M level — the SINGLE computation behind both the rail and the
// sign gate (2026-06-13, #313 trigger-parity fix).
// ----------------------------------------------------------------------------
// The E/M billing level is never persisted; it is recomputed on-read. TWO
// surfaces show/gate it and they MUST agree:
//
//   • the CodingRail displays `override ?? engine.code`, recomputed from the
//     live note text + the visit's structured icd/rx signals (POST /em-score);
//   • the sign gate (suggestion actions → emPendingChange → /sign) decides
//     whether to force a confirmation by comparing the level before vs after
//     an adoption.
//
// Before this module the two diverged: the /em-score route's rx extractor
// read `rxDrafts.drafts` while the worker writes `rxDrafts.prescriptions`
// (so the rail scored with NO rx signal and could show a note-text-driven
// 99213→99214), while the gate read `prescriptions` and pinned both sides
// equal → the gate computed null and the upcode reached the note WITHOUT a
// confirm dialog (silent upcoding — exactly what the gate exists to stop).
// Additionally the gate compared the raw engine code while the rail showed
// the override-projected code.
//
// `computeDisplayedEmCode` is the ONE projection both surfaces call, with the
// ONE set of extractors below. Same inputs → same code, by construction:
// the rail and the gate cannot disagree.
// ============================================================================

import { computeEmScore } from './score';
import type { EmCode } from './types';
import type { IcdCodeRow, RxDraftRow } from './fallback-mdm';
import type { EmOverride } from '../../lib/em-coding-ui/types';

/** icdCodes jsonb → engine rows. Handles BOTH shapes seen across migrations:
 *  Layer 7a's `{ codes: [{ code, description }] }` AND legacy bare arrays.
 *  (The route handled both; the gate's old copy handled only `{codes}` —
 *  a divergence source.) */
export function extractIcdRows(raw: unknown): IcdCodeRow[] {
  if (!raw) return [];
  if (Array.isArray(raw)) {
    return raw
      .filter((r): r is Record<string, unknown> => !!r && typeof r === 'object')
      .map((r) => ({
        code: typeof r.code === 'string' ? r.code : '',
        description: typeof r.description === 'string' ? r.description : undefined,
      }))
      .filter((r) => r.code.length > 0);
  }
  if (typeof raw === 'object') {
    const blob = raw as { codes?: unknown };
    if (Array.isArray(blob.codes)) return extractIcdRows(blob.codes);
  }
  return [];
}

/** rxDrafts jsonb → engine rows. Reads BOTH the worker's current
 *  `{ prescriptions: [...] }` (Layer 7c) AND the legacy `{ drafts: [...] }`
 *  shape. The route previously read ONLY `drafts` (→ empty for every real
 *  visit, since the worker writes `prescriptions`); the gate previously read
 *  ONLY `prescriptions`. Reading both, in one place, is what locks parity. */
export function extractRxRows(raw: unknown): RxDraftRow[] {
  if (!raw || typeof raw !== 'object') return [];
  const blob = raw as { prescriptions?: unknown; drafts?: unknown };
  const list = Array.isArray(blob.prescriptions)
    ? blob.prescriptions
    : Array.isArray(blob.drafts)
      ? blob.drafts
      : [];
  return list
    .filter((d): d is Record<string, unknown> => !!d && typeof d === 'object')
    .map((d) => ({
      drug:
        typeof d.drug === 'string'
          ? d.drug
          : typeof d.drug_name === 'string'
            ? d.drug_name
            : undefined,
      drug_name: typeof d.drug_name === 'string' ? d.drug_name : undefined,
      action: typeof d.action === 'string' ? d.action : undefined,
    }));
}

/** cptCodes.em.override → the doctor-set override (if any). The rail renders
 *  `override.code ?? suggestedCode`; the gate must apply the SAME projection
 *  or an overridden visit would false-prompt (the engine code can drift
 *  while the displayed/billed code is pinned by the override). */
export function extractEmOverride(raw: unknown): EmOverride | undefined {
  if (typeof raw !== 'object' || raw === null) return undefined;
  const blob = raw as { em?: { override?: unknown } };
  const override = blob.em?.override;
  if (typeof override !== 'object' || override === null) return undefined;
  const o = override as Record<string, unknown>;
  if (typeof o.code !== 'string') return undefined;
  return {
    code: o.code as EmCode,
    reason: typeof o.reason === 'string' ? o.reason : undefined,
    overriddenAt: typeof o.overriddenAt === 'string' ? o.overriddenAt : '',
  };
}

export interface VisitEmSignals {
  /** transcribe_visits.icdCodes jsonb */
  icdCodes: unknown;
  /** transcribe_visits.rxDrafts jsonb */
  rxDrafts: unknown;
  /** transcribe_visits.cptCodes jsonb (for the doctor override) */
  cptCodes: unknown;
}

export interface EmScoreContext {
  practiceId?: string;
  visitId: string;
  userId: string | null;
}

/** The E/M code the doctor actually SEES at sign time for a given note body:
 *  `override ?? engine.code`, scored with the unified extractors. Both the
 *  rail (via POST /em-score → engineToUiScore, whose displayedCode is the
 *  same projection) and the sign gate call THIS — so the value the doctor
 *  reviews and the value the gate guards are identical by construction. */
export async function computeDisplayedEmCode(
  soapText: string,
  signals: VisitEmSignals,
  ctx: EmScoreContext
): Promise<EmCode> {
  const engine = await computeEmScore(soapText, {
    practiceId: ctx.practiceId,
    visitId: ctx.visitId,
    userId: ctx.userId ?? undefined,
    icdCodes: extractIcdRows(signals.icdCodes),
    rxDrafts: extractRxRows(signals.rxDrafts),
  });
  const override = extractEmOverride(signals.cptCodes);
  return override?.code ?? engine.code;
}
