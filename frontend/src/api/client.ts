/**
 * Typed API client.
 *
 * - Types come from the backend's OpenAPI schema (`npm run gen:api`), never hand-written.
 * - The access token lives in memory only. The refresh token is an httpOnly cookie the
 *   browser sends to /api/v1/auth automatically; JavaScript can never read it.
 * - A 401 triggers one silent refresh, then the request is retried once.
 */
import type { components } from './schema';

export type User = components['schemas']['UserOut'];
export type DocumentOut = components['schemas']['DocumentOut'];
export type VersionOut = components['schemas']['VersionOut'];
export type DocumentStats = components['schemas']['DocumentStats'];
export type DocumentPage = components['schemas']['Page_DocumentOut_'];
export type Capability = components['schemas']['Capability'];
export type Capabilities = components['schemas']['CapabilitiesOut'];
export type TokenResponse = components['schemas']['TokenResponse'];
export type DocumentKind = DocumentOut['kind'];

export const API_BASE = '/api/v1';

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
    public requestId?: string | null,
  ) {
    super(message);
  }
}

let accessToken: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;
let onSessionLost: (() => void) | null = null;

export const session = {
  set(token: string | null) {
    accessToken = token;
  },
  get() {
    return accessToken;
  },
  onLost(cb: () => void) {
    onSessionLost = cb;
  },
};

export async function toApiError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const err = body?.error;
    if (err) {
      let message: string = err.message;
      const first = err.details?.errors?.[0];
      if (err.code === 'VALIDATION_ERROR' && first?.msg) message = String(first.msg).replace(/^Value error, /, '');
      return new ApiError(res.status, err.code, message, err.details ?? {}, err.request_id);
    }
  } catch {
    /* non-JSON body */
  }
  return new ApiError(res.status, 'HTTP_ERROR', `Request failed (${res.status}).`);
}

export async function refreshSession(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, { method: 'POST', credentials: 'same-origin' });
      if (!res.ok) {
        accessToken = null;
        return false;
      }
      const body = (await res.json()) as TokenResponse;
      accessToken = body.access_token;
      return true;
    } catch {
      return false;
    } finally {
      setTimeout(() => (refreshInFlight = null), 0);
    }
  })();
  return refreshInFlight;
}

export async function apiFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'same-origin' });
  if (res.status === 401 && retry && !path.startsWith('/auth/')) {
    if (await refreshSession()) return apiFetch(path, init, false);
    onSessionLost?.();
  }
  if (!res.ok) throw await toApiError(res);
  return res;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, init);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });

/** Upload with real progress events (fetch has no upload progress API). */
export function uploadDocument(
  file: File,
  onProgress: (fraction: number) => void,
  title?: string,
): { promise: Promise<DocumentOut>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  const send = (token: string | null) =>
    new Promise<{ status: number; body: string }>((resolve, reject) => {
      xhr.open('POST', `${API_BASE}/documents`);
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
      xhr.onload = () => resolve({ status: xhr.status, body: xhr.responseText });
      xhr.onerror = () => reject(new ApiError(0, 'NETWORK_ERROR', 'Network error during upload.'));
      xhr.onabort = () => reject(new ApiError(0, 'ABORTED', 'Upload cancelled.'));
      const form = new FormData();
      form.append('file', file);
      if (title) form.append('title', title);
      xhr.send(form);
    });

  const promise = (async () => {
    let result = await send(accessToken);
    if (result.status === 401 && (await refreshSession())) result = await send(accessToken);
    const parsed = result.body ? JSON.parse(result.body) : null;
    if (result.status >= 400) {
      const err = parsed?.error;
      throw new ApiError(result.status, err?.code ?? 'HTTP_ERROR', err?.message ?? 'Upload failed.');
    }
    return parsed as DocumentOut;
  })();
  return { promise, abort: () => xhr.abort() };
}

/** Download a version with the auth header, then hand the browser a local object URL. */
export async function downloadVersion(versionId: string, fallbackName: string): Promise<void> {
  const res = await apiFetch(`/versions/${versionId}/file`);
  const disposition = res.headers.get('Content-Disposition') ?? '';
  const match = /filename\*=UTF-8''([^;]+)/.exec(disposition);
  const name = match?.[1] ? decodeURIComponent(match[1]) : fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
