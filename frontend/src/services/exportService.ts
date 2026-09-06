import api, { API_URL, getAccessToken } from '@/services/api';

/** Shape returned by both the export-trigger and export-status endpoints. */
export interface ExportStatusResponse {
  clip_id: number;
  status: 'idle' | 'rendering' | 'ready' | 'failed';
  video_file_path: string | null;
}

/**
 * Kick off (or re-kick off, on retry) export rendering for a clip.
 */
export async function triggerExport(
  clipId: number,
): Promise<ExportStatusResponse> {
  const { data } = await api.post<ExportStatusResponse>(
    `/clips/${clipId}/export`,
  );
  return data;
}

/**
 * Poll the current export status for a clip.
 */
export async function getExportStatus(
  clipId: number,
): Promise<ExportStatusResponse> {
  const { data } = await api.get<ExportStatusResponse>(
    `/clips/${clipId}/export/status`,
  );
  return data;
}

/**
 * Generates an authenticated direct download URL for the clip.
 * Uses a `?token=` query param so native browser downloads can stream
 * directly to disk without bloating JavaScript tab memory.
 */
export function getClipDownloadUrl(clipId: number): string {
  const token = getAccessToken();
  const query = token ? `?token=${encodeURIComponent(token)}` : '';
  return `${API_URL}/api/v1/clips/${clipId}/download${query}`;
}

/**
 * Download the rendered mp4 for a clip.
 * Triggers a native browser file download using an authenticated direct download URL.
 * Falls back to Axios blob streaming if needed, with safe delayed URL revocation.
 */
export async function downloadClip(clipId: number): Promise<void> {
  const token = getAccessToken();
  const directUrl = getClipDownloadUrl(clipId);

  // Direct browser download via <a> element triggers the browser's native download manager.
  // This streams the file directly to disk, uses no tab memory, and avoids object URL revocation issues.
  if (token && typeof window !== 'undefined' && typeof document !== 'undefined') {
    const link = document.createElement('a');
    link.href = directUrl;
    link.setAttribute('download', `clip-${clipId}.mp4`);
    document.body.appendChild(link);
    link.click();
    setTimeout(() => {
      link.remove();
    }, 1000);
    return;
  }

  // Fallback: Axios blob streaming
  try {
    const response = await api.get<Blob>(`/clips/${clipId}/download`, {
      responseType: 'blob',
    });

    // Check if the backend sent a JSON error inside a blob response
    if (response.data.type === 'application/json') {
      const text = await response.data.text();
      let errorMsg = 'Failed to download clip';
      try {
        const parsed = JSON.parse(text);
        errorMsg = parsed.detail || errorMsg;
      } catch {
        // use default
      }
      throw new Error(errorMsg);
    }

    const objectUrl = window.URL.createObjectURL(response.data);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = `clip-${clipId}.mp4`;
    document.body.appendChild(link);
    link.click();
    setTimeout(() => {
      link.remove();
      window.URL.revokeObjectURL(objectUrl);
    }, 10000);
  } catch (err: unknown) {
    if (err && typeof err === 'object' && 'response' in err) {
      const axiosErr = err as { response?: { data?: unknown } };
      if (axiosErr.response?.data instanceof Blob) {
        try {
          const text = await axiosErr.response.data.text();
          const parsed = JSON.parse(text);
          if (parsed.detail) {
            throw new Error(parsed.detail);
          }
        } catch (parseErr) {
          if (parseErr instanceof Error && parseErr.message !== 'Failed to download clip') {
            throw parseErr;
          }
        }
      }
    }
    throw err;
  }
}
