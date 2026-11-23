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

function authHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  const t = getToken();
  if (t) headers.set('X-Tab-Token', t);
  return headers;
}

async function raiseIfBad(response: Response): Promise<void> {
  if (response.ok) return;
  let code = 'request_failed';
  let message = `${response.status} ${response.statusText}`.trim();
  let hint: string | undefined;
  let action: string | undefined;
  try {
    const body = await response.json();
    const detail = body?.detail && typeof body.detail === 'object' ? body.detail : body;
    if (typeof detail?.code === 'string') code = detail.code;
    if (typeof detail?.message === 'string') message = detail.message;
    if (typeof detail?.hint === 'string') hint = detail.hint;
    if (typeof detail?.action === 'string') action = detail.action;
  } catch {
    // Non-JSON error body: keep the status-based message.
  }
  throw new ApiError(code, message, hint, action);
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = authHeaders(init.headers);
  const response = await fetch(path, { ...init, headers });
  await raiseIfBad(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function apiUpload(
  file: File,
): Promise<{ upload_id: string; name: string; bytes: number; duration_sec: number }> {
  const body = new FormData();
  body.append('file', file);
  const response = await fetch('/api/uploads', {
    method: 'POST',
    headers: authHeaders(),
    body,
  });
  await raiseIfBad(response);
  return (await response.json()) as {
    upload_id: string;
    name: string;
    bytes: number;
    duration_sec: number;
  };
}

export type AudioKind = 'original' | 'stem' | 'lead' | 'rhythm';

export function audioUrl(runId: string, kind: AudioKind = 'original'): string {
  const t = getToken();
  const q = new URLSearchParams({ kind });
  // Token is sent via header for fetch; for <audio src> we rely on same-origin +
  // cookie-less header is unavailable, so append token query only if needed.
  // The server uses X-Tab-Token; browsers cannot set that on media elements.
  // Workaround: fetch blob URLs in the player instead of raw src when possible.
  void t;
  return `/api/runs/${encodeURIComponent(runId)}/audio?${q.toString()}`;
}

/** Fetch a binary export with auth header. */
export async function downloadExport(
  runId: string,
  payload: {
    format: string;
    tuning: string;
    capo: number;
    transpose: number;
    bars: number;
  },
): Promise<void> {
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}/export`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  });
  await raiseIfBad(response);
  const blob = await response.blob();
  const disp = response.headers.get('content-disposition') || '';
  const match = /filename="?([^"]+)"?/i.exec(disp);
  const name = match?.[1] || `export.${payload.format}`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

/** Authenticated audio blob URL for <audio>. */
export async function fetchAudioObjectUrl(
  runId: string,
  kind: AudioKind,
): Promise<string> {
  const response = await fetch(audioUrl(runId, kind), { headers: authHeaders() });
  await raiseIfBad(response);
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
