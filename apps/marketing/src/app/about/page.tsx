import type { Metadata } from 'next';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { GradientText } from '@/components/gradient-text';
import { Badge } from '@/components/badge';

export const metadata: Metadata = {
  title: 'About',
  description: 'The story, the reason, and the approach behind QuillMD.',
};

const SECTION_BODY: React.CSSProperties = {
  marginTop: 24,
  display: 'flex',
  flexDirection: 'column',
  gap: 18,
  fontSize: 15,
  lineHeight: 1.7,
  color: 'var(--color-linear-text-2)',
};

const SECTION_TITLE: React.CSSProperties = {
  color: 'var(--color-linear-text)',
};

export default function AboutPage() {
  return (
    <>
      <NavBar />
      <main>
        <section
          className="relative overflow-hidden"
          style={{ paddingTop: 96, paddingBottom: 64 }}
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0"
            style={{
              height: 500,
              background:
                'radial-gradient(ellipse 70% 50% at 50% 0%, rgba(122,166,140,0.18) 0%, transparent 65%)',
            }}
          />
          <div
            className="container"
            style={{ maxWidth: 760, position: 'relative' }}
          >
            <Badge dot="violet">About us</Badge>
            <h1 className="hero-title" style={{ marginTop: 20, textAlign: 'left' }}>
              Built for the <GradientText>doctor at the desk</GradientText> at
              7 p.m.
            </h1>
            <p className="hero-sub" style={{ marginTop: 20, marginInline: 0, textAlign: 'left' }}>
              The one who stayed late to finish their charts. Again.
            </p>
          </div>
        </section>

        <section
          style={{
            position: 'relative',
            borderTop: '1px solid var(--color-linear-hairline)',
            paddingTop: 64,
            paddingBottom: 64,
          }}
        >
          <div className="container" style={{ maxWidth: 760 }}>
            <h2 className="section-title" style={SECTION_TITLE}>
              The story
            </h2>
            <div style={SECTION_BODY}>
              <p>
                A friend of ours is a solo family-practice doctor. Every
                Thursday night we&apos;d hear the same thing: &quot;I still
                have eight charts left.&quot; Transcription service in India,
                18-hour turnaround, good enough for boilerplate and hopeless
                for anything complicated.
              </p>
              <p>
                We&apos;d already been building a clinical note pipeline for a
                different product — SOAP generation, ICD-10 coding,
                schema-validated output. It turned out the piece she wanted
                wasn&apos;t the CRM or the patient portal. It was just this:
                send audio, get a signed note, five minutes.
              </p>
              <p>
                So we took that slice, made it standalone, priced it like
                software and not like a per-line transcription contract, and
                shipped it.
              </p>
            </div>
          </div>
        </section>

        <section
          style={{
            position: 'relative',
            borderTop: '1px solid var(--color-linear-hairline)',
            background: 'var(--color-linear-surface-1)',
            paddingTop: 64,
            paddingBottom: 64,
          }}
        >
          <div className="container" style={{ maxWidth: 760 }}>
            <h2 className="section-title" style={SECTION_TITLE}>
              Why we built this
            </h2>
            <div style={SECTION_BODY}>
              <p>
                Because the existing options for solo doctors are bad. India-
                based transcription is slow and impersonal. Enterprise AI
                scribes start at six figures and require a 45-minute sales
                call before you can see the product. Freed is great but
                opinionated about how you work; DeepScribe is great but
                enterprise-only.
              </p>
              <p>
                None of them treat a solo doctor the way a solo doctor deserves
                to be treated — like a professional who can read a pricing
                page and decide.
              </p>
            </div>
          </div>
        </section>

        <section
          style={{
            position: 'relative',
            borderTop: '1px solid var(--color-linear-hairline)',
            paddingTop: 64,
            paddingBottom: 64,
          }}
        >
          <div className="container" style={{ maxWidth: 760 }}>
            <h2 className="section-title" style={SECTION_TITLE}>
              Our approach
            </h2>
            <div style={SECTION_BODY}>
              <p>
                Self-serve signup. Transparent pricing. Cancellation as a
                button. Nothing about using software for your practice should
                require a Zoom.
              </p>
              <p>
                Every AI output has an evidence quote traced back to the
                transcript. Every ICD-10 code ships with its source. Every
                prescription flags interactions and controlled-substance
                concerns before the clinician signs. You stay in charge; we
                just do the typing.
              </p>
              <p>
                If the product doesn&apos;t save you an hour a day, it
                doesn&apos;t deserve your money. You&apos;ll know in fourteen
                days.
              </p>
            </div>
          </div>
        </section>

        <section
          style={{
            position: 'relative',
            borderTop: '1px solid var(--color-linear-hairline)',
            background: 'var(--color-linear-surface-1)',
            paddingTop: 64,
            paddingBottom: 96,
          }}
        >
          <div className="container" style={{ maxWidth: 760 }}>
            <h2 className="section-title" style={SECTION_TITLE}>
              Team
            </h2>
            <p
              style={{
                marginTop: 16,
                fontSize: 14,
                color: 'var(--color-linear-text-3)',
              }}
            >
              Small and senior. Engineers, product, and clinical advisors.
              More here soon.
            </p>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
