'use client';

// ── C1-f: the two note-format views a walk cannot reach ─────────────────────
//
// ⚠️ A SEPARATE FILE FROM `client.tsx`, AND THE REASON IS A TEST THAT BROKE.
// These previews first lived beside `DevErrorState`. That made `client.tsx`
// import the note-format tree, which reaches `next-auth` — and
// `gate-devstates` dynamically imports `client.tsx` to read the two error
// fixtures out of it, so the guard died on `Cannot find module 'next/server'`
// before asserting anything. Not a false pass, but a red that said nothing
// about the thing under test. A module that a unit test imports for two
// constants should not drag a page's worth of runtime behind it.
// Both live here rather than in `page.tsx` for the same reason `DevErrorState`
// does, and it is a hard constraint rather than a preference: every export of a
// `'use client'` module is a CLIENT REFERENCE to a server component, so
// `initialStages()` called from the page would not be the function — and
// `RejectedState` takes two callbacks, which do not cross the RSC boundary at
// all. Rendering them from a client island is the only shape that works.
//
// ⚠️ The stage model is built by the PRODUCT's `advance(initialStages(…))`,
// not by a literal array. A hand-written model would keep rendering happily
// after the real one changed shape, and this preview would then be measuring a
// state the product no longer draws — the C1-c2 lesson (a fixture built from
// its own contract) applied to a state machine instead of a predicate.

import { RejectedState } from '@/app/settings/note-format/note-format-manager';
import { ProcessingStages, advance, initialStages } from '@/app/settings/note-format/upload-flow';

/** Mid-flight: `read` done, `sections` live, two pending — one render carrying
 *  all three of the `is-done` / `is-active` / `is-pending` treatments. */
export function DevTmplProcessing() {
  return (
    <div style={{ padding: 32 }} data-testid="dev-tmpl-processing">
      <ProcessingStages
        stages={advance(initialStages(true), 'read', 'done', 'sample-form.docx')}
      />
    </div>
  );
}

/** The refusal. `reason` is a FIXED SYNTHETIC string: this route is
 *  screenshotted into a CI artifact retained for 14 days, so nothing rendered
 *  here may come from a real parse. */
export function DevTmplRejected() {
  return (
    <div style={{ padding: 32 }} data-testid="dev-tmpl-rejected">
      <RejectedState
        reason="A date and a name could not be separated from the surrounding text."
        onStandard={() => undefined}
        onRetry={() => undefined}
      />
    </div>
  );
}
