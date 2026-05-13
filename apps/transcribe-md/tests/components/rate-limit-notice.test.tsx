// ============================================================================
// RateLimitNotice — countdown + auto-clear + copy variants
// ----------------------------------------------------------------------------
// Verifies the recovery UX: when a 429 fires, the doctor sees a live
// countdown that decrements each second, and the parent form's
// `onExpire` callback fires at zero so the submit button can re-enable.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, act } from '@testing-library/react';

import { RateLimitNotice } from '@/components/rate-limit-notice';

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('RateLimitNotice — rendering + copy', () => {
  it('renders the countdown digit in seconds when retryAfter < 60', () => {
    render(<RateLimitNotice retryAfterSec={27} resource="patients" />);
    expect(screen.getByText(/Pause briefly/)).toBeInTheDocument();
    expect(screen.getByText(/27 s/)).toBeInTheDocument();
  });

  it('switches to the "long wait" copy for retryAfter > 60', () => {
    render(<RateLimitNotice retryAfterSec={300} resource="patients" />);
    expect(screen.getByText(/form will re-enable in/)).toBeInTheDocument();
    expect(screen.getByText(/5 min/)).toBeInTheDocument();
    expect(screen.queryByText(/Pause briefly/)).not.toBeInTheDocument();
  });

  it('uses the long-wait copy when limitType=hourly regardless of remaining', () => {
    // Hourly window — even if the user is only 30s from the reset,
    // we frame it as "form will re-enable in" not "pause briefly"
    // because the LIMIT pattern is hourly, not bursty.
    render(<RateLimitNotice retryAfterSec={45} limitType="hourly" resource="patients" />);
    expect(screen.getByText(/form will re-enable in/)).toBeInTheDocument();
  });

  it('uses the resource prop in the headline', () => {
    render(<RateLimitNotice retryAfterSec={5} resource="visits" />);
    expect(screen.getByText(/creating visits faster/)).toBeInTheDocument();
  });

  it('requires the resource prop to be passed explicitly', () => {
    // No default — pinning the contract per the auditor's W3 finding.
    // Resource is required so a future reuse in visit-create can't
    // silently fall back to "patients".
    render(<RateLimitNotice retryAfterSec={5} resource="patients" />);
    expect(screen.getByText(/creating patients faster/)).toBeInTheDocument();
  });

  it('survives a flurry of parent re-renders without resetting the timer (B1 regression)', () => {
    // The auditor's BLOCKER: depending on `onExpire` in the tick
    // effect makes a fresh closure each parent render restart the
    // 1-second timer, stalling the countdown forever. The ref-based
    // fix below means the timer only depends on `remaining`.
    let onExpire = vi.fn();
    const { rerender } = render(
      <RateLimitNotice retryAfterSec={3} resource="patients" onExpire={onExpire} />,
    );
    // Simulate parent re-renders mid-countdown (e.g., doctor typing
    // in another field of the form while the countdown ticks). Each
    // re-render passes a fresh `onExpire` closure.
    for (let i = 0; i < 3; i++) {
      act(() => {
        vi.advanceTimersByTime(500);
      });
      onExpire = vi.fn();
      rerender(
        <RateLimitNotice
          retryAfterSec={3}
          resource="patients"
          onExpire={onExpire}
        />,
      );
      act(() => {
        vi.advanceTimersByTime(500);
      });
    }
    // After 3 simulated re-renders × 1000ms total, the countdown
    // should have ticked down to ~0 and expired. Pre-fix, the timer
    // would have been continuously reset and the countdown would
    // still be at 3.
    expect(onExpire).toHaveBeenCalledTimes(1);
  });

  it('does NOT double-fire onExpire across simulated StrictMode re-mount', () => {
    const onExpire = vi.fn();
    const { rerender } = render(
      <RateLimitNotice retryAfterSec={1} resource="patients" onExpire={onExpire} />,
    );
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(onExpire).toHaveBeenCalledTimes(1);
    // Simulate StrictMode-style extra effect run by re-rendering
    // with the same props.
    rerender(<RateLimitNotice retryAfterSec={1} resource="patients" onExpire={onExpire} />);
    expect(onExpire).toHaveBeenCalledTimes(1);
  });

  it('renders as aria-live polite for accessibility', () => {
    render(<RateLimitNotice retryAfterSec={10} resource="patients" />);
    const region = screen.getByRole('status');
    expect(region).toHaveAttribute('aria-live', 'polite');
  });
});

describe('RateLimitNotice — countdown behavior', () => {
  it('decrements every second', () => {
    render(<RateLimitNotice retryAfterSec={5} resource="patients" />);
    expect(screen.getByText(/5 s/)).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText(/4 s/)).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText(/3 s/)).toBeInTheDocument();
  });

  it('unmounts itself when the countdown reaches 0', () => {
    const { container } = render(<RateLimitNotice retryAfterSec={2} resource="patients" />);
    expect(container.querySelector('[role="status"]')).not.toBeNull();
    // Advance in 1s steps so each setTimeout's setState commits before
    // the next effect schedules its successor — a single
    // advanceTimersByTime(2000) only fires the first cascade tick.
    for (let i = 0; i < 2; i++) {
      act(() => {
        vi.advanceTimersByTime(1000);
      });
    }
    expect(container.querySelector('[role="status"]')).toBeNull();
  });

  it('fires onExpire exactly once when the countdown reaches 0', () => {
    const onExpire = vi.fn();
    render(<RateLimitNotice retryAfterSec={3} resource="patients" onExpire={onExpire} />);
    expect(onExpire).not.toHaveBeenCalled();
    for (let i = 0; i < 3; i++) {
      act(() => {
        vi.advanceTimersByTime(1000);
      });
    }
    expect(onExpire).toHaveBeenCalledTimes(1);
  });

  it('ceils a fractional retryAfter input', () => {
    render(<RateLimitNotice retryAfterSec={2.3} resource="patients" />);
    expect(screen.getByText(/3 s/)).toBeInTheDocument();
  });

  it('renders nothing and fires onExpire immediately when retryAfterSec <= 0', () => {
    const onExpire = vi.fn();
    const { container } = render(
      <RateLimitNotice retryAfterSec={0} resource="patients" onExpire={onExpire} />,
    );
    expect(container.querySelector('[role="status"]')).toBeNull();
    // useEffect runs after mount; advance microtasks
    act(() => {
      vi.advanceTimersByTime(0);
    });
    expect(onExpire).toHaveBeenCalled();
  });

  it('resets the countdown if retryAfterSec prop changes mid-countdown (fresh 429)', () => {
    const { rerender } = render(<RateLimitNotice retryAfterSec={10} resource="patients" />);
    for (let i = 0; i < 3; i++) {
      act(() => {
        vi.advanceTimersByTime(1000);
      });
    }
    expect(screen.getByText(/7 s/)).toBeInTheDocument();
    // Fresh 429 with a new (longer) window
    rerender(<RateLimitNotice retryAfterSec={30} resource="patients" />);
    expect(screen.getByText(/30 s/)).toBeInTheDocument();
  });
});
