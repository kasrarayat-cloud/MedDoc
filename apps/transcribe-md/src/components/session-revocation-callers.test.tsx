import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  getRecentVisits: vi.fn(),
  push: vi.fn(),
  refresh: vi.fn(),
  signOutAction: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mocks.push, refresh: mocks.refresh }),
}));

vi.mock('sonner', () => ({
  toast: { error: mocks.toastError, success: vi.fn() },
}));

vi.mock('@/actions/session', () => ({
  signOutAction: mocks.signOutAction,
}));

vi.mock('@/actions/command-palette', () => ({
  getRecentVisits: mocks.getRecentVisits,
}));

import { CommandPalette } from './command-palette';
import { UserMenu } from './user-menu';

const retryableFailure = {
  ok: false,
  code: 'SESSION_REVOCATION_FAILED',
  retryable: true,
  message: 'We could not securely end your session. Please try again.',
} as const;

const originalScrollIntoView = Object.getOwnPropertyDescriptor(
  HTMLElement.prototype,
  'scrollIntoView',
);

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    value: vi.fn(),
  });
  mocks.getRecentVisits.mockResolvedValue([]);
  mocks.signOutAction.mockResolvedValue(retryableFailure);
});

afterEach(() => {
  vi.unstubAllGlobals();
  if (originalScrollIntoView) {
    Object.defineProperty(
      HTMLElement.prototype,
      'scrollIntoView',
      originalScrollIntoView,
    );
  } else {
    delete (HTMLElement.prototype as { scrollIntoView?: unknown })
      .scrollIntoView;
  }
});

describe('session revocation action callers', () => {
  it('keeps the user menu on the current page and shows the typed failure', async () => {
    render(
      <UserMenu
        name="Synthetic Physician"
        email="synthetic@example.test"
      />,
    );

    fireEvent.pointerDown(
      screen.getByRole('button', { name: 'Open user menu' }),
      {
        button: 0,
        ctrlKey: false,
      },
    );
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Sign out' }));

    await waitFor(() =>
      expect(mocks.toastError).toHaveBeenCalledWith(
        'Sign-out was not completed',
        { description: retryableFailure.message },
      ),
    );
    expect(mocks.push).not.toHaveBeenCalled();
    expect(mocks.refresh).not.toHaveBeenCalled();
  });

  it('keeps the command-palette caller on the current page and shows the typed failure', async () => {
    render(<CommandPalette authed />);

    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
    fireEvent.click(await screen.findByText('Sign out'));

    await waitFor(() =>
      expect(mocks.toastError).toHaveBeenCalledWith(
        'Sign-out was not completed',
        { description: retryableFailure.message },
      ),
    );
    expect(mocks.push).not.toHaveBeenCalled();
    expect(mocks.refresh).not.toHaveBeenCalled();
  });
});
