import { useEffect, useRef, type ReactNode } from 'react';

/** Accessible modal built on the native <dialog> element (focus trap + Esc for free). */
export function Dialog({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="dialog-title"
      className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-2xl border border-ink-600 bg-ink-850 p-0 text-paper shadow-2xl backdrop:bg-ink-950/70 backdrop:backdrop-blur-sm"
    >
      <div className="p-6">
        <h2 id="dialog-title" className="font-serif text-xl font-semibold">
          {title}
        </h2>
        <div className="mt-3">{children}</div>
      </div>
    </dialog>
  );
}
