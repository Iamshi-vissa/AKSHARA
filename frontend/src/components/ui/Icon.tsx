/** Small inline icon set (no icon-library dependency). Stroke icons on a 24px grid. */
const PATHS = {
  dashboard: 'M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z',
  library: 'M5 4h4v16H5zM10 4h4v16h-4zM15.5 4.5l3.8-1 3.2 15.5-3.8 1z',
  upload: 'M12 16V4m0 0-5 5m5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3',
  download: 'M12 4v12m0 0-5-5m5 5 5-5M4 20h16',
  standard: 'M12 3 4 7v6c0 4 3.5 7 8 8 4.5-1 8-4 8-8V7z M9 12l2 2 4-4',
  inspect: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm9 16-4.3-4.3',
  edit: 'M4 20h4L19 9l-4-4L4 16zM14 6l4 4',
  create: 'M6 3h9l4 4v14H6zM14 3v5h5M12 11v6M9 14h6',
  slides: 'M3 5h18v11H3zM12 16v4M8 20h8',
  quality: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
  research: 'M4 5h6a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H4zM20 5h-6a3 3 0 0 0-3 3',
  visual: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zm10-3a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  settings:
    'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.8 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 2.6 14H2.5a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.6 7a1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 10 2.6V2.5a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 2.8 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8 1.7 1.7 0 0 0 1.5 1h.2a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
  logout: 'M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l5-5-5-5M15 12H3',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm9 16-4.3-4.3',
  trash: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13',
  shield: 'M12 3 4 7v6c0 4 3.5 7 8 8 4.5-1 8-4 8-8V7z',
  alert: 'M12 3 2 20h20zM12 10v4M12 17v.5',
  lock: 'M6 11h12v9H6zM8 11V8a4 4 0 0 1 8 0v3',
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  back: 'M19 12H5m6 6-6-6 6-6',
  file: 'M6 3h9l4 4v14H6zM14 3v5h5',
  check: 'M5 12l5 5 9-10',
  x: 'M6 6l12 12M18 6 6 18',
  history: 'M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 3',
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, className = 'size-4', title }: { name: IconName; className?: string; title?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
    >
      {title && <title>{title}</title>}
      <path d={PATHS[name]} />
    </svg>
  );
}
