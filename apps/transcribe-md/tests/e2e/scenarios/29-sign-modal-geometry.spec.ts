// ============================================================================
// The sign modal's footer is REACHABLE — measured, not assumed.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS BECAUSE A REQUIRED CONTROL WENT OFF-SCREEN AND NOTHING SAID SO.
//
// `POST /sign` gained a required attestation (2026-08-02). The modal collects it
// on every path where nothing upstream has, and the block was added above the
// action row — which was the one place it could not go. The dialog had NO height
// bound and its body a fixed `max-h-[60vh]`, so total height was
// `12vh + header + 60vh + gates + action row`. That already overflowed 720px;
// one more required block pushed "Sign & Deliver" fully below the fold.
//
// Three signing specs failed, and NONE of them said "the button is off-screen".
// They said "waiting for event download" and "expected dialog to be hidden" —
// symptoms one whole interaction downstream of the cause. A geometry assertion
// is the cheapest thing that would have named it immediately.
//
// So: the attestation and the submit are one control region, pinned, and this
// asserts they are both inside the viewport at the size the default pack runs.
//
// ────────────────────────────────────────────────────────────────────────────
// ⚠️ RE-POINTED 2026-08-04 — THE ATTESTATION MOVED, SO THE MEASUREMENT SPLIT IN
// TWO AND THE NON-VACUITY GUARD BECAME SKIN-AWARE. The sentence above is still
// the whole intent; under Rounds "one control region" is no longer literally
// true, and pretending otherwise is what would have weakened this test.
//
// WAS (:48-51) — one opener, clicked straight off the visit page:
//     getByRole('button', { name: /sign (&|and) (download|deliver|send)/i })
// That is the FLAG-OFF opener only ("Sign & Send", `soap-editor.tsx:479`).
// Under Rounds no signature control exists on the stage at all — the stage pack
// asserts its ABSENCE there on purpose (`rounds-stage.spec.ts:648-661`) — and
// the walk is three steps: the rail's `rounds-review-sign` → Gate 3's
// `rounds-gate-attest` (`gate-flow.tsx:337`) → the gate signbar's
// "Sign & Download" (`review-sign-bar.tsx:118`, hosted at
// `gate-flow.tsx:400-404`). `helpers/sign.ts:61` walks whichever skin was
// BUILT, branching on the DOM rather than on a flag the runner cannot see.
// FAILS IF: no opener is reachable, the rail never enables, the gate flow never
// presents the attestation, or the gates never clear — each named by the helper.
//
// WAS (:60-65) — a flat `expect(sign-attestation).toHaveCount(1)` guard.
// Under Rounds that count is CORRECTLY 0: Gate 3 collects the attestation and
// `visit-ready-view.tsx:1101` forwards it, so `attestationNeededHere` is false
// (`sign-and-send-modal.tsx:148`) and the modal declines to ask a second time.
// A naive re-point trips this spec's own guard.
// ⚠️ THE GUARD IS NOT DELETED AND NOT WIDENED. It is restated as the property
// it was always protecting — **exactly ONE attestation exists on the signing
// path** — and checked as a sum across both homes. ZERO still fails, for the
// original reason (nothing is being measured, and a server-enforced gate with
// no UI anywhere is a bypass). TWO now fails as well, which is the duplication
// R2 removed (`review-sign-bar.tsx:4-43`). The only thing that changed is that
// the one attestation is allowed to live in Gate 3 instead of in the modal.
//
// WAS (:67-84) — one `0 <= y && y+h <= vh` loop over BOTH controls. That was
// right while both sat in the same bounded, pinned-footer dialog. They no
// longer do:
//   · THE SUBMIT still does. `Dialog.Portal` mounts it on <body>, `fixed
//     top-[12vh] max-h-[76vh] flex-col` with a `flex-none` footer
//     (`sign-and-send-modal.tsx:321-341` + `:546`). The Rounds gate overlay
//     never contains it, so the ORIGINAL HARD ASSERTION IS KEPT VERBATIM, on
//     both skins — it is still the single cheapest thing that would have named
//     the 2026-08-02 defect.
//   · THE ATTESTATION, under Rounds, is inside `.qm-rounds-gateflow`:
//     `position: fixed; inset: 0; overflow-y: auto`
//     (`rounds-tokens.css:1072-1085`). At 640px it legitimately sits below the
//     fold and the doctor scrolls to it, so an on-screen assertion there would
//     be a FALSE RED against a correct product. The invariant in a scrolling
//     region is REACHABILITY: content may exceed the box, but only if the box
//     scrolls — asserted directly, below, rather than assumed.
//
// WAS (:101-106) — `getByRole('dialog')` for "the modal closed". Forbidden
// under Rounds: the gate flow carries `role="dialog"` too
// (`gate-flow.tsx:228`), so the query is strict-mode ambiguous with both open,
// and Radix un-aria-hides the gate flow the instant the modal closes — a
// role-scoped hidden-check would go red for a reason unrelated to the sign.
// Anchored on the modal's own <h2> (`sign-and-send-modal.tsx:347`) instead:
// unique in the app, and present in every modal state including the pending
// "Signing…" one (the BUTTON relabels, `:596`, so a wedged mid-sign modal would
// satisfy a hidden-check on it while still sitting on screen).
// ============================================================================

import { test, expect } from '@playwright/test';

import { attestAndSubmit, openSignFlow } from '../helpers/sign';
import { signupFreshUser } from '../helpers/signup';
import { createReadyTextVisit } from '../helpers/visit-setup';
import { psqlOne } from '../helpers/seedReviewDocVisit';

/** The default pack runs `devices['Desktop Chrome']` — 1280×720. 720 is the
 *  number that matters: the overflow was vertical. */
const VIEWPORTS = [
  { name: 'desktop-chrome-720', width: 1280, height: 720 },
  // The shortest viewport any pack uses. If the footer survives here it
  // survives everywhere the suite looks.
  { name: 'short-640', width: 1280, height: 640 },
];

test.describe('the sign modal keeps its signature controls on screen', () => {
  for (const vp of VIEWPORTS) {
    test(`attestation + submit are both inside the viewport @${vp.name}`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await signupFreshUser(page, `signgeo-${vp.height}`);
      const visitId = await createReadyTextVisit(page, {
        patientName: 'Sign Geometry',
      });
      await page.goto(`/visits/${visitId}`);

      // Wait for AN opener before walking. `openSignFlow` branches on a
      // SYNCHRONOUS `.count()` of the Rounds rail, so arriving one tick early
      // would take the legacy branch and then fail 10s later on a button the
      // Rounds skin never renders.
      await expect(
        page
          .getByTestId('rounds-review-sign')
          .or(page.getByRole('button', { name: /sign & send/i }))
          .first(),
        'visit reached READY but neither sign opener ever rendered on the page',
      ).toBeVisible({ timeout: 30_000 });

      await openSignFlow(page);

      // The modal's identity is its title, not `role="dialog"` — see the header.
      const signModal = page.getByRole('heading', {
        name: 'Sign and deliver your note',
        exact: true,
      });
      await expect(
        signModal,
        'openSignFlow completed but the sign modal never opened',
      ).toBeVisible({ timeout: 10_000 });

      const vh = vp.height;

      // ── 1. THE PINNED CONTROL — unchanged measurement, both skins ─────────
      // The modal is portalled to <body> and bounded at `top-[12vh]` +
      // `max-h-[76vh]` with a `flex-none` footer, so its submit must be fully
      // on screen with no scrolling anywhere.
      // FAILS IF: the dialog loses its height bound, the footer stops being
      // `flex-none`, or a new required block is added below the action row —
      // i.e. the exact 2026-08-02 regression, on either skin.
      const submit = page
        .getByRole('button', { name: /sign & deliver/i })
        .first();
      await expect(submit).toBeVisible();

      const submitBox = await submit.boundingBox();
      expect(
        submitBox,
        'sign submit has no box — it is not laid out at all',
      ).not.toBeNull();
      expect(
        submitBox!.y,
        `sign submit starts at y=${submitBox!.y} on a ${vh}px viewport — above the fold`,
      ).toBeGreaterThanOrEqual(0);
      expect(
        submitBox!.y + submitBox!.height,
        `sign submit ends at y=${Math.round(submitBox!.y + submitBox!.height)} on a ` +
          `${vh}px viewport — BELOW THE FOLD, so the doctor cannot reach it ` +
          'without scrolling a region that does not scroll',
      ).toBeLessThanOrEqual(vh);

      // ── 2. NON-VACUITY: exactly ONE attestation on the signing path ───────
      // Restated, not widened. Zero fails (nothing being measured / a
      // server-enforced gate with no UI is a bypass); two fails (the
      // duplication R2 removed). WHICH home holds it is the skin's business.
      const modalAttestation = page.getByTestId('sign-attestation');
      const gateAttestation = page.getByTestId('rounds-gate-attest');
      const modalCount = await modalAttestation.count();
      const gateCount = await gateAttestation.count();
      expect(
        modalCount + gateCount,
        `attestations on the signing path: ${modalCount} in the modal ` +
          `(sign-and-send-modal.tsx:423), ${gateCount} in Gate 3 ` +
          '(gate-flow.tsx:337). Exactly one is required — ZERO means this test ' +
          'is not measuring the control that broke and `POST /sign` has a ' +
          'server-enforced gate with no UI anywhere; TWO means the doctor is ' +
          'asked to attest twice, the duplication R2 removed.',
      ).toBe(1);

      if (gateCount === 1) {
        // ── ROUNDS: the attestation is upstream, in a SCROLLING region ──────
        // Prove it was genuinely collected. `openSignFlow` ticked it, and a
        // build that forwarded a hardcoded `true` without collecting anything
        // would leave this unchecked while the modal still looked fine.
        await expect(
          gateAttestation,
          'Gate 3 renders the attestation but it is not ticked — the modal ' +
            'dropped its own copy anyway, so nothing on this path attests',
        ).toBeChecked();

        // …and that ticking it CLEARED the counted gate the signature is wired
        // to. `blocked` on the gate signbar is `roundsView.n > 0`
        // (`visit-ready-view.tsx:1182`), and `n` is what this element carries
        // (`gate-flow.tsx:427`). If the tick were cosmetic — not fed through
        // `applyGateOverlay` (`stage-view-model.ts:171`) — this would still
        // read 1 and the trigger would still be refusing.
        await expect(
          page.getByTestId('rounds-gate-n'),
          'the attestation is ticked but the gate count still shows a blocker ' +
            '— the tick is not reaching the number that gates the signature',
        ).toHaveAttribute('data-blockers', '0');

        // THE REACHABILITY INVARIANT, in place of the on-screen one. The gate
        // panel is `position: fixed; inset: 0; overflow-y: auto`. Content
        // taller than the box is fine there; content taller than a box that
        // CANNOT scroll is the 2026-08-02 defect wearing a new container.
        // FAILS IF: `.qm-rounds-gateflow` loses `overflow-y: auto` (or gains
        // `hidden`/`clip`) while its content exceeds the viewport.
        const region = await page
          .getByTestId('rounds-gate-flow')
          .evaluate((el) => ({
            scrollHeight: el.scrollHeight,
            clientHeight: el.clientHeight,
            overflowY: getComputedStyle(el).overflowY,
          }));
        expect(
          region.scrollHeight <= region.clientHeight + 1 ||
            /^(auto|scroll|overlay)$/.test(region.overflowY),
          `the gate panel needs ${region.scrollHeight}px inside a ` +
            `${region.clientHeight}px box and its overflow-y is ` +
            `"${region.overflowY}" — everything past the fold is UNREACHABLE, ` +
            'so the doctor cannot get to the attestation or to the signature',
        ).toBe(true);

        // And each moved control can actually be brought FULLY into view.
        // Native `scrollIntoView` rather than Playwright's
        // `scrollIntoViewIfNeeded`: the modal is open over this region, and a
        // synchronous DOM scroll makes no actionability claim about an element
        // an overlay covers. No `scroll-behavior: smooth` is in play
        // (`rounds-tokens.css:217` only forces `auto`), so the scroll lands
        // before the measurement.
        // FAILS IF: a control ends up somewhere the region cannot scroll it to,
        // or is taller than the viewport — unreachable at this size, which is
        // this spec's whole subject.
        for (const [label, loc] of [
          ['gate attestation', gateAttestation],
          ['gate signbar', page.getByTestId('review-doc-signbar')],
        ] as const) {
          const el = loc.first();
          await el.evaluate((node) => node.scrollIntoView({ block: 'center' }));
          const box = await el.boundingBox();
          expect(
            box,
            `${label} has no box — it is not laid out at all`,
          ).not.toBeNull();
          expect(
            box!.y,
            `${label} still starts at y=${box!.y} after being scrolled to the ` +
              `centre of a ${vh}px viewport — it cannot be brought on screen`,
          ).toBeGreaterThanOrEqual(0);
          expect(
            box!.y + box!.height,
            `${label} still ends at y=${Math.round(box!.y + box!.height)} after ` +
              `being scrolled to the centre of a ${vh}px viewport — the gate ` +
              'region clips it, so it is unreachable at this size',
          ).toBeLessThanOrEqual(vh);
        }

        // ⚠️ NO `toBeDisabled()` HERE, AND THAT IS NOT A WEAKENING. Under
        // Rounds the refusal happens one step EARLIER than this spec can now
        // observe: the attestation is a counted gate, so the signbar's trigger
        // is `disabled` until it is ticked and the modal cannot be opened at
        // all — `openSignFlow` could not have got here otherwise. Once inside,
        // `attested` is already true and an enabled submit is correct. The
        // coupling is still proved end-to-end below: `POST /sign` answers 400
        // ATTESTATION_REQUIRED without an attestation (`sign-gates.ts:238-247`),
        // so the modal closing is proof one reached the server, and Gate 3 is
        // the only place this walk collected one.
      } else {
        // ── LEGACY: the attestation is in the modal, beside the submit ──────
        // Same pinned dialog, so the same hard on-screen measurement the spec
        // was written with.
        const attestationBox = await modalAttestation.boundingBox();
        expect(
          attestationBox,
          'attestation has no box — it is not laid out at all',
        ).not.toBeNull();
        expect(
          attestationBox!.y,
          `attestation starts at y=${attestationBox!.y} on a ${vh}px viewport — above the fold`,
        ).toBeGreaterThanOrEqual(0);
        expect(
          attestationBox!.y + attestationBox!.height,
          `attestation ends at y=${Math.round(
            attestationBox!.y + attestationBox!.height,
          )} on a ${vh}px viewport — BELOW THE FOLD, so the doctor cannot reach ` +
            'it without scrolling a region that does not scroll',
        ).toBeLessThanOrEqual(vh);

        // And the coupling the ruling asks for: the submit refuses until the
        // attestation beside it is checked. (`attestAndSubmit` below ticks it
        // and asserts the button then ENABLES, with its own message.)
        await expect(
          submit,
          'the submit is live before the attestation was ticked — the UI half ' +
            'of a server-enforced gate is not gating anything',
        ).toBeDisabled();
      }

      // ⚠️ ENABLED IS NOT THE SAME AS WORKING, and that gap cost three specs.
      // `disabled` reads fresh state from JSX every render, so the button lit
      // up the instant the box was ticked — while the memoised `submit`
      // callback, missing `attestationSatisfied` from its dep array, still held
      // `false` and returned at the attestation guard. No request, no audit
      // row, no toast: a control that looks ready and does nothing.
      // Asserting the modal CLOSES is the cheapest proof the handler actually
      // ran, and it is the assertion that would have named this immediately.
      //
      // `attestAndSubmit` (helpers/sign.ts:101) is what ticks the modal's box
      // where there is one, waits for ENABLED, and clicks — a real click first,
      // `dispatchEvent` only where the Rounds overlay blocks one.
      await attestAndSubmit(page);
      await expect(
        signModal,
        'the submit was enabled and clicked, and the modal is still open — ' +
          'the handler returned early (a stale closure over a gate, a guard ' +
          'the UI is not showing, or a server refusal the modal swallowed)',
      ).toBeHidden({ timeout: 15_000 });
    });
  }
});

// ============================================================================
// ⚠️ THE PANEL CLIPS, AND THE VIEWPORT ASSERTION ABOVE CANNOT SEE IT.
// ----------------------------------------------------------------------------
// FOUND BY T4's ADVERSARIAL PASS, WHICH REFUTED THE AUTHOR'S OWN CLAIM. The
// sign card is capped at `max-h-[76vh]` from `top-[12vh]`, so its BOX always
// ends at 88vh — and the author argued the submit was therefore safe "by
// construction". The cap bounds the CARD, not the CONTENT:
// `.qm-lin-spotlight-panel` carries `overflow: hidden` (globals.css), so once
// the `flex-none` siblings out-sum the cap the excess is CLIPPED WITH NO
// SCROLLBAR ANYWHERE.
//
// `boundingBox()` still returns the laid-out coordinates of a clipped element,
// so `y + height <= vh` passes while the button is not there. Measured on the
// T4 skin at 1280x640: 15.1px clipped, and
// `document.elementFromPoint(cx, bottom - 5)` returned `HTML` instead of the
// button — the pixels were not merely ugly, they were not hit-testable.
//
// TWO THINGS THIS ADDS, and each catches what the other cannot:
//
//   1. CONTAINMENT IN THE CLIPPER — the submit's box must be inside the
//      panel's box, which is the element that actually does the clipping.
//   2. HIT-TESTABILITY — `elementFromPoint` at the button's own bottom edge
//      must land ON the button. That is the doctor's question, not a number.
//
// AND THE STATE IT WALKS IS THE ONE THE ORIGINAL FIXTURE COULD NOT REACH:
// `createReadyTextVisit` never produces an `emPendingChange`, so the E/M
// confirm block — a `flex-none` sibling that is live at TWO call sites
// (`review-tabs-v2.tsx`, `soap-editor.tsx`, neither of which passes `attested`)
// — was never in the measured tree at all.
// ============================================================================

test.describe('the sign modal is not CLIPPED by its own panel', () => {
  for (const vp of VIEWPORTS) {
    test(`submit survives an E/M confirm block @${vp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await signupFreshUser(page, `signclip-${vp.height}`);
      const visitId = await createReadyTextVisit(page, {
        patientName: 'Sign Clip',
      });

      // ⚠️ PLANTED, NOT WAITED FOR. The E/M scorer is a real model and we do
      // not get to choose its answer, so the only deterministic way to put the
      // confirm block on screen is to write the record the modal renders from.
      // Skipped rather than failed where psql is unavailable — an unmeasured
      // state named honestly beats a red that means "no database".
      let planted = false;
      try {
        psqlOne(
          `update transcribe_visits set "emPendingChange"=` +
            `'{"from":"99213","to":"99214","at":"2026-09-05T00:00:00.000Z"}'::jsonb ` +
            `where id='${visitId}'`,
        );
        planted = true;
      } catch {
        planted = false;
      }
      test.skip(!planted, 'psql seeding unavailable — the E/M state cannot be planted');

      await page.goto(`/visits/${visitId}`);
      await expect(
        page
          .getByTestId('rounds-review-sign')
          .or(page.getByRole('button', { name: /sign & send/i }))
          .first(),
        'visit reached READY but neither sign opener ever rendered',
      ).toBeVisible({ timeout: 30_000 });

      await openSignFlow(page);
      await expect(
        page.getByRole('heading', { name: 'Sign and deliver your note', exact: true }),
        'openSignFlow completed but the sign modal never opened',
      ).toBeVisible({ timeout: 10_000 });

      // NON-VACUITY: the E/M block really is on screen, so the geometry below
      // is measured in the state this test exists for and not in the easy one.
      await expect(
        page.getByTestId('em-change-confirm'),
        'the E/M confirm block is absent — the planted emPendingChange did not ' +
          'reach the modal, so this test is measuring the SAME tree the ' +
          'viewport assertion already covers',
      ).toBeVisible({ timeout: 10_000 });

      const submit = page.getByRole('button', { name: /sign & deliver/i }).first();
      await expect(submit).toBeVisible();

      // ── 1 · CONTAINED BY THE ELEMENT THAT CLIPS ──────────────────────────
      const panel = page.locator('.qm-lin-spotlight-panel').first();
      const [sBox, pBox] = [await submit.boundingBox(), await panel.boundingBox()];
      expect(sBox, 'sign submit has no box — it is not laid out at all').not.toBeNull();
      expect(pBox, 'the spotlight panel has no box').not.toBeNull();
      expect(
        Math.round(sBox!.y + sBox!.height),
        `sign submit ends at y=${Math.round(sBox!.y + sBox!.height)} inside a panel ` +
          `that ends at y=${Math.round(pBox!.y + pBox!.height)} and has ` +
          `overflow:hidden — the difference is CLIPPED AWAY, with no scrollbar ` +
          `anywhere, on a ${vp.height}px viewport`,
      ).toBeLessThanOrEqual(Math.round(pBox!.y + pBox!.height));

      // ── 2 · AND IT IS ACTUALLY HIT-TESTABLE ──────────────────────────────
      // The box test above is arithmetic; this is the doctor's question. A
      // clipped element keeps its coordinates, so only a hit test can tell
      // whether the pixels the doctor aims at belong to the button.
      const hit = await page.evaluate(
        ([x, y]) => {
          const el = document.elementFromPoint(x as number, y as number);
          return el ? `${el.tagName}.${(el as HTMLElement).className || ''}`.slice(0, 80) : 'NONE';
        },
        [sBox!.x + sBox!.width / 2, sBox!.y + sBox!.height - 4],
      );
      expect(
        hit.toLowerCase(),
        `the point at the bottom edge of "Sign & Deliver" resolves to ${hit} — ` +
          `the doctor cannot click the control that signs the note`,
      ).toContain('button');
    });
  }
});
