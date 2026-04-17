import { redirect } from 'next/navigation';
import Link from 'next/link';
import { getSession } from '@/lib/auth';

// Every page in this group reads the authenticated session, which depends
// on the incoming request cookies. Forcing dynamic rendering here prevents
// Next from trying to prerender these routes (which would call getSession()
// with no request context and crash on null). Applies to all children.
export const dynamic = 'force-dynamic';

const MEDDOC_PRO_URL =
  process.env.MEDDOC_PRO_PUBLIC_URL?.trim() || 'http://meddoc-pro.localhost';

// Server-side auth gate. The proxy catches this on the edge, but the
// layout does a second check so server components always see a guaranteed-
// present session (simpler call-site code, no optional chaining everywhere).
export default async function ScribeDashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (!session) redirect(`${MEDDOC_PRO_URL}/login`);

  return (
    <div className="flex-1 flex flex-col">
      <header className="border-b border-slate-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/visits" className="text-lg font-semibold">
            MedDoc Scribe
          </Link>
          <span className="text-xs text-slate-400 px-2 py-0.5 rounded bg-slate-800">
            beta
          </span>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-slate-300">{session.user.fullName}</span>
          <Link
            href={MEDDOC_PRO_URL}
            className="text-slate-400 hover:text-slate-200 underline-offset-4 hover:underline"
          >
            Back to MedDoc Pro
          </Link>
        </div>
      </header>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
