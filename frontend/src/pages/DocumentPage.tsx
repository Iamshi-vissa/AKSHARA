import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, ApiError, downloadVersion, json, type DocumentOut, type VersionOut } from '@/api/client';
import { Badge, KindBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Icon } from '@/components/ui/Icon';
import { describeWarning, formatBytes, formatDate } from '@/lib/format';

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1 py-3 sm:flex-row sm:items-baseline sm:gap-6">
      <dt className="label w-36 shrink-0">{label}</dt>
      <dd className="min-w-0 text-sm text-paper">{children}</dd>
    </div>
  );
}

export function DocumentPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const doc = useQuery({ queryKey: ['documents', id], queryFn: () => api<DocumentOut>(`/documents/${id}`) });
  const versions = useQuery({
    queryKey: ['documents', id, 'versions'],
    queryFn: () => api<VersionOut[]>(`/documents/${id}/versions`),
    enabled: doc.isSuccess,
  });

  const rename = useMutation({
    mutationFn: (title: string) => api<DocumentOut>(`/documents/${id}`, { method: 'PATCH', ...json({ title }) }),
    onSuccess: (d) => {
      queryClient.setQueryData(['documents', id], d);
      void queryClient.invalidateQueries({ queryKey: ['documents'] });
      setEditing(false);
    },
  });
  const remove = useMutation({
    mutationFn: () => api<void>(`/documents/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['documents'] });
      navigate('/documents');
    },
  });

  async function download(v: VersionOut, name: string) {
    setDownloadError(null);
    try {
      await downloadVersion(v.id, name);
    } catch (e) {
      setDownloadError(e instanceof ApiError ? e.message : 'Download failed.');
    }
  }

  if (doc.isPending) return <div className="surface mx-auto h-96 max-w-5xl animate-pulse" />;
  if (doc.isError) {
    const notFound = doc.error instanceof ApiError && doc.error.status === 404;
    return (
      <div className="mx-auto max-w-xl py-20 text-center">
        <h1 className="font-serif text-3xl">{notFound ? 'Document not found' : 'Something went wrong'}</h1>
        <p className="mt-2 text-paper-dim">{notFound ? 'It may have been deleted, or it belongs to another account.' : doc.error.message}</p>
        <Link to="/documents" className="mt-6 inline-block text-accent">Back to library</Link>
      </div>
    );
  }

  const d = doc.data;
  const v = d.current_version;

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <Link to="/documents" className="inline-flex items-center gap-2 text-sm text-paper-faint hover:text-paper">
        <Icon name="back" /> Library
      </Link>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="mb-3 flex items-center gap-2">
            <KindBadge kind={d.kind} />
            <Badge tone="accent">v{v?.number ?? 1}</Badge>
            <Badge tone="ok">
              <Icon name="lock" className="size-3" /> Original preserved
            </Badge>
          </div>
          {editing ? (
            <form
              className="flex flex-wrap gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                const title = String(new FormData(e.currentTarget).get('title') ?? '').trim();
                if (title) rename.mutate(title);
              }}
            >
              <input
                name="title"
                defaultValue={d.title}
                maxLength={300}
                autoFocus
                aria-label="Document title"
                className="h-11 min-w-0 flex-1 rounded-lg border border-accent bg-ink-900 px-3 font-serif text-2xl outline-none"
              />
              <Button type="submit" loading={rename.isPending}>Save</Button>
              <Button type="button" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
            </form>
          ) : (
            <h1 className="font-serif text-4xl font-semibold break-words">
              {d.title}
              <button onClick={() => setEditing(true)} className="ml-3 align-middle text-paper-faint hover:text-accent" aria-label="Rename document">
                <Icon name="edit" className="size-5" />
              </button>
            </h1>
          )}
          {rename.isError && <p className="mt-2 text-sm text-sev-critical">{rename.error.message}</p>}
        </div>
        <div className="flex gap-2">
          {v && (
            <Button onClick={() => void download(v, d.original_filename)}>
              <Icon name="download" /> Download original
            </Button>
          )}
          <Button variant="danger" onClick={() => setConfirmDelete(true)} aria-label="Delete document">
            <Icon name="trash" />
          </Button>
        </div>
      </header>
      {downloadError && <p role="alert" className="text-sm text-sev-critical">{downloadError}</p>}

      {d.safety_warnings.length > 0 && (
        <section className="rounded-2xl border border-sev-medium/30 bg-sev-medium/5 p-5" aria-labelledby="sec-h">
          <h2 id="sec-h" className="flex items-center gap-2 font-semibold text-sev-medium">
            <Icon name="shield" /> Security notes
          </h2>
          <p className="mt-1 text-sm text-paper-dim">AKSHARA found active content in this file. It is stored as-is but is never executed.</p>
          <ul className="mt-3 space-y-1 text-sm text-paper">
            {d.safety_warnings.map((w) => (
              <li key={w} className="flex gap-2"><span className="text-sev-medium">•</span>{describeWarning(w)}</li>
            ))}
          </ul>
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <section className="surface px-6 py-3" aria-label="File details">
          <dl className="divide-y divide-ink-700/70">
            <Meta label="Original name">{d.original_filename}</Meta>
            <Meta label="Size">{v ? formatBytes(v.size_bytes) : '—'}</Meta>
            <Meta label="Uploaded">{formatDate(d.created_at)}</Meta>
            <Meta label="SHA-256">
              <code className="block font-mono text-xs break-all text-paper-dim">{v?.sha256}</code>
            </Meta>
          </dl>
        </section>

        <section className="surface p-6" aria-labelledby="analysis-h">
          <h2 id="analysis-h" className="font-serif text-lg font-semibold">Analysis</h2>
          <p className="mt-2 text-sm leading-relaxed text-paper-dim">
            Structure, preview and inspection are not run yet. Parsing into AKSHARA&apos;s canonical document model arrives in
            Phase 2, and inspection in Phase 3.
          </p>
          <Badge>Not analysed</Badge>
        </section>
      </div>

      <section aria-labelledby="versions-h">
        <h2 id="versions-h" className="mb-4 flex items-center gap-2 font-serif text-2xl font-semibold">
          <Icon name="history" className="size-5 text-gold" /> Version history
        </h2>
        <ol className="surface divide-y divide-ink-700/70">
          {(versions.data ?? []).map((ver) => (
            <li key={ver.id} className="flex flex-wrap items-center gap-4 px-5 py-4">
              <span className="grid size-9 place-items-center rounded-full border border-gold/30 bg-gold-soft font-mono text-sm text-gold">
                {ver.number}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{ver.created_by === 'upload' ? 'Original upload' : ver.created_by}</p>
                <p className="text-xs text-paper-faint">
                  {formatDate(ver.created_at)} · {formatBytes(ver.size_bytes)} · <span className="font-mono">{ver.sha256.slice(0, 12)}…</span>
                </p>
              </div>
              <Button variant="secondary" size="sm" onClick={() => void download(ver, d.original_filename)}>
                <Icon name="download" /> Download
              </Button>
            </li>
          ))}
          {versions.isPending && <li className="h-16 animate-pulse" />}
        </ol>
      </section>

      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)} title="Remove this document?">
        <p className="text-sm text-paper-dim">
          It will disappear from your library. The original file is retained in storage and is never destroyed.
        </p>
        {remove.isError && <p className="mt-2 text-sm text-sev-critical">{remove.error.message}</p>}
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setConfirmDelete(false)}>Cancel</Button>
          <Button variant="danger" loading={remove.isPending} onClick={() => remove.mutate()}>Remove</Button>
        </div>
      </Dialog>
    </div>
  );
}
