import api from '@/services/api';

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
 * Download the rendered mp4 for a clip. Streams the response as a blob and
 * triggers a browser save via a temporary object URL + <a> click, since the
 * shared Axios client can't hand the browser a direct file URL (auth header
 * required).
 */
export async function downloadClip(clipId: number): Promise<void> {
  const response = await api.get<Blob>(`/clips/${clipId}/download`, {
    responseType: 'blob',
  });

  const objectUrl = window.URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = `clip-${clipId}.mp4`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}
