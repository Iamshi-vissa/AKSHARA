import { useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';

import { api, type DocumentKind, type DocumentPage } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { DocumentTable } from '@/features/documents/DocumentTable';
import { UploadPanel } from '@/features/documents/UploadPanel';

const KINDS: (DocumentKind | 'all')[] = ['all', 'docx', 'pdf', 'pptx'];

export function LibraryPage() {
  const [q, setQ] = useState('');
  const [kind, setKind] = useState<DocumentKind | 'all'>('all');

  const query = useInfiniteQuery({
    queryKey: ['documents', 'list', { q, kind }],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: '20' });
      if (q.trim()) params.set('q', q.trim());
      if (kind !== 'all') params.set('kind', kind);
      if (pageParam) params.set('cursor', pageParam);
      return api<DocumentPage>(`/documents?${params}`);
    },
    getNextPageParam: (last) => last.next_cursor ?? null,
  });

  const docs = query.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header>
        <p className="label text-gold/80">Library</p>
        <h1 className="mt-2 font-serif text-4xl font-semibold">Your documents</h1>
        <p className="mt-2 text-paper-dim">Every upload is validated by content, stored once, and kept as an immutable original.</p>
      </header>

      <UploadPanel />

      <section aria-label="Documents" className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <label className="relative min-w-60 flex-1">
            <span className="sr-only">Search documents</span>
            <Icon name="search" className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-paper-faint" />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by title"
              className="h-10 w-full rounded-lg border border-ink-600 bg-ink-900/80 pr-3 pl-9 text-sm outline-none placeholder:text-paper-faint focus:border-accent focus:ring-2 focus:ring-accent/25"
            />
          </label>
          <div role="radiogroup" aria-label="Filter by type" className="flex rounded-lg border border-ink-600 bg-ink-900/80 p-1">
            {KINDS.map((k) => (
              <button
                key={k}
                role="radio"
                aria-checked={kind === k}
                onClick={() => setKind(k)}
                className={`rounded-md px-3 py-1 text-xs font-medium uppercase transition-colors ${kind === k ? 'bg-accent-soft text-paper' : 'text-paper-faint hover:text-paper'}`}
              >
                {k}
              </button>
            ))}
          </div>
        </div>

        {query.isPending ? (
          <div className="surface h-64 animate-pulse" />
        ) : query.isError ? (
          <p role="alert" className="text-sm text-sev-critical">Could not load documents: {query.error.message}</p>
        ) : docs.length === 0 ? (
          <div className="surface px-6 py-12 text-center">
            <p className="font-serif text-lg">{q || kind !== 'all' ? 'No matching documents' : 'Your library is empty'}</p>
            <p className="mt-1 text-sm text-paper-faint">
              {q || kind !== 'all' ? 'Try a different search or filter.' : 'Upload a DOCX, PDF or PPTX above.'}
            </p>
          </div>
        ) : (
          <>
            <DocumentTable docs={docs} />
            {query.hasNextPage && (
              <div className="flex justify-center">
                <Button variant="secondary" onClick={() => void query.fetchNextPage()} loading={query.isFetchingNextPage}>
                  Load more
                </Button>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
