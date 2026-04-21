import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

import prisma from '@meddoc/db';

import { auth } from '@/lib/nextauth';
import { NavBar } from '@/components/nav-bar';
import { PageWrapper } from '@/components/page-wrapper';
import { SUPPORTED_TOKENS } from '@/lib/template-tokens';

import { TemplateUploadForm } from './template-upload-form';
import { TemplateCard } from './template-card';
import { TemplateGuideButton } from './template-guide';

export const metadata: Metadata = { title: 'Templates · Settings' };

interface TemplateRow {
  id: string;
  name: string;
  originalFileName: string;
  tokens: string[];
  createdAt: Date;
}

export default async function TemplatesSettingsPage() {
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const [user, templates] = await Promise.all([
    prisma.user.findUnique({
      where: { id: session.user.id },
      select: { name: true, email: true },
    }),
    prisma.transcribeTemplate.findMany({
      where: { userId: session.user.id, deletedAt: null },
      orderBy: { createdAt: 'desc' },
      select: {
        id: true,
        name: true,
        originalFileName: true,
        tokens: true,
        createdAt: true,
      },
    }),
  ]);
  if (!user) redirect('/login');

  return (
    <PageWrapper>
      <NavBar name={user.name} email={user.email} />

      <main className="mx-auto max-w-4xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
        <Link
          href="/settings"
          className="inline-flex items-center gap-1.5 text-[12px] text-text-tertiary transition-colors hover:text-text-primary"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
          Back to settings
        </Link>

        <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="type-h1 text-text-primary">Templates</h1>
            <p className="mt-2 text-[13px] text-text-tertiary">
              Upload your own SOAP template (.docx) and use it on any visit.
              We fill the placeholders you define with AI-generated content
              from the transcript, preserving your formatting exactly.
            </p>
          </div>
          <TemplateGuideButton />
        </div>

        {/* Upload section */}
        <section className="mt-8">
          <h2 className="type-h2 text-text-primary">Upload a new template</h2>
          <div className="mt-4 rounded-xl border border-border-default bg-bg-surface-1/60 p-6">
            <TemplateUploadForm supportedTokens={[...SUPPORTED_TOKENS]} />
          </div>
        </section>

        {/* Your templates */}
        <section className="mt-10">
          <h2 className="type-h2 text-text-primary">
            Your templates
            <span className="ml-2 text-[13px] font-normal text-text-muted">
              ({templates.length})
            </span>
          </h2>

          {templates.length === 0 ? (
            <div className="mt-4 rounded-xl border border-dashed border-border-default bg-bg-surface-1/30 p-10 text-center">
              <p className="text-[14px] text-text-secondary">
                No templates yet.
              </p>
              <p className="mt-1 text-[12px] text-text-muted">
                Upload your first SOAP template to use it on future visits.
              </p>
            </div>
          ) : (
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {(templates as TemplateRow[]).map((t) => (
                <TemplateCard
                  key={t.id}
                  template={{
                    id: t.id,
                    name: t.name,
                    originalFileName: t.originalFileName,
                    tokens: t.tokens,
                    createdAt: t.createdAt.toISOString(),
                  }}
                />
              ))}
            </div>
          )}
        </section>
      </main>
    </PageWrapper>
  );
}
