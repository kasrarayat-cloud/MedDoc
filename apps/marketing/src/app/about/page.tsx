import type { Metadata } from 'next';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { GradientText } from '@/components/gradient-text';
import { Badge } from '@/components/badge';

export const metadata: Metadata = {
  title: 'About',
  description:
    'The story, the reason, and the approach behind TranscribeMD.',
};

export default function AboutPage() {
  return (
    <>
      <NavBar />
      <main>
        <section className="relative overflow-hidden pt-32 pb-16">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 h-[500px]"
            style={{
              background:
                'radial-gradient(ellipse 70% 50% at 50% 0%, rgba(139,92,246,0.18) 0%, transparent 65%)',
            }}
          />
          <div className="relative mx-auto max-w-3xl px-6 lg:px-8">
            <Badge dot="violet">About us</Badge>
            <h1 className="mt-6 type-h1 text-text-primary">
              Built for the <GradientText>doctor at the desk</GradientText> at
              7 p.m.
            </h1>
            <p className="mt-6 type-body text-text-tertiary">
              The one who stayed late to finish their charts. Again.
            </p>
          </div>
        </section>

        <section className="relative border-t border-border-subtle py-16">
          <div className="mx-auto max-w-3xl px-6 lg:px-8">
            <h2 className="type-h2 text-text-primary">The story</h2>
            <div className="mt-6 space-y-5 text-[16px] leading-relaxed text-text-secondary">
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

        <section className="relative border-t border-border-subtle bg-bg-surface-1/30 py-16">
          <div className="mx-auto max-w-3xl px-6 lg:px-8">
            <h2 className="type-h2 text-text-primary">Why we built this</h2>
            <div className="mt-6 space-y-5 text-[16px] leading-relaxed text-text-secondary">
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

        <section className="relative border-t border-border-subtle py-16">
          <div className="mx-auto max-w-3xl px-6 lg:px-8">
            <h2 className="type-h2 text-text-primary">Our approach</h2>
            <div className="mt-6 space-y-5 text-[16px] leading-relaxed text-text-secondary">
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

        <section className="relative border-t border-border-subtle bg-bg-surface-1/30 py-16 pb-24">
          <div className="mx-auto max-w-3xl px-6 lg:px-8">
            <h2 className="type-h2 text-text-primary">Team</h2>
            <p className="mt-4 text-[14px] text-text-muted">
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
