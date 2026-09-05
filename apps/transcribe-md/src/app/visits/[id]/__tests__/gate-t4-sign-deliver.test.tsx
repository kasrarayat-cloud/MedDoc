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
import { render, screen, within } from '@testing-library/react';

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
