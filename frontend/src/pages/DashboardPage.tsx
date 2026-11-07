import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';

import { api, type Capability, type DocumentPage, type DocumentStats } from '@/api/client';
import { useCapabilities } from '@/components/layout/AppShell';
import BlurText from '@/components/reactbits/BlurText';
import CountUp from '@/components/reactbits/CountUp';
import SpotlightCard from '@/components/reactbits/SpotlightCard';
import { Badge } from '@/components/ui/Badge';
import { Icon, type IconName } from '@/components/ui/Icon';
import { DocumentTable } from '@/features/documents/DocumentTable';
import { UploadPanel } from '@/features/documents/UploadPanel';
import { useAuth } from '@/lib/auth';
import { formatBytes } from '@/lib/format';

/** Quick actions from the brief. Each reflects the server's real capability flags. */
const ACTIONS: { key: string; title: string; icon: IconName; to: string; blurb: string }[] = [
  { key: 'upload', title: 'Upload & store', icon: 'upload', to: '/documents', blurb: 'Add DOCX, PDF or PPTX to your secure library.' },
  { key: 'inspect', title: 'Inspect document', icon: 'inspect', to: '/inspect', blurb: 'Find structural and formatting defects.' },
  { key: 'standards', title: 'Apply standard', icon: 'standard', to: '/standards', blurb: 'Validate against IEEE, APA, MLA or your own rules.' },
  { key: 'edit', title: 'Edit document', icon: 'edit', to: '/edit', blurb: 'Tracked, approval-gated improvements.' },
  { key: 'create', title: 'Create document', icon: 'create', to: '/create', blurb: 'Outline-first drafting with real citations.' },
  { key: 'presentations', title: 'Generate presentation', icon: 'slides', to: '/presentations', blurb: 'Themed decks, validated slide by slide.' },
];

function ActionCard({ action, cap }: { action: (typeof ACTIONS)[number]; cap?: Capability }) {
  const available = cap?.available ?? false;
  const body = (
    <SpotlightCard
      className={`h-full rounded-2xl border border-ink-700 bg-ink-850/80 p-5 transition-colors ${available ? 'hover:border-ink-500' : 'opacity-70'}`}
      spotlightColor={available ? 'rgba(139, 147, 255, 0.22)' : 'rgba(148, 163, 184, 0.10)'}
      theme="dark"
    >
      <div className="flex items-start justify-between">
        <span className={`grid size-10 place-items-center rounded-xl border ${available ? 'border-accent/30 bg-accent-soft text-accent' : 'border-ink-600 bg-ink-800 text-paper-faint'}`}>
          <Icon name={action.icon} className="size-5" />
        </span>
        {available ? <Badge tone="ok">Ready</Badge> : <Badge>Phase {cap?.phase ?? '—'}</Badge>}
      </div>
      <h3 className="mt-4 font-semibold text-paper">{action.title}</h3>
      <p className="mt-1 text-sm leading-relaxed text-paper-faint">{action.blurb}</p>
    </SpotlightCard>
  );
  return available ? (
    <Link to={action.to} className="block h-full rounded-2xl">
      {body}
    </Link>
  ) : (
    <div aria-disabled="true" title={`Not available yet — arrives in Phase ${cap?.phase}`} className="h-full cursor-not-allowed">
      {body}
    </div>
  );
}

function Stat({ label, value, suffix, hint, decimals = 0 }: { label: string; value: number | null; suffix?: string; hint?: string; decimals?: number }) {
  return (
    <div className="surface px-5 py-4">
      <p className="label">{label}</p>
      <p className="mt-2 font-serif text-3xl font-semibold text-paper tabular-nums">
        {value === null ? <span className="inline-block h-8 w-16 animate-pulse rounded bg-ink-700" /> : <CountUp to={value} duration={1.1} separator="," suffix={suffix} decimals={decimals} />}
      </p>
      {hint && <p className="mt-1 text-xs text-paper-faint">{hint}</p>}
    </div>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const caps = useCapabilities();
  const stats = useQuery({ queryKey: ['documents', 'stats'], queryFn: () => api<DocumentStats>('/documents/stats') });
  const recent = useQuery({ queryKey: ['documents', 'recent'], queryFn: () => api<DocumentPage>('/documents?limit=5') });

  const name = user?.display_name?.split(' ')[0];
  const s = stats.data;
  const stored = s ? formatBytes(s.stored_bytes) : null;
  const [storedNum, storedUnit] = stored ? stored.split(' ') : [null, ''];

  return (
    <div className="mx-auto max-w-6xl space-y-10">
      <header>
        <p className="label text-gold/80">Dashboard</p>
        <BlurText
          text={name ? `Good to see you, ${name}.` : 'Your document workspace.'}
          className="mt-2 font-serif text-4xl font-semibold text-paper"
          animateBy="words"
          delay={70}
          trigger="load"
        />
        <p className="mt-2 max-w-2xl text-paper-dim">
          Content quality, structural correctness, formatting compliance and visual quality, all in one place.
        </p>
      </header>

      <section aria-label="Library statistics" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Documents" value={s ? s.documents : null} />
        <Stat label="Versions" value={s ? s.versions : null} hint="Originals are never overwritten" />
        <Stat
          label="Stored"
          value={storedNum ? Number(storedNum) : null}
          decimals={storedNum?.includes('.') ? 1 : 0}
          suffix={storedUnit ? ` ${storedUnit}` : ''}
          hint="Deduplicated by content"
        />
        <div className="surface px-5 py-4">
          <p className="label">By type</p>
          <div className="mt-3 space-y-1.5 font-mono text-xs">
            {(['docx', 'pdf', 'pptx'] as const).map((k) => (
              <div key={k} className="flex justify-between text-paper-dim">
                <span className="uppercase">{k}</span>
                <span className="text-paper">{s?.by_kind[k] ?? 0}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section aria-labelledby="actions-h">
        <div className="mb-4 flex items-end justify-between">
          <h2 id="actions-h" className="font-serif text-2xl font-semibold">Quick actions</h2>
          <p className="text-xs text-paper-faint">Modules unlock as each phase is verified.</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {ACTIONS.map((a) => (
            <ActionCard key={a.key} action={a} cap={caps.data?.capabilities.find((c) => c.key === a.key)} />
          ))}
        </div>
      </section>

      <section aria-labelledby="recent-h" className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div>
          <div className="mb-4 flex items-end justify-between">
            <h2 id="recent-h" className="font-serif text-2xl font-semibold">Recent documents</h2>
            <Link to="/documents" className="text-sm font-medium text-accent hover:text-accent-strong">
              View library
            </Link>
          </div>
          {recent.isPending ? (
            <div className="surface h-48 animate-pulse" />
          ) : recent.data && recent.data.items.length > 0 ? (
            <DocumentTable docs={recent.data.items} />
          ) : (
            <div className="surface px-6 py-10 text-center">
              <p className="font-serif text-lg">No documents yet</p>
              <p className="mt-1 text-sm text-paper-faint">Upload your first file to start building your library.</p>
            </div>
          )}
        </div>
        <div>
          <h2 className="mb-4 font-serif text-2xl font-semibold">Upload</h2>
          <UploadPanel compact />
        </div>
      </section>
    </div>
  );
}
