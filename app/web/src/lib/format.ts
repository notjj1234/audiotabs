/** Human formatting: one size formatter, timecodes, sentence joins. */

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const mb = bytes / (1024 * 1024);
  if (mb >= 1) return `${mb.toFixed(1)} MB`;
  const kb = bytes / 1024;
  if (kb >= 1) return `${kb.toFixed(1)} KB`;
  return `${Math.round(bytes)} B`;
}

export function formatDuration(totalSeconds: number): string {
  if (!Number.isFinite(totalSeconds) || totalSeconds < 0) return '0:00';
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

export function joinSentence(first: string, second: string): string {
  const lead = first.trim();
  const rest = second.trim();
  if (!lead) return rest;
  if (!rest) return lead;
  const punctuated = /[.!?]$/.test(lead) ? lead : `${lead}.`;
  return `${punctuated} ${rest.charAt(0).toUpperCase()}${rest.slice(1)}`;
}
