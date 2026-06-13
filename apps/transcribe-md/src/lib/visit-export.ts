// ============================================================================
// Pure visit-export types + helpers (T-M7)
// ----------------------------------------------------------------------------
// This module is safe to import from client components. The Prisma-
// touching loader lives in visit-export-server.ts — keeping it there
// prevents @prisma/adapter-pg from reaching fs/net/tls/dns in the
// client bundle via the ehr-formatters → visit-ready-view import chain.
// ============================================================================

import type { TranscribeVisitStatus } from '@prisma/client';

// ----------------------------------------------------------------------------
// Wire types — duplicated from worker/layers/* so this module can be
// imported from both the web app AND test files without pulling in the
// worker-only modules.
// ----------------------------------------------------------------------------

export interface IcdCode {
  code: string;
  description: string;
  evidence_quote: string;
  confidence: number;
}

export interface CptEm {
  /** The E/M code to PRINT. The export loader projects the authoritative
   *  displayed level onto this field (signed → frozen signedCode; otherwise
   *  override ?? raw) so every artifact prints what the doctor reviewed —
   *  NOT the raw L7b suggestion. See visit-export-server.loadVisitExportData. */
  code: string;
  description: string;
  reasoning: {
    problems: { description: string; status: string }[];
    data: string;
    risk: string;
  };
  evidence_quote: string;
  /** Doctor override set via the override route (cptCodes.em.override). */
  override?: { code: string; reason?: string; overriddenAt?: string };
  /** The displayed E/M level FROZEN at sign time (#315 obs#2 parity fix).
   *  Present on visits signed after 2026-06-13; the authoritative billing
   *  code for a signed visit. */
  signedCode?: string;
}

export interface CptProcedure {
  code: string;
  description: string;
  evidence_quote: string;
}

export interface CptModifier {
  code: string;
  rationale: string;
}

export interface Prescription {
  drug: string;
  strength?: string | null;
  form?: string | null;
  sig?: string | null;
  quantity?: string | null;
  refills?: string | null;
  action:
    | 'new'
    | 'continue'
    | 'increase'
    | 'decrease'
    | 'discontinue'
    | 'unclear';
  evidence_quote: string;
}

export interface RxWarning {
  severity: 'critical' | 'major' | 'minor';
  rx_drug: string;
  message: string;
  evidence_quote?: string | null;
}

export interface Referral {
  to: string;
  reason: string;
  relevant_history: string;
  urgency: 'routine' | 'urgent' | 'stat';
  evidence_quote: string;
}

/**
 * The complete bundle every downstream generator consumes. Nulls are
 * allowed and expected — each generator decides how to handle missing
 * sections (skip vs "not documented").
 */
export interface VisitExportData {
  visitId: string;
  patientName: string | null;
  specialty: string;
  chiefComplaint: string | null;
  status: TranscribeVisitStatus;
  createdAt: Date;
  signedAt: Date | null;

  clinicianName: string | null;
  clinicianEmail: string;

  /** The displayable SOAP: signedSoap when frozen, soapFinal otherwise. */
  soapText: string;

  icdCodes: IcdCode[];
  em: CptEm | null;
  procedures: CptProcedure[];
  modifiers: CptModifier[];
  prescriptions: Prescription[];
  rxWarnings: RxWarning[];
  referrals: Referral[];
  patientSummary: string | null;
}

/** Human-readable short date used in filenames + PDF headers. */
export function formatVisitDate(d: Date): string {
  // ISO-like YYYY-MM-DD is filename-safe + sortable. The PDF header
  // uses a prettier variant; see pdf-generator.ts.
  return d.toISOString().slice(0, 10);
}

/** Filename-safe version of the patient name (or "anonymous"). */
export function filenameSlug(name: string | null | undefined): string {
  const base = (name ?? 'anonymous').trim().toLowerCase();
  return base.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40) ||
    'visit';
}

/** Format a prescription into a single Epic-compatible line. Shared
 *  between clipboard formatters + the PDF/DOCX generators so their Rx
 *  sections stay aligned if one of us changes format conventions later. */
export function prescriptionOneLine(rx: Prescription): string {
  const parts: string[] = [rx.drug];
  if (rx.strength) parts.push(rx.strength);
  if (rx.form) parts.push(rx.form);
  if (rx.sig) parts.push(`– ${rx.sig}`);
  const tail: string[] = [];
  if (rx.quantity) tail.push(`#${rx.quantity}`);
  if (rx.refills) tail.push(`Refills ${rx.refills}`);
  if (tail.length) parts.push(`(${tail.join(', ')})`);
  // Append an uppercase action tag only when it carries information
  // beyond "new Rx" — NEW is implied by context on a fresh note.
  if (rx.action !== 'new') {
    parts.push(`[${rx.action.toUpperCase()}]`);
  }
  return parts.join(' ');
}
