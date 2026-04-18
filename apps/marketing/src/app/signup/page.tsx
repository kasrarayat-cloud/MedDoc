import type { Metadata } from 'next';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { SignupForm } from './signup-form';

export const metadata: Metadata = {
  title: 'Start free trial',
  description:
    'Sign up for TranscribeMD — 10 free signed notes, 14-day trial, no credit card.',
};

export default function SignupPage() {
  return (
    <>
      <NavBar />
      <main>
        <section className="relative overflow-hidden pt-32 pb-24">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 h-[500px]"
            style={{
              background:
                'radial-gradient(ellipse 60% 50% at 50% 0%, rgba(139,92,246,0.18) 0%, transparent 65%)',
            }}
          />
          <div className="relative mx-auto max-w-md px-6 lg:px-8">
            <SignupForm />
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
