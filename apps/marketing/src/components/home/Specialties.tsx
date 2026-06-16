/**
 * Specialties — Phase 7 v6 (Apple Product).
 *
 * Centred stage with rounded pills, one per shared catalog entry. Hover
 * lifts each pill with sage tint background + glow. Pill labels and
 * the headline count are both derived from the shared specialty catalog
 * (packages/shared) so adding a specialty updates the marketing site,
 * the in-app dropdowns, and the AI pipeline in one PR — no triplicate
 * vocab drift, and no manual "Eight"/"Nine" typo when the count changes.
 */
import { visibleSpecialties } from '@meddoc/shared/specialties';

// Flag-aware: a flag-gated specialty (Ultrasound) is not advertised publicly
// until NEXT_PUBLIC_ULTRASOUND_SPECIALTY is on at the marketing build. Flag
// OFF → exactly the pre-ultrasound pill list.
const PILLS = visibleSpecialties({ forVisitCreate: true }).map((s) => s.label);

const COUNT_WORDS = [
  'Zero', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight',
  'Nine', 'Ten', 'Eleven', 'Twelve',
] as const;
const COUNT_LABEL: string = COUNT_WORDS[PILLS.length] ?? String(PILLS.length);

export function Specialties() {
  return (
    <section className="stage" id="specialties">
      <div className="container stage-inner">
        <div className="reveal">
          <span className="eyebrow-tiny">Tuned per specialty</span>
        </div>
        <h2 className="stage-h2 reveal delay-1">
          {COUNT_LABEL} specialty templates. <span className="quiet">More every month.</span>
        </h2>
        <p className="stage-sub reveal delay-2">
          Each template adapts to your charting shorthand and preferred note structure within the
          first five visits.
        </p>

        <div className="specs-pills reveal delay-3">
          {PILLS.map((p) => (
            <span key={p} className="qm-pill">
              {p}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
