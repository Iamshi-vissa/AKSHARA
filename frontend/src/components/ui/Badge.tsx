import type { ReactNode } from 'react';

import type { DocumentKind } from '@/api/client';

const KIND_STYLE: Record<DocumentKind, string> = {
  docx: 'text-[#93c5fd] bg-[#93c5fd14] border-[#93c5fd33]',
  pdf: 'text-[#fca5a5] bg-[#fca5a514] border-[#fca5a533]',
  pptx: 'text-[#fdba74] bg-[#fdba7414] border-[#fdba7433]',
};

export function KindBadge({ kind }: { kind: DocumentKind }) {
  return (
    <span
      className={`inline-flex h-6 min-w-12 items-center justify-center rounded-md border px-2 font-mono text-[11px] font-semibold tracking-wider uppercase ${KIND_STYLE[kind]}`}
    >
      {kind}
    </span>
  );
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'gold' | 'accent' | 'warn' | 'ok' }) {
  const tones = {
    neutral: 'border-ink-600 bg-ink-800 text-paper-dim',
    gold: 'border-gold/30 bg-gold-soft text-gold',
    accent: 'border-accent/30 bg-accent-soft text-accent-strong',
    warn: 'border-sev-medium/30 bg-sev-medium/10 text-sev-medium',
    ok: 'border-ok/30 bg-ok/10 text-ok',
  }[tone];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${tones}`}>
      {children}
    </span>
  );
}
