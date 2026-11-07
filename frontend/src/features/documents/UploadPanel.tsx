import { useRef, useState, type DragEvent } from 'react';
import { Link } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';

import { ApiError, uploadDocument, type DocumentOut } from '@/api/client';
import StatusMark, { type StatusMarkStatus } from '@/components/reactbits/StatusMark';
import { Icon } from '@/components/ui/Icon';
import { formatBytes } from '@/lib/format';
import { ACCEPT, precheck } from '@/lib/upload';

interface Item {
  id: string;
  name: string;
  size: number;
  status: StatusMarkStatus;
  progress: number;
  message?: string;
  doc?: DocumentOut;
}

export function UploadPanel({ compact = false }: { compact?: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [dragging, setDragging] = useState(false);
  const queryClient = useQueryClient();

  const patch = (id: string, p: Partial<Item>) =>
    setItems((list) => list.map((it) => (it.id === id ? { ...it, ...p } : it)));

  function start(files: FileList | File[]) {
    for (const file of Array.from(files)) {
      const id = crypto.randomUUID();
      const check = precheck(file);
      const item: Item = { id, name: file.name, size: file.size, status: 'running', progress: 0 };
      if (!check.ok) {
        setItems((l) => [{ ...item, status: 'failed', message: check.reason }, ...l]);
        continue;
      }
      setItems((l) => [item, ...l]);
      const { promise } = uploadDocument(file, (f) => patch(id, { progress: Math.min(f, 0.98) }));
      promise
        .then((doc) => {
          patch(id, { status: 'done', progress: 1, doc, message: 'Stored securely as version 1' });
          void queryClient.invalidateQueries({ queryKey: ['documents'] });
        })
        .catch((err: unknown) =>
          patch(id, { status: 'failed', message: err instanceof ApiError ? err.message : 'Upload failed.' }),
        );
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length) start(e.dataTransfer.files);
  }

  return (
    <section aria-label="Upload documents">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`group relative flex flex-col items-center justify-center rounded-2xl border border-dashed text-center transition-colors ${
          compact ? 'px-6 py-7' : 'px-6 py-12'
        } ${dragging ? 'border-accent bg-accent-soft' : 'border-ink-600 bg-ink-900/60 hover:border-ink-500'}`}
      >
        <div className="mb-3 grid size-11 place-items-center rounded-xl border border-ink-600 bg-ink-800 text-accent">
          <Icon name="upload" className="size-5" />
        </div>
        <p className="text-sm text-paper">
          Drop files here or{' '}
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="font-semibold text-accent underline-offset-4 hover:underline"
          >
            browse
          </button>
        </p>
        <p className="mt-1 text-xs text-paper-faint">DOCX, PDF or PPTX · up to 50 MB · macros are never accepted</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          className="sr-only"
          aria-label="Choose files to upload"
          onChange={(e) => {
            if (e.target.files) start(e.target.files);
            e.target.value = '';
          }}
        />
      </div>

      {items.length > 0 && (
        <ul className="mt-4 space-y-2" aria-live="polite">
          {items.map((it) => (
            <li key={it.id} className="surface flex items-center gap-4 px-4 py-3">
              <StatusMark
                status={it.status}
                progress={it.status === 'running' ? it.progress : undefined}
                size={22}
                color="#8b93ff"
                doneColor="#4ade80"
                errorColor="#f87171"
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{it.name}</p>
                <p className={`text-xs ${it.status === 'failed' ? 'text-sev-critical' : 'text-paper-faint'}`}>
                  {it.status === 'running'
                    ? `Uploading · ${Math.round(it.progress * 100)}% of ${formatBytes(it.size)}`
                    : it.message}
                </p>
              </div>
              {it.doc && (
                <Link to={`/documents/${it.doc.id}`} className="text-sm font-medium text-accent hover:text-accent-strong">
                  Open
                </Link>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
