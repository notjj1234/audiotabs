/** Token-authenticated fetch wrapper for the local API. */

export class ApiError extends Error {
  code: string;
  hint: string | undefined;
  action: string | undefined;

  constructor(code: string, message: string, hint?: string, action?: string) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.hint = hint;
    this.action = action;
  }
}

let token: string | null = null;

/** Read `#token=…` once, keep it in memory, and clear it from the URL. */
export function getToken(): string | null {
  if (token !== null) return token;
  const match = window.location.hash.match(/(?:^#|&)token=([^&]+)/);
  if (match) {
    token = decodeURIComponent(match[1]);
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
  }
  return token;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const t = getToken();
  if (t) headers.set('X-Tab-Token', t);
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    let code = 'request_failed';
    let message = `${response.status} ${response.statusText}`.trim();
    let hint: string | undefined;
    let action: string | undefined;
    try {
      const body = await response.json();
      if (typeof body?.code === 'string') code = body.code;
      if (typeof body?.message === 'string') message = body.message;
      if (typeof body?.hint === 'string') hint = body.hint;
      if (typeof body?.action === 'string') action = body.action;
    } catch {
      // Non-JSON error body: keep the status-based message.
    }
    throw new ApiError(code, message, hint, action);
  }
  return (await response.json()) as T;
}
