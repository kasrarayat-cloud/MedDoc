'use client';

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
  // "Loading" is derived from state only — authed + open + fetch not
  // yet resolved. Once setRecent is called (to [] or the real rows),
  // this flips to false naturally. No refs read during render, which
  // keeps the react-hooks/refs lint happy.
  const loading = authed && open && recent === null;
  // Guard ref to avoid re-fetching on every Cmd+K press. Only read/written
  // inside the effect body below — never during render.
  const hasFetchedRef = useRef(false);

  // Cmd+K / Ctrl+K everywhere. The `meta` flag covers both platforms.
  useShortcut({
    key: 'k',
    meta: true,
    onFire: () => setOpen((v) => !v),
  });

  // Load recent visits lazily — only on the first open for an authed
  // user. Keeps the initial render cost tiny and avoids a probe query
  // on every Cmd+K press.
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
      // Defer to the next tick so the close animation starts before the
      // navigation — otherwise the palette blinks open on the new route.
      setTimeout(() => {
        void fn();
      }, 20);
    },
    []
  );

  const navTo = useCallback(
    (path: string) => run(() => router.push(path)),
    [router, run]
  );

  const signOut = useCallback(
    () =>
      run(async () => {
        await signOutAction();
        router.push('/login');
        router.refresh();
      }),
    [router, run]
  );

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay
          className={cn(
            'fixed inset-0 z-[200] bg-black/60 backdrop-blur-sm',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0'
          )}
        />
        <Dialog.Content
          aria-describedby={undefined}
          className={cn(
            'fixed left-1/2 top-[20vh] z-[201] w-[min(94vw,600px)] -translate-x-1/2',
            'rounded-2xl border border-border-default bg-bg-surface-1/95 backdrop-blur-xl',
            'shadow-[0_32px_96px_-24px_rgba(0,0,0,0.9),0_0_0_1px_rgba(139,92,246,0.15)]',
            'focus:outline-none overflow-hidden',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0',
            'data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-top-2',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
            'data-[state=closed]:zoom-out-95'
          )}
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <Command
            label="Command palette"
            // cmdk handles its own ↑↓↵ navigation, but let Escape close
            // the Dialog rather than blur the input.
            className="[&_[cmdk-input-wrapper]]:border-b [&_[cmdk-input-wrapper]]:border-border-subtle"
          >
            <div className="flex items-center gap-3 px-4 py-3">
              <Search className="h-4 w-4 flex-none text-text-muted" aria-hidden />
              <Command.Input
                value={query}
                onValueChange={setQuery}
                placeholder="Type a command or search…"
                className={cn(
                  'flex-1 bg-transparent text-[14px] text-text-primary',
                  'placeholder:text-text-muted outline-none',
                  // cmdk mounts the input via a portal sometimes — this
                  // ensures it still takes focus ring when tabbed to.
                  'focus:outline-none'
                )}
                autoFocus
              />
              <kbd className="hidden rounded bg-bg-surface-3 px-1.5 py-0.5 text-[10px] font-medium text-text-muted sm:inline">
                esc
              </kbd>
            </div>

            <Command.List className="max-h-[min(60vh,480px)] overflow-y-auto p-2">
              <Command.Empty className="py-8 text-center text-[13px] text-text-muted">
                No commands match &quot;{query}&quot;.
              </Command.Empty>

              <Command.Group
                heading="Navigate"
                className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-text-muted"
              >
                <PaletteItem
                  onSelect={() => navTo('/visits/new')}
                  icon={<Plus className="h-4 w-4" />}
                  label="New visit"
                  hint="N"
                />
                <PaletteItem
                  onSelect={() => navTo('/dashboard')}
                  icon={<LayoutDashboard className="h-4 w-4" />}
                  label="Go to dashboard"
                  hint="D"
                />
                <PaletteItem
                  onSelect={() => navTo('/settings')}
                  icon={<SettingsIcon className="h-4 w-4" />}
                  label="Settings"
                  hint="S"
                />
                {authed && (
                  <PaletteItem
                    onSelect={signOut}
                    icon={<LogOut className="h-4 w-4" />}
                    label="Sign out"
                  />
                )}
              </Command.Group>

              {authed && (
                <Command.Group
                  heading="Recent visits"
                  className="mt-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-text-muted"
                >
                  {loading && (
                    <div className="flex items-center gap-2 px-2 py-3 text-[13px] text-text-muted">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                      Loading recent visits…
                    </div>
                  )}
                  {recent?.length === 0 && !loading && (
                    <div className="px-2 py-3 text-[13px] text-text-muted">
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
                        icon={<FileText className="h-4 w-4" />}
                        label={name}
                        sublabel={v.specialty}
                      />
                    );
                  })}
                </Command.Group>
              )}
            </Command.List>

            <div className="flex items-center justify-between gap-4 border-t border-border-subtle bg-bg-surface-2/60 px-4 py-2 text-[11px] text-text-muted">
              <div className="flex items-center gap-3">
                <KbdPair keys={['↑', '↓']} label="navigate" />
                <KbdPair keys={['↵']} label="select" />
                <KbdPair keys={['esc']} label="close" />
              </div>
              <div className="hidden sm:flex items-center gap-1">
                <kbd className="rounded bg-bg-surface-3 px-1.5 py-0.5 font-medium text-text-tertiary">
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

// ---------------------------------------------------------------------------
// Sub-components — kept local since they don't make sense outside the palette.
// ---------------------------------------------------------------------------

interface PaletteItemProps {
  onSelect: () => void;
  icon: React.ReactNode;
  label: string;
  sublabel?: string;
  hint?: string;
  /** Override the string cmdk uses for fuzzy-matching. Defaults to label. */
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
        'flex cursor-pointer select-none items-center gap-3 rounded-lg px-2 py-2',
        'text-[13px] text-text-secondary outline-none',
        'data-[selected=true]:bg-bg-surface-2 data-[selected=true]:text-text-primary',
        'transition-colors duration-150 ease-[cubic-bezier(0.4,0,0.2,1)]'
      )}
    >
      <span
        aria-hidden
        className="flex h-7 w-7 flex-none items-center justify-center rounded-md bg-bg-surface-3 text-text-tertiary group-data-[selected=true]:text-violet-300"
      >
        {icon}
      </span>
      <span className="flex-1 truncate">{label}</span>
      {sublabel && (
        <span className="flex-none text-[11px] text-text-muted">{sublabel}</span>
      )}
      {hint && (
        <kbd className="flex-none rounded bg-bg-surface-3 px-1.5 py-0.5 text-[10px] font-medium text-text-muted">
          {hint}
        </kbd>
      )}
    </Command.Item>
  );
}

function KbdPair({ keys, label }: { keys: string[]; label: string }) {
  return (
    <span className="flex items-center gap-1">
      {keys.map((k) => (
        <kbd
          key={k}
          className="rounded bg-bg-surface-3 px-1.5 py-0.5 font-medium text-text-tertiary"
        >
          {k}
        </kbd>
      ))}
      <span>{label}</span>
    </span>
  );
}
