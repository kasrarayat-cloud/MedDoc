// ============================================================================
// T4 — SIGN & DELIVER. THE GATE FOR WHAT RULING #188 RULED.
// ----------------------------------------------------------------------------
// The re-skin itself is CSS and is not asserted here. What IS asserted is the
// two things the ruling settled AGAINST the frames, because those are the ones
// a future "make it match the mockup" pass would undo:
//
//   #188(1)  the row is applied PER FORMAT — five EHR clipboard destinations,
//            not the one row the frames draw
//   #188(2)  the email group's safety caption SURVIVES
//
// ⚠️ AND THE SECOND IS THE ONE THAT MATTERS. "Don't use for patient
// communication" is the line that stops a doctor mailing a note to a patient.
// The frames' flat DELIVER TO list had no slot for it, so building them
// literally would have deleted it. A LITERAL FRAME THAT DELETES A SAFETY
// INSTRUCTION IS NOT THE SPEC.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';

vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
}));

import { toast } from 'sonner';

import { SignAndSendModal } from '../sign-and-send-modal';

// ⚠️ MODULE MOCKS ACCUMULATE ACROSS TESTS, AND THE FIRST VERSION OF THE ARMS
// BELOW COUNTED THE PREVIOUS TEST'S CALLS — `toast.success` read 2 where the
// arm asserted 1, and `fetch` read 4 where it asserted 1. Both reds were the
// INSTRUMENT, not the component: a per-test count is only a measurement if the
// counter starts at zero.
beforeEach(() => {
  vi.clearAllMocks();
});

type Props = Parameters<typeof SignAndSendModal>[0];

/** The modal renders its card in a portal, so queries run against the body. */
function open(over: Partial<Props> = {}) {
  return render(
    <SignAndSendModal
      visitId="v1"
      doctorEmail="doc@test.dev"
      emailEnabled
      signOnSubmit
      triggerLabel="Sign & Send"
      triggerIcon={null}
      controlledOpen
      onControlledOpenChange={() => {}}
      {...over}
    />,
  );
}

describe('⚠️ #188(1) — the row is applied PER FORMAT, and nothing collapses', () => {
  it('all five EHR clipboard destinations render as their own row', () => {
    open();
    // The frames draw ONE "Copy note to clipboard" row. Collapsing to that
    // would mean a doctor on Epic cannot pick the Epic format.
    for (const label of [
      'Copy for Epic',
      'Copy for Athena',
      'Copy for Cerner',
      'Copy for eClinicalWorks',
      'Copy as plain text',
    ]) {
      expect(
        screen.getByRole('button', { name: label }),
        `${label} is gone — the five formats collapsed into one row`,
      ).toBeTruthy();
    }
  });

  it('the clipboard GROUP holds exactly those five, and each is independently checkable', () => {
    open();
    const group = screen.getByTestId('t4-group-clipboard');
    const rows = within(group).getAllByRole('button');
    expect(rows.length).toBe(5);
    // `aria-pressed` is what makes a row a checkable control to a screen
    // reader — the visual box is aria-hidden decoration.
    for (const r of rows) expect(r.getAttribute('aria-pressed')).toBeTruthy();
  });

  it('download and email keep their own groups — the grouping is not flattened', () => {
    open();
    expect(within(screen.getByTestId('t4-group-download')).getAllByRole('button').length).toBe(2);
    expect(within(screen.getByTestId('t4-group-email')).getAllByRole('button').length).toBe(1);
  });
});

describe('⚠️ #188(2) — the safety caption survives the re-skin', () => {
  it('the email row carries "Don’t use for patient communication"', () => {
    open();
    const caption = screen.getByTestId('t4-caption-email');
    expect(
      caption.textContent,
      'the email safety instruction is gone — a literal frame deleted it',
    ).toContain("Don't use for patient communication");
  });

  it('and it names the recipient, which is the DOCTOR — not a referring physician', () => {
    // #188(3): sending to a referring physician is its own product item. The
    // shipped behaviour mails the signing doctor a link to their own note, and
    // the caption must keep saying so.
    open({ doctorEmail: 'someone@clinic.test' });
    expect(screen.getByTestId('t4-caption-email').textContent).toContain('someone@clinic.test');
  });

  it('every group has a caption — the slot exists for all three, not just email', () => {
    open();
    for (const g of ['clipboard', 'download', 'email']) {
      expect(screen.getByTestId(`t4-caption-${g}`).textContent?.trim().length).toBeGreaterThan(0);
    }
  });
});

// ============================================================================
// ⚠️ THE ADVERSARIAL PASS'S FINDINGS, AS ARMS.
// ----------------------------------------------------------------------------
// Six lenses over the finished skin. None of the arms above could see any of
// these, and two of them were defects the re-skin INTRODUCED on the surface
// that signs a clinical note.
// ============================================================================

describe('⚠️ the re-skin must not delete what the doctor was told', () => {
  // ⚠️ THESE ARMS USE `screen`, NOT `within(result.container)`, AND THE
  // DIFFERENCE IS THE PORTAL. `Dialog.Content` mounts on `document.body`, so
  // the render result's `container` holds only the trigger — an assertion
  // scoped to it finds nothing and reds against correct code, which is exactly
  // what the first version of these three arms did.
  //
  // It is the MIRROR of the trap in `gate-f8-s2-coding-view`, where `container`
  // was required because `screen` saw two renders at once. Neither is a rule;
  // the rule is to know where the content actually is.
  it('⚠️ THE PRE-SIGN MODAL STILL SAYS THE NOTE LOCKS', () => {
    // Deleting this was the same defect ruling #188(2) exists to prevent, one
    // line over from the caption that ruling protects: the frames' sub-copy
    // replaced the flat slot that carried the warning, so the warning went with
    // the words around it. Signing is terminal for editing, and no other string
    // in the modal said so — the doctor would have been told only afterwards.
    open();
    expect(screen.getByText(/locks after signing/i)).toBeTruthy();
  });

  it('and it still says a locked note can be re-exported', () => {
    // The mitigation, and the answer to "if I sign now, can I still get the
    // PDF?". It was deleted with the footer copy it lived in — so the doctor
    // lost the warning AND its answer in one diff.
    open();
    expect(screen.getByTestId('t4-reexport-note').textContent).toMatch(/re-exported later/i);
  });

  it('⚠️ and it does NOT invent a requirement the product has not got', () => {
    // The frames' post-sign copy says "Deliver to required destinations". No
    // destination is required and none is marked so; the only rule is at least
    // one. A frame's copy does not get to invent a constraint.
    open({ signOnSubmit: false });
    expect(screen.queryByText(/required destinations/i)).toBeNull();
    // Non-vacuity: the post-sign sub-copy IS rendered, so the absence above is
    // about the words and not about an empty render.
    expect(screen.getByText(/choose where to deliver it/i)).toBeTruthy();
  });
});

describe('⚠️ the email caption describes what the sender actually does', () => {
  it('says a LINK is sent, never that the note is attached', () => {
    // `sendVisitPdfEmail` sends NO attachment and its own body says "We don't
    // send notes or patient details by email" — while the caption promised a
    // PDF, directly above the sentence that exists to stop a doctor forwarding
    // it. A doctor who believes the note is IN the email is one forward away
    // from the disclosure the warning prevents.
    open();
    const cap = screen.getByTestId('t4-caption-email').textContent ?? '';
    expect(cap).toMatch(/link/i);
    expect(cap).toMatch(/never attached/i);
    expect(cap, 'the caption still promises a PDF the sender does not send').not.toMatch(
      /send a pdf/i,
    );
    // And the safety half is still there — this fix must not cost it.
    expect(cap).toContain("Don't use for patient communication");
  });
});

describe('the delivery summary reflects the checked set', () => {
  it('names the checked destinations and nothing else', () => {
    open();
    const s = screen.getByTestId('t4-delivery-summary').textContent ?? '';
    // PDF is the default-checked destination.
    expect(s).toContain('Download PDF');
    // A destination that is NOT checked must not appear — a summary that can
    // disagree with the boxes above it is worse than no summary.
    expect(s).not.toContain('Copy for Cerner');
  });

  it('⚠️ NAMES ONE CLIPBOARD FORMAT, BECAUSE ONLY ONE IS COPIED', () => {
    // ⚠️ THE ARM ABOVE COULD NOT SEE THIS, AND THAT IS RECORDED RATHER THAN
    // QUIETLY FIXED. It asserts `not.toContain('Copy for Cerner')` against the
    // DEFAULT selection, which never contained Cerner — so it passed whatever
    // the summary did. A mutation that listed every clipboard format redded
    // NOTHING. Vacuous, in the exact shape this repo hunts for.
    //
    // The property: `applyBrowserSideDeliveries` copies the LAST selected
    // clipboard format and discards the others, so a summary listing both told
    // the doctor something untrue.
    open();
    // Epic is checked by default; add Athena so two are selected at once.
    fireEvent.click(screen.getByRole('button', { name: 'Copy for Athena' }));
    const s = screen.getByTestId('t4-delivery-summary').textContent ?? '';

    const named = ['Copy for Epic', 'Copy for Athena'].filter((l) => s.includes(l));
    expect(named.length, `the summary named ${named.length} clipboard formats: ${s}`).toBe(1);
    // And it says so, rather than silently dropping one.
    expect(s).toMatch(/only one clipboard format is copied/i);
    // Non-vacuity: both rows really are selected.
    expect(screen.getByRole('button', { name: 'Copy for Epic' }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: 'Copy for Athena' }).getAttribute('aria-pressed')).toBe('true');
  });
});

describe('⚠️ the names the e2e pack pins are still here', () => {
  it('the heading is EXACTLY the string `29-sign-modal-geometry` matches', () => {
    // Matched with `exact: true` in three specs. The frames title the card
    // "Sign & deliver"; keeping the tested string is a recorded departure,
    // because a geometry gate on the signing surface outranks a card name.
    open();
    expect(screen.getByRole('heading', { name: 'Sign and deliver your note' })).toBeTruthy();
  });

  it('the attestation testids survive the row re-skin', () => {
    open();
    expect(screen.getByTestId('sign-attestation')).toBeTruthy();
    const t = screen.getByTestId('sign-attestation-toggle');
    expect(t.getAttribute('aria-pressed')).toBe('false');
  });

  it('the submit still answers to /sign & deliver/i and is disabled before attesting', () => {
    open();
    const submit = screen.getByRole('button', { name: /sign & deliver/i });
    expect((submit as HTMLButtonElement).disabled).toBe(true);
  });
});

// ============================================================================
// ⚠️ #188(4) — THE POST-SIGN ROWS ARE ACTIONS, NOT CHECKBOXES.
// ----------------------------------------------------------------------------
// Before signing a destination is a CHOICE you accumulate and then commit;
// after signing it is a THING YOU DO NOW, repeatedly. This is the half that is
// BEHAVIOUR rather than skin, which is why it landed as its own change — a
// re-skin that also changes what a click DOES is two claims wearing one diff.
// ============================================================================

describe('⚠️ #188(4) — after signing, every row commits itself', () => {
  const post = (over: Partial<Props> = {}) =>
    open({ signOnSubmit: false, triggerLabel: 'Export again', ...over });

  it('the rows are ACTIONS — no aria-pressed, because there is no state to press', () => {
    post();
    const row = screen.getByTestId('t4-action-pdf');
    expect(row).toBeTruthy();
    // ⚠️ A checkbox wearing different paint would still carry `aria-pressed`,
    // and a screen reader would announce a togglable state that does not
    // exist. The absence IS the claim here.
    expect(row.getAttribute('aria-pressed')).toBeNull();
  });

  it('every destination gets its own action row — all eight, per #188(1)', () => {
    post();
    for (const k of [
      'clipboard_epic', 'clipboard_athena', 'clipboard_cerner',
      'clipboard_eclinicalworks', 'clipboard_generic', 'pdf', 'docx', 'email',
    ]) {
      expect(screen.getByTestId(`t4-action-${k}`), `${k} has no action row`).toBeTruthy();
    }
  });

  it('⚠️ NO Cancel and NO primary button — there is nothing left to confirm', () => {
    post();
    expect(screen.queryByTestId('t4-submit'), 'a primary button would re-deliver a selection nobody can see').toBeNull();
    expect(screen.queryByRole('button', { name: /^cancel$/i })).toBeNull();
    // Non-vacuity: the PRE-sign state still has both.
    open();
    expect(screen.getByTestId('t4-submit')).toBeTruthy();
  });

  it('the PRE-sign state still uses checkboxes — the shift is post-only', () => {
    open();
    expect(screen.queryByTestId('t4-action-pdf')).toBeNull();
    expect(
      screen.getByRole('button', { name: 'Download PDF' }).getAttribute('aria-pressed'),
    ).toBeTruthy();
  });

  it('⚠️ one delivery at a time — a click disables every row while it runs', async () => {
    // Two concurrent clipboard writes race, and the second silently wins. The
    // pre-sign state has the same rule for the same reason.
    let release: (v: Response) => void = () => {};
    vi.spyOn(globalThis, 'fetch').mockReturnValue(
      new Promise<Response>((res) => { release = res; }),
    );
    post();
    fireEvent.click(screen.getByTestId('t4-action-clipboard_epic'));
    await Promise.resolve();
    expect(
      (screen.getByTestId('t4-action-docx') as HTMLButtonElement).disabled,
      'a second delivery could start while the first was in flight',
    ).toBe(true);
    expect(screen.getByTestId('t4-action-clipboard_epic').getAttribute('data-pending')).toBe('true');
    release(new Response(JSON.stringify({ text: 'x' }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
  });

  it('the safety caption survives into the post state too', () => {
    // #188(2) is not a pre-sign-only rule.
    post();
    expect(screen.getByTestId('t4-caption-email').textContent).toContain(
      "Don't use for patient communication",
    );
  });
});

// ============================================================================
// ⚠️ THE POST-STATE PASS'S FINDINGS, AS ARMS.
// ----------------------------------------------------------------------------
// Three of these were regressions this change introduced on the surface that
// DELIVERS a signed clinical note, and none of the six arms above could see
// any of them.
// ============================================================================

describe('⚠️ the post state never claims a delivery it did not make', () => {
  const post = (over: Partial<Props> = {}) =>
    open({ signOnSubmit: false, triggerLabel: 'Export again', ...over });

  const okJson = (body: unknown) =>
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });

  it('⚠️ THE DELIVERY SUMMARY IS GONE AFTER SIGNING — it named a set nobody sends', () => {
    // It was rendered UNGATED while only the line beneath it was gated, so a
    // signed visit permanently showed "Delivery: Copy for Epic • Download PDF"
    // — the DEFAULT set — naming two destinations that received nothing and
    // omitting whichever one the doctor had just clicked. `selected` cannot
    // move post-sign because the checkboxes are gone, so it was a CONSTANT
    // false claim, not a stale one.
    post();
    expect(screen.queryByTestId('t4-delivery-summary')).toBeNull();
    expect(screen.getByTestId('t4-post-footer')).toBeTruthy();
    // Non-vacuity: it IS still there before signing, where it is true.
    open();
    expect(screen.getByTestId('t4-delivery-summary')).toBeTruthy();
  });

  it('⚠️ A BLOCKED CLIPBOARD DOES NOT REPORT "Delivered"', async () => {
    // `applyBrowserSideDeliveries` reports a blocked clipboard by toast and
    // does NOT throw — right for the sign path, which must not fail a
    // signature over it. But the row's success toast fires AFTER, so the
    // doctor saw "Copy blocked" and then "Delivered — Copy for Epic", with the
    // affirmative one last, while the clipboard still held whatever it held
    // before.
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(okJson({ text: 'note text' }));
    const write = vi.fn().mockRejectedValue(new Error('NotAllowedError'));
    Object.defineProperty(globalThis.navigator, 'clipboard', {
      value: { writeText: write }, configurable: true,
    });
    post();
    fireEvent.click(screen.getByTestId('t4-action-clipboard_epic'));
    await new Promise((r) => setTimeout(r, 50));

    const successes = (toast.success as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(
      successes.length,
      `the row claimed success after a blocked clipboard: ${JSON.stringify(successes)}`,
    ).toBe(0);
    expect((toast.error as unknown as { mock: { calls: unknown[][] } }).mock.calls.length)
      .toBeGreaterThan(0);
  });

  it('⚠️ A DOWNLOAD SAYS "Download started", NOT "Delivered" — nothing observed it', async () => {
    // `pdf`/`docx` fire an `<a download>` with NO error channel, and
    // `prepareDeliverOnly` makes no request for them at all. A 503 from the
    // PDF route (Gotenberg down), a 401 on an expired session, a 500 — every
    // one returns JSON the anchor silently discards. "Delivered" asserts
    // something this code cannot see; the honest fix is filed as F-T4-2.
    post();
    fireEvent.click(screen.getByTestId('t4-action-pdf'));
    await new Promise((r) => setTimeout(r, 50));
    const calls = (toast.success as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(calls.length).toBe(1);
    expect(calls[0][0]).toBe('Download started');
    expect(calls[0][0]).not.toBe('Delivered');
  });

  it('a CLIPBOARD success still says "Delivered" — the distinction is observability', async () => {
    // Non-vacuity for the arm above: the honest label is not applied to
    // everything, only to what cannot be observed.
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(okJson({ text: 'note text' }));
    Object.defineProperty(globalThis.navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) }, configurable: true,
    });
    post();
    fireEvent.click(screen.getByTestId('t4-action-clipboard_athena'));
    await new Promise((r) => setTimeout(r, 50));
    const calls = (toast.success as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(calls.length).toBe(1);
    expect(calls[0][0]).toBe('Delivered');
  });

  it('⚠️ TWO CLICKS IN ONE BATCH DELIVER ONCE — the state read was a stale closure', async () => {
    // `if (rowPending !== null) return` reads whatever the value was when the
    // callback was last memoised, so two clicks dispatched inside one React
    // batch both saw `null` and both proceeded. The rendered `disabled` is the
    // guard a real user hits; the ref is the guard for anything faster than a
    // render.
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(okJson({ text: 't' }));
    Object.defineProperty(globalThis.navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) }, configurable: true,
    });
    post();
    const row = screen.getByTestId('t4-action-clipboard_cerner');
    // ⚠️ NATIVE DISPATCH, NOT `fireEvent` — and that difference is the arm.
    // `fireEvent` wraps each click in `act()`, which flushes the state update
    // and re-renders the button as `disabled`, so the second click lands on a
    // dead control and the arm passes WITH OR WITHOUT the guard. Dispatching
    // twice in one tick is what actually puts two handler invocations inside a
    // single React batch, which is the condition the ref exists for.
    row.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    row.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await new Promise((r) => setTimeout(r, 60));
    expect(
      (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls.length,
      'two clicks in one batch started two deliveries',
    ).toBe(1);
  });
});

// ============================================================================
// ⚠️ THE HALF THIS CHANGE ASSERTS AND DOES NOT TOUCH.
// ----------------------------------------------------------------------------
// `applyBrowserSideDeliveries` was widened from `Promise<void>` to
// `Promise<Destination[]>` so the per-row action could SEE a browser-side
// failure it previously only toasted. That is a signature change on a function
// the SIGN path also calls — the surface that commits a clinical signature.
//
// The claim "the sign path is unchanged" was written in a comment on the
// function and in the PR's §2.5 row, and measured NOWHERE. An asserted
// negative half needs its own measurement.
// ============================================================================

describe('⚠️ widening the return type did not change the SIGN path', () => {
  const okJson = (body: unknown) =>
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });

  it('⚠️ A BLOCKED CLIPBOARD STILL REPORTS A CLEAN "Signed"', async () => {
    // ⚠️ THE FIRST VERSION OF THIS ARM NAMED THE WRONG PROPERTY, AND THE
    // MUTATION IS WHAT SAID SO. It claimed to prove "a rethrow cannot fail the
    // signature" — but the sign path calls `applyBrowserSideDeliveries` as a
    // VOIDED fire-and-forget with its own `.catch`, AFTER the outcome toast has
    // already fired. Rethrowing there is structurally unable to reach the
    // signature, so that mutation redded nothing and proved nothing.
    //
    // The refactor the widened return type actually invites is different, and
    // it is the one worth a gate: *now that it reports failures, fold them into
    // the outcome*. Hoist the call above the classification, add its failures
    // to `failedEntries`, and a doctor whose browser blocked the clipboard is
    // told "Signed — some destinations failed" about a signature that was
    // committed cleanly server-side.
    //
    // So the property is not "the submit does not throw". It is: THE OUTCOME
    // TOAST FOR THE SIGNATURE IS INDEPENDENT OF BROWSER-SIDE DELIVERY RESULTS.
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      okJson({
        signedAt: '2026-09-05T00:00:00.000Z',
        clipboardTexts: { clipboard_epic: 'note text' },
      }),
    );
    Object.defineProperty(globalThis.navigator, 'clipboard', {
      value: { writeText: vi.fn().mockRejectedValue(new Error('NotAllowedError')) },
      configurable: true,
    });

    open({ attested: true });
    fireEvent.click(screen.getByTestId('t4-submit'));
    await new Promise((r) => setTimeout(r, 60));

    const successes = (toast.success as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    const warnings = (toast.warning as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(
      successes.some((c) => c[0] === 'Signed'),
      `the signature was not reported cleanly: success=${JSON.stringify(successes)} warning=${JSON.stringify(warnings)}`,
    ).toBe(true);
    // And it is not ALSO downgraded — a fold-in refactor emits the warning
    // instead, so pinning both directions is what makes the arm bite.
    expect(
      warnings.some((c) => typeof c[0] === 'string' && /some destinations failed/i.test(c[0] as string)),
      'the browser-side block was folded into the signature outcome',
    ).toBe(false);

    // ⚠️ NON-VACUITY, AND IT IS THE WHOLE ARM. Without this the test passes
    // just as happily when the clipboard was never reached at all — in which
    // case it measures nothing about swallowing, only that signing works.
    expect(
      (toast.error as unknown as { mock: { calls: unknown[][] } }).mock.calls
        .some((c) => c[0] === 'Copy blocked'),
      'the clipboard never failed, so this arm proved nothing about the swallow',
    ).toBe(true);
  });
});
