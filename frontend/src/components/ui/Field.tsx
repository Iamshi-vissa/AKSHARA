import { useId, type InputHTMLAttributes, type ReactNode } from 'react';

export function Field({
  label,
  hint,
  error,
  className = '',
  ...input
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: ReactNode; error?: string | null }) {
  const id = useId();
  const hintId = `${id}-hint`;
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-paper-dim">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={hint || error ? hintId : undefined}
        className="h-11 w-full rounded-lg border border-ink-600 bg-ink-900/80 px-3.5 text-paper placeholder:text-paper-faint transition-colors outline-none hover:border-ink-500 focus:border-accent focus:ring-2 focus:ring-accent/25 aria-[invalid]:border-sev-critical/70"
        {...input}
      />
      {(error || hint) && (
        <p id={hintId} className={`mt-1.5 text-xs ${error ? 'text-sev-critical' : 'text-paper-faint'}`}>
          {error || hint}
        </p>
      )}
    </div>
  );
}
