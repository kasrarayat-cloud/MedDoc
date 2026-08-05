'use client';

// ============================================================================
// Phase 5 — Linear V1 Faithful command palette (Cmd+K).
// ----------------------------------------------------------------------------
// Reference: dashboard-v1.html `.kbar` (spotlight modal pattern).
//
// The Phase 4 violet-tinted glassy palette is gone. Linear V1 spotlight
// renders on linear-surface-1 with a hairline border, mono kbd hints,
// and sage hover for the active row. Behaviour is unchanged: cmdk +
// Radix Dialog handle keyboard nav, fuzzy search, route navigation,
// sign-out. Cmd+K binding via useShortcut is preserved.
// ============================================================================

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import { Command } from 'cmdk';
import {
  Plus,
  LayoutDashboard,
  Settings as SettingsIcon,
  LogOut,
  FileText,
  Search,
  Loader2,
} from 'lucide-react';

import { cn } from '@/lib/cn';
import { useShortcut, formatCommandKey } from '@/lib/shortcuts';
import { signOutAction } from '@/actions/session';
import {
  getRecentVisits,
  type RecentVisitItem,
} from '@/actions/command-palette';

interface CommandPaletteProps {
  /** When true, authed-only commands (Sign out, recent visits) are shown.
   *  /login and /signup pages mount the palette with `false` so the Cmd+K
   *  shortcut stays consistent but the menu stays minimal. */
  authed: boolean;
}

export function CommandPalette({ authed }: CommandPaletteProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [recent, setRecent] = useState<RecentVisitItem[] | null>(null);
  const loading = authed && open && recent === null;
  const hasFetchedRef = useRef(false);

  // Cmd+K / Ctrl+K everywhere.
  useShortcut({
    key: 'k',
    meta: true,
    onFire: () => setOpen((v) => !v),
  });

  // Lazy-load recent visits on first open for an authed user.
  useEffect(() => {
    if (!open || !authed) return;
    if (hasFetchedRef.current) return;
    hasFetchedRef.current = true;
    getRecentVisits()
      .then((rows) => setRecent(rows))
      .catch((err) => {
        console.error('[command-palette] recent visits failed:', err);
        setRecent([]);
      });
  }, [open, authed]);

  const run = useCallback(
    (fn: () => void | Promise<void>) => {
      setOpen(false);
      setTimeout(() => {
        void fn();
      }, 20);
    },
    [],
  );

  const navTo = useCallback(
    (path: string) => run(() => router.push(path)),
    [router, run],
  );

  const signOut = useCallback(
    () =>
      run(async () => {
        await signOutAction();
        router.push('/login');
        router.refresh();
      }),
    [router, run],
  );

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 200,
            background: 'rgba(0, 0, 0, 0.55)',
            backdropFilter: 'blur(2px)',
          }}
          className="data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0"
        />
        <Dialog.Content
          aria-describedby={undefined}
          style={{
            position: 'fixed',
            left: '50%',
            top: '14vh',
            transform: 'translateX(-50%)',
            zIndex: 201,
            width: 'min(620px, calc(100vw - 40px))',
            background: 'var(--color-linear-surface-1)',
            border: '1px solid var(--color-linear-border-strong)',
            borderRadius: 10,
            boxShadow:
              '0 30px 80px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.03)',
            overflow: 'hidden',
            color: 'var(--color-linear-text)',
            outline: 'none',
          }}
          className="data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-top-2 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95"
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <Command label="Command palette">
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '13px 16px',
                borderBottom: '1px solid var(--color-linear-hairline)',
              }}
            >
              <Search
                className="h-3.5 w-3.5 flex-none"
                style={{ color: 'var(--color-linear-text-3)' }}
                aria-hidden
              />
              <Command.Input
                value={query}
                onValueChange={setQuery}
                placeholder="Type a command, search a patient…"
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: 0,
                  outline: 'none',
                  color: 'var(--color-linear-text)',
                  fontFamily: 'var(--font-sans)',
                  fontSize: 14,
                  letterSpacing: '-0.005em',
                }}
                autoFocus
              />
              <kbd
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10.5,
                  color: 'var(--color-linear-text-3)',
                  border: '1px solid var(--color-linear-hairline-strong)',
                  padding: '2px 6px',
                  borderRadius: 3,
                }}
              >
                esc
              </kbd>
            </div>

            <Command.List
              style={{
                maxHeight: 'min(60vh, 480px)',
                overflowY: 'auto',
                padding: '4px 0',
              }}
            >
              <Command.Empty
                style={{
                  padding: '32px 16px',
                  textAlign: 'center',
                  fontFamily: 'var(--font-sans)',
                  fontSize: 13,
                  color: 'var(--color-linear-text-3)',
                }}
              >
                No commands match &quot;{query}&quot;.
              </Command.Empty>

              <Command.Group
                heading="Navigate"
                className="[&_[cmdk-group-heading]]:px-4 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-linear-text-3"
              >
                <PaletteItem
                  onSelect={() => navTo('/visits/new')}
                  icon={<Plus className="h-3.5 w-3.5" />}
                  label="New visit"
                  hint="N"
                />
                <PaletteItem
                  // ⚠️ RE-POINTED 2026-08-05 (F-ret.3) — FOUND BY THE BUNDLE DIFF,
                  // NOT BY THE SOURCE CENSUS. This entry never touched
                  // `isSkinRounds`; it hardcoded the destination, so a census
                  // built from flag consumers could not see it. The shipped
                  // chunk still carried the string "Go to dashboard" after every
                  // flag site was collapsed, which is how it surfaced.
                  //
                  // It was not broken — /dashboard 307s to /board — but it named
                  // a surface that no longer exists and put a legacy URL in the
                  // history of anyone who used Cmd+K, which is the exact double
                  // hop R1 removed from the root route.
                  onSelect={() => navTo('/board')}
                  icon={<LayoutDashboard className="h-3.5 w-3.5" />}
                  label="Go to the board"
                  hint="D"
                />
                <PaletteItem
                  onSelect={() => navTo('/settings')}
                  icon={<SettingsIcon className="h-3.5 w-3.5" />}
                  label="Settings"
                  hint="S"
                />
                {authed && (
                  <PaletteItem
                    onSelect={signOut}
                    icon={<LogOut className="h-3.5 w-3.5" />}
                    label="Sign out"
                  />
                )}
              </Command.Group>

              {authed && (
                <Command.Group
                  heading="Recent visits"
                  className="mt-1 [&_[cmdk-group-heading]]:px-4 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-linear-text-3"
                >
                  {loading && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '10px 16px',
                        fontFamily: 'var(--font-sans)',
                        fontSize: 13,
                        color: 'var(--color-linear-text-3)',
                      }}
                    >
                      <Loader2
                        className="h-3.5 w-3.5 animate-spin"
                        aria-hidden
                      />
                      Loading recent visits…
                    </div>
                  )}
                  {recent?.length === 0 && !loading && (
                    <div
                      style={{
                        padding: '10px 16px',
                        fontFamily: 'var(--font-sans)',
                        fontSize: 13,
                        color: 'var(--color-linear-text-3)',
                      }}
                    >
                      No visits yet — press N to create your first.
                    </div>
                  )}
                  {recent?.map((v) => {
                    const name = v.patientName?.trim() || 'Anonymous';
                    return (
                      <PaletteItem
                        key={v.id}
                        value={`visit-${v.id} ${name} ${v.specialty}`}
                        onSelect={() => navTo(`/visits/${v.id}`)}
                        icon={<FileText className="h-3.5 w-3.5" />}
                        label={name}
                        sublabel={v.specialty}
                      />
                    );
                  })}
                </Command.Group>
              )}
            </Command.List>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 16,
                padding: '8px 16px',
                borderTop: '1px solid var(--color-linear-hairline)',
                background: 'rgba(255, 255, 255, 0.012)',
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: 'var(--color-linear-text-3)',
              }}
            >
              <div style={{ display: 'inline-flex', gap: 12 }}>
                <KbdPair keys={['↑', '↓']} label="navigate" />
                <KbdPair keys={['↵']} label="select" />
                <KbdPair keys={['esc']} label="close" />
              </div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                }}
                className="hidden sm:inline-flex"
              >
                <kbd
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    color: 'var(--color-linear-text-3)',
                    border: '1px solid var(--color-linear-hairline)',
                    padding: '1px 4px',
                    borderRadius: 2,
                  }}
                >
                  {formatCommandKey('K')}
                </kbd>
                <span>anywhere</span>
              </div>
            </div>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

interface PaletteItemProps {
  onSelect: () => void;
  icon: React.ReactNode;
  label: string;
  sublabel?: string;
  hint?: string;
  value?: string;
}

function PaletteItem({
  onSelect,
  icon,
  label,
  sublabel,
  hint,
  value,
}: PaletteItemProps) {
  return (
    <Command.Item
      value={value ?? label}
      onSelect={onSelect}
      className={cn(
        'flex cursor-pointer select-none items-center gap-3 px-4 py-1.5',
        'text-[13px] text-linear-text-2 outline-none',
        'data-[selected=true]:bg-linear-sage-tint data-[selected=true]:text-linear-text',
        'transition-colors duration-100',
      )}
    >
      <span
        aria-hidden
        style={{
          width: 14,
          height: 14,
          flex: '0 0 14px',
          color: 'var(--color-linear-text-3)',
          display: 'grid',
          placeItems: 'center',
        }}
        className="data-[selected=true]:!text-linear-sage-bright"
      >
        {icon}
      </span>
      <span
        style={{
          flex: 1,
          letterSpacing: '-0.005em',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {label}
      </span>
      {sublabel && (
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--color-linear-text-3)',
            flex: 'none',
          }}
        >
          {sublabel}
        </span>
      )}
      {hint && (
        <kbd
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10.5,
            color: 'var(--color-linear-text-3)',
            border: '1px solid var(--color-linear-hairline-strong)',
            padding: '1.5px 5px',
            borderRadius: 3,
            background: 'rgba(255, 255, 255, 0.02)',
            flex: 'none',
          }}
        >
          {hint}
        </kbd>
      )}
    </Command.Item>
  );
}

function KbdPair({ keys, label }: { keys: string[]; label: string }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
      }}
    >
      {keys.map((k) => (
        <kbd
          key={k}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: 'var(--color-linear-text-3)',
            border: '1px solid var(--color-linear-hairline)',
            padding: '1px 4px',
            borderRadius: 2,
          }}
        >
          {k}
        </kbd>
      ))}
      <span>{label}</span>
    </span>
  );
}
