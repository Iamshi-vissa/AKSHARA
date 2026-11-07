import ShinyText from '@/components/reactbits/ShinyText';

/** The AKSHARA wordmark. The product name is always "AKSHARA" (never "AKSHARA AI"). */
export function Wordmark({ size = 'md' }: { size?: 'md' | 'lg' }) {
  const text = size === 'lg' ? 'text-2xl' : 'text-lg';
  return (
    <span className="inline-flex items-center gap-2.5" aria-label="AKSHARA">
      <svg viewBox="0 0 64 64" className={size === 'lg' ? 'size-9' : 'size-7'} aria-hidden>
        <rect width="64" height="64" rx="14" fill="#151926" stroke="#2c3248" />
        <path d="M18 46 32 16l14 30" fill="none" stroke="#a5b4fc" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M23 36h18" stroke="#f5c46b" strokeWidth="4" strokeLinecap="round" />
      </svg>
      <ShinyText
        text="AKSHARA"
        color="#ecedf4"
        shineColor="#f5c46b"
        speed={3.2}
        delay={4}
        className={`font-serif ${text} font-semibold tracking-[0.22em]`}
      />
    </span>
  );
}
