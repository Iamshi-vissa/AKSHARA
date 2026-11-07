export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = bytes / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[i]}`;
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso));
}

export function relativeTime(iso: string, now = Date.now()): string {
  const diff = (new Date(iso).getTime() - now) / 1000;
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [
    ['second', 60],
    ['minute', 60],
    ['hour', 24],
    ['day', 30],
    ['month', 12],
    ['year', Infinity],
  ];
  let value = diff;
  for (const [unit, size] of steps) {
    if (Math.abs(value) < size) return rtf.format(Math.round(value), unit);
    value /= size;
  }
  return formatDate(iso);
}

const WARNING_LABELS: Record<string, string> = {
  'pdf_active_content:javascript': 'Contains JavaScript (never executed by AKSHARA)',
  'pdf_active_content:launch_action': 'Has a launch action (ignored)',
  'pdf_active_content:embedded_file': 'Contains embedded files (not extracted)',
  'pdf_active_content:rich_media': 'Contains rich media (not played)',
  'pdf_active_content:xfa_form': 'Contains an XFA form (not executed)',
  'pdf_active_content:submit_form': 'Has a form-submit action (never triggered)',
  'pdf_active_content:import_data': 'Has a data-import action (never triggered)',
  'pdf_active_content:embedded_goto': 'Links into an embedded file (not followed)',
};

export const describeWarning = (code: string) => WARNING_LABELS[code] ?? code;
