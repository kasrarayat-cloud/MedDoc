import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  refresh: vi.fn(),
  signOutAction: vi.fn(),
  signOutAllDevicesAction: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mocks.push, refresh: mocks.refresh }),
}));

vi.mock('sonner', () => ({
  toast: { error: mocks.toastError, success: mocks.toastSuccess },
}));

vi.mock('@/actions/session', () => ({
  signOutAction: mocks.signOutAction,
  signOutAllDevicesAction: mocks.signOutAllDevicesAction,
}));

import { SessionPanel } from './session-panel';

const panelProps = {
  ipAddress: '192.0.2.10',
  browser: 'Synthetic Browser',
  os: 'Synthetic OS',
  locationLabel: 'Synthetic location',
  loggedInAtIso: '2026-07-20T10:00:00.000Z',
  expiresAtIso: '2026-07-21T10:00:00.000Z',
  lastActiveAtIso: '2026-07-20T10:05:00.000Z',
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.signOutAction.mockResolvedValue({ ok: true });
  mocks.signOutAllDevicesAction.mockResolvedValue({ ok: true });
});

describe('SessionPanel revocation feedback', () => {
  it('surfaces the typed retryable current-session failure without success or navigation', async () => {
    mocks.signOutAction.mockResolvedValue({
      ok: false,
      code: 'SESSION_REVOCATION_FAILED',
      retryable: true,
      message: 'We could not securely end your session. Please try again.',
    });
    render(<SessionPanel {...panelProps} />);

    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));

    await waitFor(() =>
      expect(mocks.toastError).toHaveBeenCalledWith(
        'Sign-out was not completed',
        {
          description:
            'We could not securely end your session. Please try again.',
        },
      ),
    );
    expect(mocks.toastSuccess).not.toHaveBeenCalled();
    expect(mocks.push).not.toHaveBeenCalled();
    expect(mocks.refresh).not.toHaveBeenCalled();
  });

  it('surfaces the typed retryable all-device failure without success or navigation', async () => {
    mocks.signOutAllDevicesAction.mockResolvedValue({
      ok: false,
      code: 'SESSION_REVOCATION_FAILED',
      retryable: true,
      message: 'We could not securely end your session. Please try again.',
    });
    render(<SessionPanel {...panelProps} />);

    fireEvent.click(
      screen.getByRole('button', { name: 'Sign out all devices' }),
    );

    await waitFor(() =>
      expect(mocks.toastError).toHaveBeenCalledWith(
        'Sessions were not revoked',
        {
          description:
            'We could not securely end your session. Please try again.',
        },
      ),
    );
    expect(mocks.toastSuccess).not.toHaveBeenCalled();
    expect(mocks.push).not.toHaveBeenCalled();
    expect(mocks.refresh).not.toHaveBeenCalled();
  });

  it('retains success feedback and navigation after confirmed revocation', async () => {
    render(<SessionPanel {...panelProps} />);

    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));

    await waitFor(() =>
      expect(mocks.toastSuccess).toHaveBeenCalledWith('Signed out'),
    );
    expect(mocks.toastError).not.toHaveBeenCalled();
    expect(mocks.push).toHaveBeenCalledWith('/login');
    expect(mocks.refresh).toHaveBeenCalledTimes(1);
  });
});
