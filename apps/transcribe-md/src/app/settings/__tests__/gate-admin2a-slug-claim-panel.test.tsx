// ============================================================================
// GATE — ADMIN-2a's CLAIM CONTROL: what is DRAWN.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE PROVES NOTHING ABOUT SECURITY. `claimable` decides what is
// rendered; `claimPracticeSlug` re-reads role and slug from the database, and
// `gate-admin2a-slug-claim` is where that is measured. What is proved here is
// that an owner is not offered a claim the server will refuse, and that the
// page does not tell a doctor an address is live when ADMIN-2 is not built.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL:
//   · a claimed practice is shown an input again        -> the claimed block
//   · the claimed state stops naming support            -> the claimed block
//   · the page claims the address is reachable          -> the honesty block
// ============================================================================

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));
vi.mock('@/actions/practice-settings', () => ({ claimPracticeSlug: vi.fn() }));

import { PracticeSlugClaim } from '../practice-slug-claim';

afterEach(() => cleanup());

describe('ADMIN-2a — the claim control', () => {
  it('a machine slug is offered the one-time claim, and shows what it is today', () => {
    render(<PracticeSlugClaim currentSlug="solo-k3j9x2-mz81qa" claimable />);
    expect(screen.getByTestId('practice-slug-input')).toBeTruthy();
    expect(screen.getByTestId('practice-slug-current').textContent).toBe('solo-k3j9x2-mz81qa');
    expect(screen.queryByTestId('practice-slug-claimed')).toBeNull();
  });

  it('⚠️ a claimed practice is shown the name READ-ONLY, and told support makes later changes', () => {
    render(<PracticeSlugClaim currentSlug="northside" claimable={false} />);
    expect(screen.queryByTestId('practice-slug-input')).toBeNull();
    expect(screen.getByTestId('practice-slug-value').textContent).toBe('northside');
    expect(screen.getByTestId('practice-slug-claimed').textContent).toMatch(/support/i);
  });

  it('⚠️ it never says the address is live — ADMIN-2 and the wildcard record do not exist', () => {
    const { container } = render(<PracticeSlugClaim currentSlug="solo-x-y" claimable />);
    const text = container.textContent ?? '';
    expect(text).toMatch(/not live yet/i);
    expect(text).not.toMatch(/\.quillmd\.com/i);
  });
});
