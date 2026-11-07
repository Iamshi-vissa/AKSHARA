import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-accent text-ink-950 hover:bg-accent-strong shadow-[0_0_0_1px_#a5acff55,0_8px_24px_-8px_#8b93ff88] disabled:shadow-none',
  secondary: 'border border-ink-600 bg-ink-800 text-paper hover:border-ink-500 hover:bg-ink-700',
  ghost: 'text-paper-dim hover:bg-ink-800 hover:text-paper',
  danger: 'border border-sev-critical/40 bg-sev-critical/10 text-sev-critical hover:bg-sev-critical/20',
};

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  loading = false,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  children: ReactNode;
}) {
  const sizes = { sm: 'h-8 px-3 text-sm', md: 'h-10 px-4 text-sm', lg: 'h-12 px-5 text-base' }[size];
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${sizes} ${VARIANTS[variant]} ${className}`}
      disabled={rest.disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && (
        <span className="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden />
      )}
      {children}
    </button>
  );
}
