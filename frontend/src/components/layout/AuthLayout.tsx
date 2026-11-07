import type { ReactNode } from 'react';

import BlurText from '@/components/reactbits/BlurText';
import DecryptedText from '@/components/reactbits/DecryptedText';
import Threads from '@/components/reactbits/Threads';
import { Wordmark } from '@/components/ui/Wordmark';

const PRINCIPLES = [
  ['Content quality', 'Clear, correct, meaning-preserving writing.'],
  ['Structural correctness', 'Headings, numbering and sections that hold together.'],
  ['Formatting compliance', 'Deterministic checks against the standard you choose.'],
  ['Visual quality', 'Pages and slides inspected the way readers see them.'],
] as const;

/** Split-screen layout for sign-in and registration. */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1.15fr_1fr]">
      <aside className="relative hidden overflow-hidden border-r border-ink-700 bg-ink-950 lg:block">
        {/* Threads: flowing lines of text, the visual metaphor for documents in motion. */}
        <div className="absolute inset-0" aria-hidden>
        <Threads
          className="h-full w-full"
          color="#8b93ff"
          accentColor="#f5c46b"
          amplitude={1.1}
          distance={0.2}
          lineCount={34}
          speed={0.35}
          opacity={0.75}
          enableMouseInteraction
        />
        </div>
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(80%_60%_at_20%_20%,transparent,#07080dcc)]" />
        <div className="relative flex h-full flex-col justify-between p-12">
          <Wordmark size="lg" />
          <div className="max-w-xl">
            <p className="label mb-5 text-gold/80">Document engineering platform</p>
            <BlurText
              text="Every document, engineered with precision."
              className="font-serif text-5xl leading-[1.08] font-semibold text-paper"
              animateBy="words"
              delay={90}
              trigger="load"
            />
            <p className="mt-6 font-mono text-sm text-paper-dim">
              <DecryptedText
                text="Intelligence Behind Every Document."
                animateOn="view"
                sequential
                revealDirection="start"
                speed={40}
                encryptedClassName="text-accent"
              />
            </p>
          </div>
          <dl className="grid max-w-xl grid-cols-2 gap-x-8 gap-y-5">
            {PRINCIPLES.map(([term, desc]) => (
              <div key={term} className="border-l border-gold/30 pl-4">
                <dt className="text-sm font-semibold text-paper">{term}</dt>
                <dd className="mt-1 text-xs leading-relaxed text-paper-faint">{desc}</dd>
              </div>
            ))}
          </dl>
        </div>
      </aside>
      <main className="ruled flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="mb-10 lg:hidden">
            <Wordmark />
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}
