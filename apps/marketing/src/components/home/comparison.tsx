'use client';

import { motion } from 'framer-motion';
import { Check, X, Minus } from 'lucide-react';
import { cn } from '@/lib/cn';

type Cell = { kind: 'yes'; label: string } | { kind: 'no'; label: string } | {
  kind: 'partial';
  label: string;
};

const yes = (label: string): Cell => ({ kind: 'yes', label });
const no = (label: string): Cell => ({ kind: 'no', label });
const partial = (label: string): Cell => ({ kind: 'partial', label });

const COLUMNS = [
  { id: 'turnaround', label: 'Turnaround' },
  { id: 'price', label: 'Starting price' },
  { id: 'ai', label: 'AI-powered' },
  { id: 'selfserve', label: 'Self-serve signup' },
  { id: 'ehr', label: 'Supports your EHR' },
];

const ROWS = [
  {
    name: 'QuillMD',
    highlight: true,
    cells: {
      turnaround: yes('2–5 min'),
      price: yes('$49 / mo'),
      ai: yes('Yes'),
      selfserve: yes('Yes'),
      ehr: yes('Any'),
    },
  },
  {
    name: 'India-based transcription',
    highlight: false,
    cells: {
      turnaround: no('12–24 hr'),
      price: partial('Per-line'),
      ai: no('No'),
      selfserve: no('Sales call'),
      ehr: partial('Depends'),
    },
  },
  {
    name: 'Freed',
    highlight: false,
    cells: {
      turnaround: yes('Live'),
      price: partial('$99 / mo'),
      ai: yes('Yes'),
      selfserve: yes('Yes'),
      ehr: partial('Most'),
    },
  },
  {
    name: 'DeepScribe',
    highlight: false,
    cells: {
      turnaround: yes('Live'),
      price: no('Enterprise'),
      ai: yes('Yes'),
      selfserve: no('Sales call'),
      ehr: yes('Any'),
    },
  },
];

function CellView({ cell }: { cell: Cell }) {
  const Icon = cell.kind === 'yes' ? Check : cell.kind === 'no' ? X : Minus;
  const color =
    cell.kind === 'yes'
      ? 'text-success'
      : cell.kind === 'no'
        ? 'text-danger/80'
        : 'text-text-muted';
  return (
    <div className="flex items-center gap-2">
      <Icon className={cn('h-3.5 w-3.5', color)} />
      <span className="text-[13px] text-text-secondary">{cell.label}</span>
    </div>
  );
}

export function Comparison() {
  return (
    <section className="relative overflow-hidden border-t border-border-subtle bg-bg-surface-1/40 py-24 lg:py-32">
      <div className="relative mx-auto max-w-7xl px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
          className="max-w-2xl"
        >
          <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-text-muted">
            Stack it up
          </p>
          <h2 className="mt-3 type-h2 text-text-primary">
            How QuillMD stacks up.
          </h2>
          <p className="mt-4 type-body text-text-tertiary">
            Every option has its place. Here&apos;s where each one wins.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.4, 0, 0.2, 1] }}
          className="mt-12 overflow-hidden rounded-2xl border border-border-default"
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-separate border-spacing-0">
              <thead>
                <tr className="bg-bg-surface-2/70">
                  <th className="sticky left-0 z-10 w-[200px] border-b border-border-default bg-bg-surface-2/80 px-5 py-4 text-left text-[12px] font-semibold uppercase tracking-[0.1em] text-text-muted">
                    Provider
                  </th>
                  {COLUMNS.map((c) => (
                    <th
                      key={c.id}
                      className="border-b border-border-default px-5 py-4 text-left text-[12px] font-semibold uppercase tracking-[0.1em] text-text-muted"
                    >
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ROWS.map((row) => (
                  <tr
                    key={row.name}
                    className={cn(
                      'transition-colors',
                      row.highlight ? 'bg-violet-500/[0.06]' : ''
                    )}
                  >
                    <th
                      scope="row"
                      className={cn(
                        'sticky left-0 z-10 border-b border-border-subtle px-5 py-4 text-left text-[14px] font-medium',
                        row.highlight
                          ? 'bg-violet-500/[0.08] text-text-primary'
                          : 'bg-bg-surface-1/60 text-text-secondary'
                      )}
                    >
                      <div className="flex items-center gap-2">
                        {row.highlight && (
                          <span
                            aria-hidden
                            className="h-1.5 w-1.5 rounded-full bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.6)]"
                          />
                        )}
                        {row.name}
                      </div>
                    </th>
                    {COLUMNS.map((c) => (
                      <td
                        key={c.id}
                        className="border-b border-border-subtle px-5 py-4"
                      >
                        <CellView cell={row.cells[c.id as keyof typeof row.cells]} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
