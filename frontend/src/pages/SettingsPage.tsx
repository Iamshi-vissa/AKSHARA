import { useState, type FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';

import { api, json, type User } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { useAuth } from '@/lib/auth';

export function SettingsPage() {
  const { user, setUser } = useAuth();
  const [saved, setSaved] = useState(false);
  const save = useMutation({
    mutationFn: (body: Partial<User>) => api<User>('/auth/me', { method: 'PATCH', ...json(body) }),
    onSuccess: (u) => {
      setUser(u);
      setSaved(true);
    },
  });
  if (!user) return null;

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setSaved(false);
    save.mutate({
      display_name: String(f.get('display_name') ?? ''),
      preferred_unit: f.get('preferred_unit') as User['preferred_unit'],
      allow_external_llm: f.get('allow_external_llm') === 'on',
    });
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <header>
        <p className="label text-gold/80">Settings</p>
        <h1 className="mt-2 font-serif text-4xl font-semibold">Account & privacy</h1>
      </header>
      <form onSubmit={onSubmit} className="surface space-y-6 p-6">
        <Field label="E-mail" value={user.email} disabled readOnly />
        <Field label="Display name" name="display_name" defaultValue={user.display_name ?? ''} maxLength={120} />
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium text-paper-dim">Measurement unit</legend>
          <div className="flex gap-2">
            {(['pt', 'mm', 'in'] as const).map((u) => (
              <label key={u} className="flex cursor-pointer items-center gap-2 rounded-lg border border-ink-600 px-4 py-2 text-sm has-[:checked]:border-accent has-[:checked]:bg-accent-soft">
                <input type="radio" name="preferred_unit" value={u} defaultChecked={user.preferred_unit === u} className="accent-[#8b93ff]" />
                {u}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="flex cursor-pointer gap-3 rounded-xl border border-ink-600 p-4 has-[:checked]:border-gold/40 has-[:checked]:bg-gold-soft">
          <input type="checkbox" name="allow_external_llm" defaultChecked={user.allow_external_llm} className="mt-1 size-4 accent-[#f5c46b]" />
          <span>
            <span className="block text-sm font-medium">Allow external AI providers</span>
            <span className="mt-1 block text-xs leading-relaxed text-paper-faint">
              Off by default. When on, AI features (from Phase 5) may send selected document text to the configured language-model provider.
              No document content is ever logged.
            </span>
          </span>
        </label>
        <div className="flex items-center gap-3">
          <Button type="submit" loading={save.isPending}>Save changes</Button>
          {saved && <span role="status" className="text-sm text-ok">Saved</span>}
          {save.isError && <span role="alert" className="text-sm text-sev-critical">{save.error.message}</span>}
        </div>
      </form>
    </div>
  );
}
