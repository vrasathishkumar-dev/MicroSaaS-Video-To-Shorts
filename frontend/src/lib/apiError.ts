/** Turn a FastAPI `detail` (string or validation-error array) into a string. */
export function formatDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d && typeof d === 'object' && 'msg' in d ? String(d.msg) : ''))
      .filter(Boolean);
    if (msgs.length) return msgs.join('; ');
  }
  return fallback;
}

/** Extract a displayable message from an axios-style error. */
export function getApiErrorMessage(err: unknown, fallback: string): string {
  const data = (err as { response?: { data?: { detail?: unknown; message?: unknown } } } | null)
    ?.response?.data;
  if (typeof data?.message === 'string' && data.message && data.detail == null) return data.message;
  return formatDetail(data?.detail, fallback);
}
