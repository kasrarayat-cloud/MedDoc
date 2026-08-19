// ============================================================================
// F12-g — THE E/M ARTIFACT SCAN. Which production visits carry office-E/M state
// while `emAppliesToVisit` says no?
// ----------------------------------------------------------------------------
// `visits/[id]/page.tsx` writes `emScoredCode` while the verdict is TRUE, and
// NOTHING CLEARS IT WHEN THE VERDICT LATER FLIPS. The same holds for
// `cptCodes.em` and, on a signed record, the frozen `signedCode`. A verdict can
// flip for ordinary reasons — a template is retired, a note body is edited, the
// classifier is corrected (F12-a, F12-d, F12-f all moved it) — so the stale
// state is not a one-off: it is a standing class.
//
// ⚠️ WHY THIS IS A SEPARATE WATCHER FROM `check-imaging-em-artifacts.sh`, AND
// NOT A WIDENING OF IT. That script is `where specialty='ultrasound'` — the
// SPECIALTY axis. The note-shape axis (ruling #123) is a SECOND axis, entirely
// outside its watched set, so its 🟢 is true and covers none of these rows.
// This module reports WHICH axis suppressed each row, so the two watchers'
// relationship is legible rather than assumed:
//
//     suppressedBy 'specialty'  — the imaging watcher already owns this row
//     suppressedBy 'note-shape' — F12-g's class, watched by nothing until now
//
// ⚠️ THE PREDICATE IS NEVER RE-IMPLEMENTED HERE. F12-g's own filing records
// that an SQL re-implementation of `emAppliesToVisit`, with the specialty axis
// approximated, produced **19** where the shipped predicate produces **15**.
// Every verdict below comes from `emAppliesToVisit` itself.
//
// ⚠️ THIS MODULE NEVER SEES A NOTE BODY. Its caller hands it the note's
// markdown HEADING LINES only. That is safe because the extraction filter is a
// strict PREFIX of `NOTE_SECTION_HEADING_RE` — any line the shipped regex would
// accept necessarily matches it — so the heading list this module derives is
// identical to the one it would derive from the whole note. `assertNoBodyText`
// below asserts the other direction (no over-selection), which is a PHI control
// as much as a correctness one.
//
// STRICTLY READ-ONLY, AND DELIBERATELY SO. Clearing a stored clinical column is
// an irreversible production mutation with its own door
// (`scripts/run-ruled-mutation.sh`) and its own §2.5 declaration. The
// disposition of what this finds is a war-room question. F12-g's filing says it
// in as many words: **the first step is a WATCHER, not a mutation.**
// ============================================================================

import { emAppliesToSpecialty } from '@meddoc/shared/specialties';
import { emAppliesToVisit, normalizedNoteHeadings } from './note-shape';

/** THE WATCHED SET, NAMED — so it can be diffed against what F12-g's filing
 *  names, in writing, rather than trusted.
 *
 *  F12-g names three: `emScoredCode`, `cptCodes.em`, and the frozen
 *  `cptCodes.em.signedCode`. `check-imaging-em-artifacts.sh` additionally
 *  watches `emPendingChange`. **This watcher takes the UNION**, because a
 *  pending E/M change stranded on a visit that no longer has an E/M level is
 *  the same defect wearing a fourth column's clothes — and because two watchers
 *  over the same class with different watched sets is how one of them ends up
 *  reporting a true and worthless zero.
 *
 *  `cptCodes.em.override` is watched and is NOT the same finding as the rest:
 *  it is a code a DOCTOR set. Clearing it deletes somebody's recorded clinical
 *  judgement. It is reported under its own name for exactly that reason. */
export const EM_STATE_FIELDS = [
  'emScoredCode',
  'cptCodes.em.code',
  'cptCodes.em.override.code',
  'cptCodes.em.signedCode',
  'emPendingChange',
] as const;

export type EmStateField = (typeof EM_STATE_FIELDS)[number];

/** One production visit, projected. Field-for-field what the extract emits.
 *
 *  ⚠️ `noteHeadingLines` is the note's HEADING LINES, never its body — see the
 *  header. It is `''` for a visit with no note text at all, which is a
 *  different fact from a note with no headings and is NOT distinguished here,
 *  deliberately: both mean "the body says nothing about shape", which is what
 *  the classifier consumes. */
export type EmScanRow = {
  visitId: string;
  specialty: string | null;
  signed: boolean;
  emScoredCode: string | null;
  cptEmCode: string | null;
  cptEmOverrideCode: string | null;
  cptEmSignedCode: string | null;
  emPendingChange: boolean;
  /** `cptCodes.emSuppressed`, informational — whether the system has already
   *  recorded a suppression on this row. Never treated as state. */
  cptEmSuppressed: string | null;
  templateSections: unknown;
  noteHeadingLines: string;
  /** `jsonb_typeof` of the two JSONB columns, so a SHAPE assumption is a
   *  measurement. Null when the column itself is NULL. */
  cptCodesType: string | null;
  templateSectionsType: string | null;
};

/** Which of the watched fields this row actually carries. Empty = clean. */
export function emStateOn(row: EmScanRow): EmStateField[] {
  const on: EmStateField[] = [];
  if (row.emScoredCode) on.push('emScoredCode');
  if (row.cptEmCode) on.push('cptCodes.em.code');
  if (row.cptEmOverrideCode) on.push('cptCodes.em.override.code');
  if (row.cptEmSignedCode) on.push('cptCodes.em.signedCode');
  if (row.emPendingChange) on.push('emPendingChange');
  return on;
}

/** WHICH AXIS SUPPRESSED THIS ROW. Only meaningful when the verdict is false.
 *
 *  The specialty axis is tested the same way `emAppliesToVisit` tests it
 *  FIRST — so a row reading 'specialty' is one the imaging watcher already
 *  owns, and a row reading 'note-shape' is one that only this watcher sees. */
export function suppressingAxis(row: EmScanRow): 'specialty' | 'note-shape' {
  return emAppliesToSpecialty(row.specialty) ? 'note-shape' : 'specialty';
}

export type EmArtifact = {
  visitId: string;
  specialty: string | null;
  signed: boolean;
  axis: 'specialty' | 'note-shape';
  fields: EmStateField[];
  /** True when a SIGNED record carries a frozen code. Never remediable by a
   *  sweep; called out so it cannot be lost in a count. */
  frozenOnSigned: boolean;
};

export type EmScanResult = {
  /** Every bucket the scan can sort a row into. The four are exhaustive and
   *  disjoint by construction, and `total` reconciles against `rows.length` —
   *  anything that does not fit a named bucket would be the finding. */
  buckets: {
    verdictFalseWithState: number;
    verdictFalseClean: number;
    verdictTrueWithState: number;
    verdictTrueClean: number;
  };
  total: number;
  /** `buckets.verdictFalseWithState`, itemised. THE FINDING. */
  artifacts: EmArtifact[];
  /** Split of `artifacts` by axis, so the imaging watcher's territory is
   *  visible rather than merged in. */
  byAxis: { specialty: number; 'note-shape': number };
  /** Non-vacuity evidence. A corpus that collapsed to nothing must not be
   *  readable as "clean" — the caller turns these into a cannot-tell. */
  control: {
    rows: number;
    /** Rows the SPECIALTY axis alone would admit. Zero here means the scan
     *  could not have found a note-shape artifact even if one existed. */
    specialtyEligible: number;
    /** Rows whose projection carried at least one heading. Zero means the
     *  heading extraction produced nothing for anybody — which is what a
     *  broken extract looks like, and it is indistinguishable from a corpus of
     *  bodies with no headings unless it is stated. */
    rowsWithHeadings: number;
    /** Rows carrying a bound template with at least one label. */
    rowsWithTemplateLabels: number;
    /** Shape census of the two JSONB columns, so the caller can see that
     *  `cptCodes` really is an object before believing a `#>>` path read
     *  anything. */
    cptCodesTypes: Record<string, number>;
    templateSectionsTypes: Record<string, number>;
  };
};

/** ⚠️ THE PHI CONTROL, AND IT IS ALSO THE CORRECTNESS ONE.
 *
 *  The extract filters note lines with a regex that is a strict PREFIX of
 *  `NOTE_SECTION_HEADING_RE`. Containment gives us "no line was missed"; it
 *  does NOT give us "no extra line was included", and an extra line is body
 *  text sitting in a projection that promises it carries none.
 *
 *  So every line handed to this module must survive the shipped regex. Any
 *  survivor count below the delivered line count is a finding, and the caller
 *  turns it into a cannot-tell rather than scanning on. */
export function assertNoBodyText(rows: EmScanRow[]): {
  deliveredLines: number;
  headingLines: number;
} {
  let deliveredLines = 0;
  let headingLines = 0;
  for (const row of rows) {
    if (!row.noteHeadingLines) continue;
    deliveredLines += row.noteHeadingLines.split('\n').filter((l) => l.trim() !== '').length;
    headingLines += normalizedNoteHeadings(row.noteHeadingLines).length;
  }
  return { deliveredLines, headingLines };
}

/** THE SCAN. Every verdict comes from `emAppliesToVisit`; nothing here decides
 *  applicability itself. */
export function scanEmArtifacts(rows: EmScanRow[]): EmScanResult {
  const buckets = {
    verdictFalseWithState: 0,
    verdictFalseClean: 0,
    verdictTrueWithState: 0,
    verdictTrueClean: 0,
  };
  const artifacts: EmArtifact[] = [];
  const byAxis = { specialty: 0, 'note-shape': 0 };
  const cptCodesTypes: Record<string, number> = {};
  const templateSectionsTypes: Record<string, number> = {};
  let specialtyEligible = 0;
  let rowsWithHeadings = 0;
  let rowsWithTemplateLabels = 0;

  for (const row of rows) {
    const shape = row.cptCodesType ?? 'null';
    cptCodesTypes[shape] = (cptCodesTypes[shape] ?? 0) + 1;
    const tShape = row.templateSectionsType ?? 'null';
    templateSectionsTypes[tShape] = (templateSectionsTypes[tShape] ?? 0) + 1;

    if (emAppliesToSpecialty(row.specialty)) specialtyEligible++;
    if (normalizedNoteHeadings(row.noteHeadingLines).length > 0) rowsWithHeadings++;
    if (Array.isArray(row.templateSections) && row.templateSections.length > 0) {
      rowsWithTemplateLabels++;
    }

    const applies = emAppliesToVisit({
      specialtyId: row.specialty,
      templateSections: row.templateSections,
      noteText: row.noteHeadingLines,
    });
    const fields = emStateOn(row);

    if (applies) {
      if (fields.length > 0) buckets.verdictTrueWithState++;
      else buckets.verdictTrueClean++;
      continue;
    }

    if (fields.length === 0) {
      buckets.verdictFalseClean++;
      continue;
    }

    buckets.verdictFalseWithState++;
    const axis = suppressingAxis(row);
    byAxis[axis]++;
    artifacts.push({
      visitId: row.visitId,
      specialty: row.specialty,
      signed: row.signed,
      axis,
      fields,
      frozenOnSigned: row.signed && Boolean(row.cptEmSignedCode),
    });
  }

  return {
    buckets,
    total:
      buckets.verdictFalseWithState +
      buckets.verdictFalseClean +
      buckets.verdictTrueWithState +
      buckets.verdictTrueClean,
    artifacts,
    byAxis,
    control: {
      rows: rows.length,
      specialtyEligible,
      rowsWithHeadings,
      rowsWithTemplateLabels,
      cptCodesTypes,
      templateSectionsTypes,
    },
  };
}
