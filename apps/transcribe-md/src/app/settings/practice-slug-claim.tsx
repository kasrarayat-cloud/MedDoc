'use client';

// ============================================================================
// ADMIN-2a — THE PRACTICE ADDRESS NAME, where a practice OWNER administers it.
// ----------------------------------------------------------------------------
// ⚠️ NO NEW DESIGN LANGUAGE. Composed from the members panel's own idioms —
// `qm-lin-btn`, `SpecularButton`, the bridged `--color-linear-*` tokens and the
// same inline-style shape — so it reads as part of the panel it sits beside.
//
// ⚠️ DRAWN FOR OWNERS ONLY, AND THE SERVER REFUSES ANYWAY. `claimable` decides
// what is RENDERED; `claimPracticeSlug` re-reads the role and the current slug
// from the database, because a prop is a claim the client makes about itself.
//
// ⚠️ THE ADDRESS IS NOT LIVE, AND THE WORDS SAY SO. ADMIN-2 (the subdomain
// itself) is not built and the wildcard DNS record does not exist, so this
// page must not tell a doctor their practice is reachable anywhere.
// ============================================================================

import { useActionState, useEffect, useRef } from 'react';
import { toast } from 'sonner';

import { SpecularButton } from '@/components/specular-button';
import { claimPracticeSlug, type SlugClaimState } from '@/actions/practice-settings';

const noteStyle: React.CSSProperties = {
  margin: '6px 0 0',
  fontSize: 12,
  color: 'var(--color-linear-text-3)',
};

export function PracticeSlugClaim({
  currentSlug,
  claimable,
}: {
  currentSlug: string;
  /** Computed on the SERVER from `isMachineSlug` — true only while the
   *  practice still carries the slug signup minted. */
  claimable: boolean;
}) {
  const [state, action, pending] = useActionState<SlugClaimState, FormData>(
    claimPracticeSlug,
    null,
  );
  const seen = useRef<SlugClaimState>(null);

  useEffect(() => {
    if (state === seen.current) return;
    seen.current = state;
    if (state?.ok === true) toast.success('Practice address name saved');
    // ⚠️ THE REFUSAL IS SPOKEN — silence would make a refused claim look saved.
    else if (state?.ok === false) toast.error(state.message);
  }, [state]);

  const claimedNow = state?.ok === true ? state.slug : null;

  return (
    <section
      data-testid="practice-slug-claim"
      style={{
        marginBottom: 20,
        paddingBottom: 16,
        borderBottom: '1px solid var(--color-linear-hairline)',
      }}
    >
      <h3 style={{ fontSize: 13, color: 'var(--color-linear-text-2)', margin: '0 0 8px' }}>
        Practice address name
      </h3>

      {!claimable || claimedNow ? (
        <div data-testid="practice-slug-claimed">
          <code
            data-testid="practice-slug-value"
            style={{
              fontFamily: 'var(--font-mono, ui-monospace), monospace',
              fontSize: 14,
              color: 'var(--color-linear-text)',
            }}
          >
            {claimedNow ?? currentSlug}
          </code>
          <p style={noteStyle}>
            Chosen. To change it, contact support — changes after the first are made by
            QuillMD support so existing links and sign-ins keep working.
          </p>
        </div>
      ) : (
        <form
          action={action}
          style={{ display: 'grid', gap: 10, maxWidth: 460 }}
          // ⚠️ THE CONFIRM IS HERE BECAUSE THE CHOICE IS ONE-TIME for an owner.
          onSubmit={(e) => {
            const chosen = String(new FormData(e.currentTarget).get('slug') ?? '')
              .trim()
              .toLowerCase();
            const ok = window.confirm(
              `Use "${chosen}" as your practice's address name?\n\n` +
                'An owner can choose this only once. Later changes are made by QuillMD support.',
            );
            if (!ok) e.preventDefault();
          }}
        >
          <label style={{ fontSize: 12, color: 'var(--color-linear-text-3)' }}>
            Choose a short name for your practice&apos;s own web address. It is reserved for
            your practice now; the address itself is not live yet.
            <input
              name="slug"
              required
              minLength={3}
              maxLength={63}
              autoComplete="off"
              spellCheck={false}
              placeholder="northside-clinic"
              data-testid="practice-slug-input"
              className="qm-lin-btn"
              style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px' }}
            />
          </label>
          <p style={{ ...noteStyle, margin: 0 }}>
            Lowercase letters, numbers and hyphens. Currently an automatic name:{' '}
            <code data-testid="practice-slug-current">{currentSlug}</code>
          </p>
          {state?.ok === false ? (
            <p
              role="alert"
              data-testid="practice-slug-error"
              style={{ margin: 0, fontSize: 13, color: 'var(--color-linear-text)' }}
            >
              {state.message}
            </p>
          ) : null}
          <div>
            <SpecularButton type="submit" disabled={pending} data-testid="practice-slug-save">
              {pending ? 'Saving…' : 'Save name'}
            </SpecularButton>
          </div>
        </form>
      )}
    </section>
  );
}
