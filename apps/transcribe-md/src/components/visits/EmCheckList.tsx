'use client';

// ============================================================================
// EmCheckList — three criterion groups (History / Exam / MDM)
// ----------------------------------------------------------------------------
// Mirrors `.checklist` from soap-v6.html lines 941-1093. Each group has a
// dashed-hairline head (title + summary) + N rows + optional micro-meta
// footer ("99213 ✓ expanded prob-focused" / "99214 needs 8+").
//
// Group → SOAP-section mapping for jump-to-section coupling:
//   - history → subjective
//   - exam    → objective
//   - mdm     → assessment
// ============================================================================

import { useState, useCallback } from 'react';
import type { EmCriterionGroup } from '@/lib/em-coding-ui/types';
import { EmCriterion } from './EmCriterion';

interface EmCheckListProps {
  groups: EmCriterionGroup[];
  /** Called when a row's nudge fires — parent surfaces the suggestion via toast. */
  onNudge?: (criterionId: string, suggestion: string) => void;
  /** Set of criterion ids currently in optimistic "applying..." state. */
  applyingIds?: Set<string>;
}

export function EmCheckList({ groups, onNudge, applyingIds }: EmCheckListProps) {
  // Track ids that the user has interacted with so we don't keep firing the
  // same nudge on re-renders. Pure UI state, never persisted.
  const [, setTouchedIds] = useState<Set<string>>(() => new Set());

  const handleNudge = useCallback(
    (criterionId: string, suggestion: string) => {
      setTouchedIds((prev) => {
        const next = new Set(prev);
        next.add(criterionId);
        return next;
      });
      onNudge?.(criterionId, suggestion);
    },
    [onNudge]
  );

  return (
    // P5.2 hot-fix: dropped `role="list"` here. axe-core flagged it
    // critical because the role demands `<li>` / `role="listitem"`
    // children, and we render `<section>` groups instead. The
    // sections already carry their own `aria-labelledby`, so screen
    // readers still navigate them as titled regions.
    <div className="qm-lin-em-checklist" aria-label="Coding criteria">
      {groups.map((group) => (
        <section
          key={group.id}
          className="qm-lin-em-criterion-group"
          aria-labelledby={`em-group-${group.id}`}
        >
          <header className="qm-lin-em-criterion-group-head">
            <span id={`em-group-${group.id}`} className="qm-lin-em-criterion-group-title">
              {group.title}
            </span>
            <span className="qm-lin-em-criterion-group-summary">{group.summary}</span>
          </header>
          {group.items.map((item) => (
            <EmCriterion
              key={item.id}
              criterion={item}
              onNudge={(suggestion) => handleNudge(item.id, suggestion)}
              applying={applyingIds?.has(item.id) ?? false}
            />
          ))}
          {group.footer ? (
            <footer className="qm-lin-em-criterion-group-foot">
              <span className="qm-lin-em-criterion-group-foot-satisfied">
                {group.footer.satisfied}
              </span>
              {group.footer.nextLevel ? (
                <span className="qm-lin-em-criterion-group-foot-next">
                  {group.footer.nextLevel}
                </span>
              ) : null}
            </footer>
          ) : null}
        </section>
      ))}
    </div>
  );
}
