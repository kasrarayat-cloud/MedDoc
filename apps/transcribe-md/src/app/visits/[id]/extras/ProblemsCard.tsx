'use client';

// ============================================================================
// ProblemsCard — chronic / acute diagnoses with ICD-10 codes.
// ----------------------------------------------------------------------------
// Status pills: ACTIVE (sage) / DRAFT (amber) / RESOLVED (text-3).
// ----------------------------------------------------------------------------
// We can opportunistically derive a draft entry from the visit's
// chiefComplaint + first ICD code, but that's the caller's job — this
// component just renders the rows it's handed.
// ============================================================================

import { ExtrasCard } from './ExtrasCard';

export type ProblemStatus = 'active' | 'draft' | 'resolved';

export interface Problem {
  /** ICD-10 code, e.g. "I10". */
  icd: string | null;
  /** Diagnosis name, e.g. "Hypertension". */
  name: string;
  status: ProblemStatus;
  /** Optional contextual line ("Controlled, stable on lisinopril …"). */
  detail?: string | null;
}

interface Props {
  problems: Problem[];
  readonly: boolean;
}

const STATUS_DOT: Record<ProblemStatus, string> = {
  active: '●',
  draft: '○',
  resolved: '·',
};

const STATUS_CLS: Record<ProblemStatus, string> = {
  active: 'qm-lin-extras-problem-row qm-lin-extras-problem-row--active',
  draft: 'qm-lin-extras-problem-row qm-lin-extras-problem-row--draft',
  resolved: 'qm-lin-extras-problem-row',
};

export function ProblemsCard({ problems, readonly }: Props) {
  const total = problems.length;
  const active = problems.filter((p) => p.status === 'active').length;
  const draft = problems.filter((p) => p.status === 'draft').length;

  let count: string | null = null;
  let tone: 'sage' | 'warn' | 'default' = 'default';
  if (total === 0) {
    count = null;
  } else if (draft > 0) {
    count = `${active} active · ${draft} draft`;
    tone = 'warn';
  } else {
    count = `${active} active`;
    tone = 'sage';
  }

  return (
    <ExtrasCard
      icon="📋"
      title="Problem list"
      sub="Active diagnoses on this patient"
      count={count}
      countTone={tone}
      hideEdit={readonly}
      foot={
        total > 0 && !readonly ? (
          <>
            <span className="opacity-60">+ Add problem (coming soon)</span>
            <span>Updates with Sign &amp; send</span>
          </>
        ) : null
      }
    >
      {total === 0 ? (
        <div className="qm-lin-extras-empty">
          No active or draft problems recorded.
        </div>
      ) : (
        <div>
          {problems.map((p, i) => (
            <div
              key={`${p.icd ?? 'noicd'}-${i}`}
              className={STATUS_CLS[p.status]}
            >
              <span className="qm-lin-extras-problem-dot">
                {STATUS_DOT[p.status]}
              </span>
              <div className="min-w-0 flex-1">
                <div className="qm-lin-extras-problem-head">
                  <span className="qm-lin-extras-problem-name">{p.name}</span>
                  {p.icd && (
                    <span className="qm-lin-extras-icd-pill">{p.icd}</span>
                  )}
                  {p.status === 'draft' && (
                    <span className="qm-lin-extras-draft-pill">
                      Draft · pending sign-off
                    </span>
                  )}
                  {p.status === 'resolved' && (
                    <span className="qm-lin-extras-draft-pill">Resolved</span>
                  )}
                </div>
                {p.detail && (
                  <div className="qm-lin-extras-problem-detail">{p.detail}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </ExtrasCard>
  );
}
