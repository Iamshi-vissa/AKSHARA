import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';

import { App } from '@/App';
import { AuthProvider } from '@/lib/auth';

function jsonResponse(status: number, body: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function renderApp(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const capabilities = {
  product: 'AKSHARA',
  version: '0.1.0',
  capabilities: [
    { key: 'upload', label: 'Secure upload & library', available: true, phase: 1, note: '' },
    { key: 'inspect', label: 'Inspect document', available: false, phase: 3, note: '' },
    { key: 'standards', label: 'Apply standard (UDSE)', available: false, phase: 4, note: '' },
  ],
};

describe('authentication flow', () => {
  it('does not probe for a session on a first visit', async () => {
    localStorage.clear();
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('redirects anonymous users to sign-in and shows server errors', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith('/auth/refresh')) return jsonResponse(401, { error: { code: 'NO_SESSION', message: 'x' } });
      if (url.endsWith('/auth/login'))
        return jsonResponse(401, { error: { code: 'INVALID_CREDENTIALS', message: 'Incorrect e-mail or password.' } });
      return jsonResponse(404, {});
    });
    renderApp('/documents');
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('E-mail'), 'ada@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong-password');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect e-mail or password.');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/login', expect.objectContaining({ method: 'POST' }));
  });

  it('keeps the register button disabled until the password meets the rules', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(401, { error: { code: 'NO_SESSION', message: '' } }));
    renderApp('/register');
    const button = await screen.findByRole('button', { name: /create account/i });
    expect(button).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Password'), 'onlyletters');
    expect(button).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Password'), '-2026');
    expect(button).toBeEnabled();
  });

  it('restores a session and shows unbuilt modules as locked, not fake', async () => {
    localStorage.setItem('akshara.session-hint', '1');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith('/auth/refresh')) return jsonResponse(200, { access_token: 't', token_type: 'bearer', expires_in: 900 });
      if (url.endsWith('/auth/me'))
        return jsonResponse(200, {
          id: '1', email: 'ada@example.com', display_name: 'Ada Lovelace', preferred_unit: 'pt',
          allow_external_llm: false, created_at: '2026-11-07T00:00:00Z',
        });
      if (url.endsWith('/capabilities')) return jsonResponse(200, capabilities);
      if (url.includes('/documents/stats')) return jsonResponse(200, { documents: 0, versions: 0, stored_bytes: 0, by_kind: {} });
      if (url.includes('/documents')) return jsonResponse(200, { items: [], next_cursor: null });
      return jsonResponse(404, {});
    });
    renderApp('/');
    expect(await screen.findByText('No documents yet')).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText('Phase 3').length).toBeGreaterThan(0));
    const inspectCard = screen.getByText('Inspect document').closest('[aria-disabled="true"]');
    expect(inspectCard).not.toBeNull();
    expect(screen.getByText('Upload & store').closest('a')).toHaveAttribute('href', '/documents');
  });
});
