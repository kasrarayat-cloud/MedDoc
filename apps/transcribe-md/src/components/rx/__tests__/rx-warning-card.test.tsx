import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import type { RxWarning } from '../rx-warning-card';

// ----------------------------------------------------------------------------
// Module-level mock for the server action. The modal imports
// recordOverride at module load; we override it before importing the
// components under test.
// ----------------------------------------------------------------------------

const recordOverrideMock = vi.fn();

vi.mock('@/lib/rx-warning-audit', () => ({
  recordOverride: (...args: unknown[]) => recordOverrideMock(...args),
}));
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    message: vi.fn(),
  },
}));

// Import AFTER the mocks are set up.
import { RxWarningCard } from '../rx-warning-card';

// ----------------------------------------------------------------------------
// Fixtures
// ----------------------------------------------------------------------------

function criticalFixture(overrides: Partial<RxWarning> = {}): RxWarning {
  return {
    id: 'test-critical-1',
    rxLineNumber: 2,
    sev: 'critical',
    headline: 'Cannot verify medication.',
    action: 'Do NOT prescribe until confirmed.',
    heard: 'abirrobing',
    guess: 'possibly ibuprofen?',
    transcriberConfidence: 0.42,
    confidenceThreshold: 0.7,
    risks: [
      {
        parts: [
          { t: 'Patient is on ' },
          { t: 'Valsartan + HCTZ', b: true },
          { t: '.' },
        ],
        outcome: [
          { t: 'Adds risk of ' },
          { t: 'AKI', b: true },
          { t: '.' },
        ],
      },
    ],
    nextStep: 'Confirm medication name verbally with prescriber.',
    details: ['Raw transcript token had confidence 0.42.'],
    source: 'Transcript 14:22',
    ...overrides,
  };
}

function warningFixture(overrides: Partial<RxWarning> = {}): RxWarning {
  return {
    id: 'test-warning-1',
    rxLineNumber: 4,
    sev: 'warning',
    headline: 'Dose outside typical range.',
    action: 'Double-check dose.',
    details: ['Exceeds upper bound by 50%.'],
    ...overrides,
  };
}

function infoFixture(overrides: Partial<RxWarning> = {}): RxWarning {
  return {
    id: 'test-info-1',
    rxLineNumber: 7,
    sev: 'info',
    headline: 'Prescriber preference applied.',
    action: 'Using brand-name per default.',
    ...overrides,
  };
}

// ----------------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------------

function focusCardButton(container: HTMLElement) {
  const btn = container.querySelector('button');
  if (btn) (btn as HTMLButtonElement).focus();
}

function pressKey(key: string) {
  fireEvent.keyDown(document, { key });
}

beforeEach(() => {
  recordOverrideMock.mockReset();
});
afterEach(() => {
  vi.restoreAllMocks();
});

// ----------------------------------------------------------------------------
// Tests
// ----------------------------------------------------------------------------

describe('RxWarningCard · rendering by severity', () => {
  it('renders critical variant with role="alert" and all 8 regions', () => {
    const { container } = render(
      <RxWarningCard
        warning={criticalFixture()}
        visitId="visit-1"
        onEdit={() => {}}
        onCall={() => {}}
      />
    );
    const section = container.querySelector('section');
    expect(section).toHaveAttribute('role', 'alert');
    expect(section).toHaveAttribute('aria-live', 'assertive');
    // Region 1 header — icon + badge + field + headline
    expect(screen.getByText('Critical')).toBeInTheDocument();
    expect(screen.getByText('Rx · Line 2')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent(
      'Cannot verify medication.'
    );
    // Region 3 action tile
    expect(screen.getByText('Do NOT prescribe until confirmed.')).toBeInTheDocument();
    // Region 4 transcribed
    expect(screen.getByText('Heard')).toBeInTheDocument();
    expect(screen.getByText('Phonetic guess')).toBeInTheDocument();
    // Region 5 risks (count label)
    expect(screen.getByText('Patient-specific risks · 1')).toBeInTheDocument();
    // Region 6 next step
    expect(screen.getByText(/Confirm medication name/)).toBeInTheDocument();
    // Region 7 details toggle (collapsed by default)
    const toggle = screen.getByRole('button', { name: /Show clinical reasoning/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    // Region 8 actions
    expect(screen.getByRole('button', { name: /Edit medication/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Call provider/ })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Override & sign anyway/ })
    ).toBeInTheDocument();
  });

  it('renders warning variant with role="status" + polite live region', () => {
    const { container } = render(
      <RxWarningCard
        warning={warningFixture()}
        visitId="visit-1"
        onEdit={() => {}}
        onCall={() => {}}
        onAcknowledge={() => {}}
      />
    );
    const section = container.querySelector('section');
    expect(section).toHaveAttribute('role', 'status');
    expect(section).toHaveAttribute('aria-live', 'polite');
    expect(screen.getByRole('button', { name: /Acknowledge/ })).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Override/ })
    ).not.toBeInTheDocument();
  });

  it('renders info variant with role="note" and only header + action tile + dismiss', () => {
    const { container } = render(
      <RxWarningCard
        warning={infoFixture()}
        visitId="visit-1"
        onDismiss={() => {}}
      />
    );
    const section = container.querySelector('section');
    expect(section).toHaveAttribute('role', 'note');
    // Info suppresses region 4-7; only dismiss button in region 8.
    expect(screen.queryByText(/Patient-specific risks/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Show clinical reasoning/ })
    ).not.toBeInTheDocument();
    // Match the region-8 action button, not the header's X
    // ("Dismiss warning"). Regex anchors to the exact accessible name.
    expect(
      screen.getByRole('button', { name: /^Dismiss$/ })
    ).toBeInTheDocument();
  });
});

describe('RxWarningCard · transcriberConfidence chip', () => {
  it('renders the chip when both values are defined', () => {
    render(<RxWarningCard warning={criticalFixture()} visitId="v" />);
    expect(screen.getByText('42%')).toBeInTheDocument();
  });

  it('hides the chip when confidenceThreshold is missing', () => {
    render(
      <RxWarningCard
        warning={criticalFixture({ confidenceThreshold: undefined })}
        visitId="v"
      />
    );
    expect(screen.queryByText('42%')).not.toBeInTheDocument();
  });

  it('hides the chip when transcriberConfidence is missing', () => {
    render(
      <RxWarningCard
        warning={criticalFixture({ transcriberConfidence: undefined })}
        visitId="v"
      />
    );
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });
});

describe('RxWarningCard · dismiss X affordance', () => {
  it('omits dismiss X on critical even when onDismiss is supplied', () => {
    render(
      <RxWarningCard
        warning={criticalFixture()}
        visitId="v"
        onDismiss={() => {}}
      />
    );
    expect(
      screen.queryByRole('button', { name: /Dismiss warning/ })
    ).not.toBeInTheDocument();
  });

  it('renders dismiss X on warning when onDismiss is supplied', () => {
    render(
      <RxWarningCard
        warning={warningFixture()}
        visitId="v"
        onDismiss={() => {}}
      />
    );
    expect(
      screen.getByRole('button', { name: /Dismiss warning/ })
    ).toBeInTheDocument();
  });
});

describe('RxWarningCard · keyboard shortcuts', () => {
  it('? toggles details (critical)', () => {
    const { container } = render(
      <RxWarningCard warning={criticalFixture()} visitId="v" onEdit={() => {}} />
    );
    const toggle = screen.getByRole('button', { name: /Show clinical reasoning/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    focusCardButton(container);
    pressKey('?');
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
  });

  it('E fires onEdit on critical', () => {
    const onEdit = vi.fn();
    const { container } = render(
      <RxWarningCard warning={criticalFixture()} visitId="v" onEdit={onEdit} />
    );
    focusCardButton(container);
    pressKey('E');
    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it('E fires onEdit on warning', () => {
    const onEdit = vi.fn();
    const { container } = render(
      <RxWarningCard warning={warningFixture()} visitId="v" onEdit={onEdit} />
    );
    focusCardButton(container);
    pressKey('E');
    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it('E is a no-op on info', () => {
    const onEdit = vi.fn();
    const { container } = render(
      <RxWarningCard
        warning={infoFixture()}
        visitId="v"
        onEdit={onEdit}
        onDismiss={() => {}}
      />
    );
    focusCardButton(container);
    pressKey('E');
    expect(onEdit).not.toHaveBeenCalled();
  });

  it('C fires onCall on critical + warning', () => {
    const onCallA = vi.fn();
    const onCallB = vi.fn();
    const { unmount } = render(
      <RxWarningCard warning={criticalFixture()} visitId="v" onCall={onCallA} />
    );
    focusCardButton(document.body);
    pressKey('C');
    expect(onCallA).toHaveBeenCalledTimes(1);
    unmount();

    render(
      <RxWarningCard warning={warningFixture()} visitId="v" onCall={onCallB} />
    );
    focusCardButton(document.body);
    pressKey('C');
    expect(onCallB).toHaveBeenCalledTimes(1);
  });

  it('A fires onAcknowledge only on warning', () => {
    const onAckCritical = vi.fn();
    const onAckInfo = vi.fn();
    const onAckWarning = vi.fn();

    const { unmount: u1 } = render(
      <RxWarningCard
        warning={criticalFixture()}
        visitId="v"
        onAcknowledge={onAckCritical}
      />
    );
    focusCardButton(document.body);
    pressKey('A');
    expect(onAckCritical).not.toHaveBeenCalled();
    u1();

    const { unmount: u2 } = render(
      <RxWarningCard
        warning={infoFixture()}
        visitId="v"
        onAcknowledge={onAckInfo}
        onDismiss={() => {}}
      />
    );
    focusCardButton(document.body);
    pressKey('A');
    expect(onAckInfo).not.toHaveBeenCalled();
    u2();

    render(
      <RxWarningCard
        warning={warningFixture()}
        visitId="v"
        onAcknowledge={onAckWarning}
      />
    );
    focusCardButton(document.body);
    pressKey('A');
    expect(onAckWarning).toHaveBeenCalledTimes(1);
  });

  it('D dismisses info', () => {
    const onDismiss = vi.fn();
    const { container } = render(
      <RxWarningCard warning={infoFixture()} visitId="v" onDismiss={onDismiss} />
    );
    focusCardButton(container);
    pressKey('D');
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('ignores shortcuts while modal is open (except Escape)', async () => {
    recordOverrideMock.mockResolvedValue({ ok: true, auditId: 'audit-1' });
    const onEdit = vi.fn();
    const { container } = render(
      <RxWarningCard
        warning={criticalFixture()}
        visitId="v"
        onEdit={onEdit}
      />
    );
    // Open the override modal via the button (synchronous state flip).
    const overrideBtn = screen.getByRole('button', {
      name: /Override & sign anyway/,
    });
    fireEvent.click(overrideBtn);
    // Modal open — textarea present.
    const textarea = await screen.findByLabelText(/Reason for override/i);
    expect(textarea).toBeInTheDocument();

    // Pressing E while modal is open must NOT fire onEdit.
    focusCardButton(container);
    pressKey('E');
    expect(onEdit).not.toHaveBeenCalled();
  });

  it('modifier keys suppress shortcuts', () => {
    const onEdit = vi.fn();
    const { container } = render(
      <RxWarningCard warning={criticalFixture()} visitId="v" onEdit={onEdit} />
    );
    focusCardButton(container);
    fireEvent.keyDown(document, { key: 'E', metaKey: true });
    fireEvent.keyDown(document, { key: 'E', ctrlKey: true });
    fireEvent.keyDown(document, { key: 'E', altKey: true });
    fireEvent.keyDown(document, { key: 'E', shiftKey: true });
    expect(onEdit).not.toHaveBeenCalled();
  });

  it('ignores shortcuts when focus is not inside the card', () => {
    const onEdit = vi.fn();
    render(
      <RxWarningCard warning={criticalFixture()} visitId="v" onEdit={onEdit} />
    );
    // Focus is on document.body — not inside the card.
    document.body.focus();
    pressKey('E');
    expect(onEdit).not.toHaveBeenCalled();
  });
});

describe('RxWarningCard · details expansion', () => {
  it('clicking the toggle flips aria-expanded', () => {
    render(
      <RxWarningCard warning={criticalFixture()} visitId="v" onEdit={() => {}} />
    );
    const toggle = screen.getByRole('button', { name: /Show clinical reasoning/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(toggle).toHaveTextContent(/Hide clinical reasoning/);
  });

  it('defaultOpen renders expanded on mount', () => {
    render(
      <RxWarningCard
        warning={criticalFixture()}
        visitId="v"
        defaultOpen
        onEdit={() => {}}
      />
    );
    const toggle = screen.getByRole('button', { name: /Hide clinical reasoning/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
  });

  it('does not render the toggle when info (no details region)', () => {
    render(
      <RxWarningCard
        warning={infoFixture()}
        visitId="v"
        onDismiss={() => {}}
      />
    );
    expect(
      screen.queryByRole('button', { name: /clinical reasoning/ })
    ).not.toBeInTheDocument();
  });
});

describe('RxWarningCard · override flow', () => {
  it('O key opens the override modal', async () => {
    const { container } = render(
      <RxWarningCard warning={criticalFixture()} visitId="v" onEdit={() => {}} />
    );
    focusCardButton(container);
    pressKey('O');
    const textarea = await screen.findByLabelText(/Reason for override/i);
    expect(textarea).toBeInTheDocument();
  });

  it('modal confirm is disabled until reason ≥ 10 chars', async () => {
    const { container } = render(
      <RxWarningCard warning={criticalFixture()} visitId="v" onEdit={() => {}} />
    );
    focusCardButton(container);
    pressKey('O');
    const textarea = (await screen.findByLabelText(
      /Reason for override/i
    )) as HTMLTextAreaElement;
    const confirm = screen.getByRole('button', { name: /Confirm override/ });

    expect(confirm).toBeDisabled();
    fireEvent.change(textarea, { target: { value: 'too short' } });
    expect(confirm).toBeDisabled();
    fireEvent.change(textarea, { target: { value: 'Patient already verified.' } });
    expect(confirm).toBeEnabled();
  });

  it('modal confirm calls recordOverride with the right payload', async () => {
    recordOverrideMock.mockResolvedValue({ ok: true, auditId: 'audit-42' });
    const onOverridden = vi.fn();
    const { container } = render(
      <RxWarningCard
        warning={criticalFixture()}
        visitId="visit-xyz"
        onOverridden={onOverridden}
      />
    );
    focusCardButton(container);
    pressKey('O');
    const textarea = await screen.findByLabelText(/Reason for override/i);
    fireEvent.change(textarea, {
      target: { value: 'Already verified verbally with pharmacy at 14:31.' },
    });
    const confirm = screen.getByRole('button', { name: /Confirm override/ });
    fireEvent.click(confirm);

    // Wait for async resolution (mocked resolve is next microtask).
    await new Promise((r) => setTimeout(r, 0));

    expect(recordOverrideMock).toHaveBeenCalledTimes(1);
    const payload = recordOverrideMock.mock.calls[0][0];
    expect(payload).toMatchObject({
      visitId: 'visit-xyz',
      warningId: 'test-critical-1',
      rxLineNumber: 2,
      severity: 'critical',
      headline: 'Cannot verify medication.',
    });
    expect(payload.reason).toContain('Already verified');
    expect(onOverridden).toHaveBeenCalledWith('audit-42');
  });

  it('modal cancel does NOT call recordOverride', async () => {
    const { container } = render(
      <RxWarningCard warning={criticalFixture()} visitId="v" />
    );
    focusCardButton(container);
    pressKey('O');
    await screen.findByLabelText(/Reason for override/i);
    const cancel = screen.getByRole('button', { name: /Cancel/i });
    fireEvent.click(cancel);
    expect(recordOverrideMock).not.toHaveBeenCalled();
  });

  it('modal stays open + shows inline error on { ok: false }', async () => {
    recordOverrideMock.mockResolvedValue({
      ok: false,
      error: 'Visit not found.',
    });
    const { container } = render(
      <RxWarningCard warning={criticalFixture()} visitId="v" />
    );
    focusCardButton(container);
    pressKey('O');
    const textarea = await screen.findByLabelText(/Reason for override/i);
    fireEvent.change(textarea, {
      target: { value: 'Reason long enough to pass the threshold.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Confirm override/ }));
    await new Promise((r) => setTimeout(r, 0));

    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText(/Visit not found/)).toBeInTheDocument();
    // Textarea still present — modal did not close.
    expect(
      screen.getByLabelText(/Reason for override/i)
    ).toBeInTheDocument();
  });
});

describe('RxWarningCard · keyboard hint chips', () => {
  it('renders O chip on the Override button (not ⇧O)', () => {
    render(<RxWarningCard warning={criticalFixture()} visitId="v" onEdit={() => {}} />);
    const overrideBtn = screen.getByRole('button', {
      name: /Override & sign anyway/,
    });
    expect(overrideBtn).toHaveTextContent('O');
    expect(overrideBtn).not.toHaveTextContent('⇧O');
  });

  it('renders A chip on the Acknowledge button (warning)', () => {
    render(
      <RxWarningCard
        warning={warningFixture()}
        visitId="v"
        onEdit={() => {}}
        onAcknowledge={() => {}}
      />
    );
    const ackBtn = screen.getByRole('button', { name: /Acknowledge/ });
    expect(ackBtn).toHaveTextContent('A');
  });
});
