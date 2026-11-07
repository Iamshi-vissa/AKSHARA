import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';

import { ApiError } from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Icon } from '@/components/ui/Icon';
import { useAuth } from '@/lib/auth';

function useRedirectTarget() {
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  return from && from.startsWith('/') && !from.startsWith('//') ? from : '/';
}

function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div role="alert" className="flex items-start gap-2 rounded-lg border border-sev-critical/30 bg-sev-critical/10 px-3.5 py-3 text-sm text-sev-critical">
      <Icon name="alert" className="mt-0.5 size-4 shrink-0" />
      {message}
    </div>
  );
}

export function LoginForm() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const target = useRedirectTarget();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await login(String(data.get('email')), String(data.get('password')));
      navigate(target, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not sign in. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5" noValidate>
      <header className="mb-8">
        <h1 className="font-serif text-3xl font-semibold">Welcome back</h1>
        <p className="mt-2 text-sm text-paper-dim">Sign in to your AKSHARA workspace.</p>
      </header>
      <FormError message={error} />
      <Field label="E-mail" name="email" type="email" autoComplete="email" required autoFocus />
      <Field label="Password" name="password" type="password" autoComplete="current-password" required />
      <Button type="submit" size="lg" className="w-full" loading={busy}>
        Sign in <Icon name="arrow" />
      </Button>
      <p className="text-center text-sm text-paper-faint">
        New to AKSHARA?{' '}
        <Link to="/register" className="font-medium text-accent hover:text-accent-strong">
          Create an account
        </Link>
      </p>
    </form>
  );
}

export function RegisterForm() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [password, setPassword] = useState('');

  const pwOk = password.length >= 10 && /[A-Za-z]/.test(password) && /[^A-Za-z]/.test(password);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await register(String(data.get('email')), password, String(data.get('name') || ''));
      navigate('/', { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create the account.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5" noValidate>
      <header className="mb-8">
        <h1 className="font-serif text-3xl font-semibold">Create your workspace</h1>
        <p className="mt-2 text-sm text-paper-dim">Your documents stay private to your account.</p>
      </header>
      <FormError message={error} />
      <Field label="Name (optional)" name="name" autoComplete="name" maxLength={120} />
      <Field label="E-mail" name="email" type="email" autoComplete="email" required />
      <Field
        label="Password"
        name="password"
        type="password"
        autoComplete="new-password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        hint={
          <span className={pwOk ? 'text-ok' : undefined}>
            At least 10 characters, with letters and a number or symbol.
          </span>
        }
      />
      <Button type="submit" size="lg" className="w-full" loading={busy} disabled={!pwOk}>
        Create account <Icon name="arrow" />
      </Button>
      <p className="text-center text-sm text-paper-faint">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-accent hover:text-accent-strong">
          Sign in
        </Link>
      </p>
    </form>
  );
}
