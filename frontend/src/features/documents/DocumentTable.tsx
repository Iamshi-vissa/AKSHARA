import { Link } from 'react-router';

import type { DocumentOut } from '@/api/client';
import { KindBadge } from '@/components/ui/Badge';
import { Icon } from '@/components/ui/Icon';
import { formatBytes, relativeTime } from '@/lib/format';

export function DocumentTable({ docs }: { docs: DocumentOut[] }) {
  return (
    <div className="surface overflow-hidden">
      <table className="w-full text-sm">
        <thead className="border-b border-ink-700 bg-ink-900/60 text-left">
          <tr>
            <th scope="col" className="label px-5 py-3 font-medium">Document</th>
            <th scope="col" className="label hidden px-5 py-3 font-medium sm:table-cell">Type</th>
            <th scope="col" className="label hidden px-5 py-3 font-medium md:table-cell">Size</th>
            <th scope="col" className="label px-5 py-3 text-right font-medium">Added</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-700/70">
          {docs.map((d) => (
            <tr key={d.id} className="group transition-colors hover:bg-ink-800/60">
              <td className="max-w-0 px-5 py-3.5">
                <Link to={`/documents/${d.id}`} className="flex items-center gap-3 outline-none">
                  <Icon name="file" className="size-4 shrink-0 text-paper-faint group-hover:text-accent" />
                  <span className="min-w-0">
                    <span className="block truncate font-medium text-paper group-hover:text-accent-strong">{d.title}</span>
                    <span className="block truncate text-xs text-paper-faint">{d.original_filename}</span>
                  </span>
                  {d.safety_warnings.length > 0 && (
                    <span title="Security notes on this file" className="text-sev-medium">
                      <Icon name="shield" className="size-4" title="Security notes" />
                    </span>
                  )}
                </Link>
              </td>
              <td className="hidden px-5 py-3.5 sm:table-cell">
                <KindBadge kind={d.kind} />
              </td>
              <td className="hidden px-5 py-3.5 font-mono text-xs text-paper-dim md:table-cell">
                {d.current_version ? formatBytes(d.current_version.size_bytes) : '—'}
              </td>
              <td className="px-5 py-3.5 text-right text-xs whitespace-nowrap text-paper-dim">
                {relativeTime(d.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
