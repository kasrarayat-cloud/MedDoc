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

import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
}));

import { SignAndSendModal } from '../sign-and-send-modal';

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
