import { Link } from 'react-router';

import { useCapabilities } from '@/components/layout/AppShell';
import DecryptedText from '@/components/reactbits/DecryptedText';

/** Honest placeholder for modules that are not built yet. No fake results. */
export function ComingSoonPage({ capability }: { capability: string }) {
  const caps = useCapabilities();
  const cap = caps.data?.capabilities.find((c) => c.key === capability);
  return (
    <div className="mx-auto max-w-xl py-24 text-center">
      <p className="label text-gold/80">Phase {cap?.phase ?? '—'}</p>
      <h1 className="mt-3 font-serif text-4xl font-semibold">
        <DecryptedText text={cap?.label ?? 'Not available yet'} animateOn="view" sequential speed={35} />
      </h1>
      <p className="mt-3 text-paper-dim">{cap?.note}</p>
      <p className="mt-6 text-sm text-paper-faint">
        This module is not built yet. AKSHARA only shows features once they are implemented and verified.
      </p>
      <Link to="/" className="mt-8 inline-block text-sm font-medium text-accent">Back to dashboard</Link>
    </div>
  );
}

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-xl py-24 text-center">
      <p className="label">404</p>
      <h1 className="mt-3 font-serif text-4xl font-semibold">Page not found</h1>
      <Link to="/" className="mt-8 inline-block text-sm font-medium text-accent">Back to dashboard</Link>
    </div>
  );
}
