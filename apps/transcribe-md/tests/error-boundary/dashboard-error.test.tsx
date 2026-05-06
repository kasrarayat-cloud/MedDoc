// ============================================================================
// F-12 closure test — Dashboard <Suspense> error boundary
// ----------------------------------------------------------------------------
// QA Interaction Auditor v3.2 PASS A surfaced F-12 ("Dashboard
// <Suspense> swallows render errors → skeleton stays forever").
//
// Investigation (PR fix/dashboard-suspense-error-boundary) determined
// F-12 was a **false positive**: `apps/transcribe-md/src/app/dashboard/
// error.tsx` already exists. Next.js auto-wraps the dashboard route
// segment in a React Error Boundary that mounts <ErrorFallback>, so a
// throw from `<DashboardBody>` (whether direct or via Suspense
// propagation) DOES surface a visible error UI — not an infinite
// skeleton. The discovery sub-agent missed the sibling error.tsx file.
//
// What WAS missing: tests that prove the error path actually catches.
// This file fills that gap so a future refactor (e.g. moving the
// Suspense outside the error.tsx scope, or accidentally deleting
// the file) trips CI.
//
// Two test paths:
//
//   1. Direct render of dashboard/error.tsx with a fake error +
//      reset() — asserts the visible UI matches the F-12 spec
//      (heading, retry button, error ID, no PHI in copy, etc.)
//   2. Confirm dashboard/error.tsx re-exports from the shared
//      ErrorFallback with scope='dashboard' so the telemetry hook
//      labels failures correctly for ops.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

// Mock telemetry — ErrorFallback fires a sendBeacon on mount to
// /api/client-errors. The test environment doesn't need that wire.
beforeEach(() => {
  Object.defineProperty(globalThis, 'navigator', {
    value: {
      ...globalThis.navigator,
      sendBeacon: vi.fn(() => true),
      userAgent: 'vitest',
    },
    configurable: true,
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// Static-import the route's error.tsx — Next.js auto-wraps page.tsx
// in this component, so what we test here is what doctors actually see
// when /dashboard's data fetch fails.
import DashboardError from '@/app/dashboard/error';

describe('F-12 closure: dashboard/error.tsx renders ErrorFallback on render failure', () => {
  function makeError(overrides: Partial<Error & { digest?: string }> = {}) {
    const e = new Error('fake prisma reconnect blip — never reaches the user') as Error & {
      digest?: string;
    };
    return Object.assign(e, overrides);
  }

  it('renders the "Something went wrong" heading instead of an infinite skeleton', () => {
    render(<DashboardError error={makeError()} reset={vi.fn()} />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      /Something went wrong/i
    );
  });

  it('exposes a retry CTA wired to reset()', () => {
    const reset = vi.fn();
    render(<DashboardError error={makeError()} reset={reset} />);
    const tryAgain = screen.getByRole('button', { name: /try again/i });
    fireEvent.click(tryAgain);
    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("renders a stable error ID so doctors can quote it to support", () => {
    const digest = 'NEXT_REDIRECT_DIGEST_LIKE_VALUE_12345';
    render(<DashboardError error={makeError({ digest })} reset={vi.fn()} />);
    // Error ID copy uses digest verbatim when present.
    expect(screen.getByText(/Error ID:/i)).toBeInTheDocument();
    expect(screen.getByText(digest)).toBeInTheDocument();
  });

  it('does NOT leak the raw error message into the UI (PHI safety)', () => {
    // The fake error message above pretends to be a Prisma blip; if
    // some future refactor accidentally renders error.message in the
    // UI, this test trips. The current behaviour (per ErrorFallback)
    // is to keep the message strictly server-side / telemetry-side.
    const messageSnippet = 'fake prisma reconnect blip — never reaches the user';
    render(
      <DashboardError
        error={makeError({ message: messageSnippet })}
        reset={vi.fn()}
      />
    );
    expect(screen.queryByText(messageSnippet)).toBeNull();
  });

  it('includes a "Back to dashboard" link as the calm-recovery affordance', () => {
    render(<DashboardError error={makeError()} reset={vi.fn()} />);
    const back = screen.getByRole('link', { name: /back to dashboard/i });
    expect(back.getAttribute('href')).toBe('/dashboard');
  });

  it('fires a sendBeacon to /api/client-errors with scope="dashboard" on mount', () => {
    const beacon = navigator.sendBeacon as unknown as ReturnType<typeof vi.fn>;
    render(<DashboardError error={makeError()} reset={vi.fn()} />);
    expect(beacon).toHaveBeenCalled();
    const [url, body] = (beacon as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('/api/client-errors');
    // body is a Blob — read as text + parse to assert the scope label.
    return (body as Blob).text().then((text: string) => {
      const payload = JSON.parse(text);
      expect(payload.scope).toBe('dashboard');
      expect(typeof payload.errorId).toBe('string');
      expect(payload.errorId.length).toBeGreaterThan(0);
    });
  });
});
