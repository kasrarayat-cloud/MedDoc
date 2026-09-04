'use client';

/**
 * ⚠️ RULING #182(1) — "CANNOT TELL" IS SHOWN AS A RETRY, NEVER AS A SIGN-OUT.
 *
 * The database could not answer whether this session is still valid. Three
 * things follow, and each is a correction of something that shipped before:
 *
 *   · NO CLINICAL DATA IS RENDERED. The previous behaviour served the page from
 *     JWT-claimed `role` and `practiceId`, which admitted a deactivated,
 *     suspended or soft-deleted account for the life of the token.
 *   · THE SESSION IS NOT ENDED and the cookie is NOT cleared. The next attempt
 *     re-validates; a transient pool timeout costs a retry, not a re-login.
 *     (#181(d) briefly did clear it, which ejected working doctors on a blip.)
 *   · IT SAYS WHICH OF THE TWO THIS IS. "Signed out" would be a lie, and a
 *     generic error would send the doctor to sign in again for no reason.
 */
export function SessionUnverifiable({ reset }: { reset: () => void }) {
  return (
    <main
      role="alert"
      aria-live="assertive"
      data-testid="session-unverifiable"
      style={{
        maxWidth: '32rem',
        margin: '4rem auto',
        padding: '1.5rem',
        textAlign: 'center',
      }}
    >
      <h1 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.75rem' }}>
        Verifying your session…
      </h1>
      <p style={{ marginBottom: '1.25rem', lineHeight: 1.6 }}>
        We could not confirm your session with the server just now, so nothing is
        being shown. <strong>You have not been signed out</strong> — this is
        usually brief. Please try again.
      </p>
      <button
        type="button"
        onClick={reset}
        data-testid="session-unverifiable-retry"
        style={{ padding: '0.5rem 1rem', fontWeight: 600, cursor: 'pointer' }}
      >
        Try again
      </button>
    </main>
  );
}
