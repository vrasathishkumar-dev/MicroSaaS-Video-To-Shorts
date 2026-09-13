import api, { API_URL, getAccessToken } from '@/services/api';

/** Shape returned by both the export-trigger and export-status endpoints. */
export interface ExportStatusResponse {
  clip_id: number;
  status: 'idle' | 'rendering' | 'ready' | 'failed';
  video_file_path: string | null;
  /** Server-computed 0-100 virality score, null for unscored legacy clips. */
  virality_score?: number | null;
  /** True when virality_score < 50 — used to show the soft-warning dialog. */
  below_threshold?: boolean;
}

/** Detail object returned inside a 409 score-gate response. */
export interface ScoreGateDetail {
  code: 'score_below_threshold';
  virality_score: number;
  threshold: number;
  message: string;
}

/** Shape of a 409 score-gate error from the export endpoint. */
export interface ScoreGateError {
  isScoreGate: true;
  detail: ScoreGateDetail;
}

function isScoreGateError(err: unknown): err is { response: { status: number; data: { detail: ScoreGateDetail } } } {
  return (
    typeof err === 'object' &&
    err !== null &&
    'response' in err &&
    typeof (err as { response?: unknown }).response === 'object' &&
    (err as { response: { status?: number } }).response.status === 409
  );
}

/**
 * Kick off (or re-kick off, on retry) export rendering for a clip.
 *
 * @param force - When true, bypasses the soft virality score gate and
 *   renders even if the clip scored below the review threshold. The
 *   frontend shows a confirmation dialog on a ScoreGateError and calls
 *   this again with force=true if the user proceeds.
 *
 * @throws ScoreGateError when the clip scores below 50 and force is not set.
 */
export async function triggerExport(
  clipId: number,
  force = false,
): Promise<ExportStatusResponse> {
  try {
    const { data } = await api.post<ExportStatusResponse>(
      `/clips/${clipId}/export${force ? '?force=true' : ''}`,
    );
    return data;
  } catch (err) {
    if (isScoreGateError(err)) {
      // Re-throw as a typed ScoreGateError so ExportPanel can distinguish it.
      const gateErr: ScoreGateError = {
        isScoreGate: true,
        detail: err.response.data.detail,
      };
      throw gateErr;
    }
    throw err;
  }
}

export function isScoreGate(err: unknown): err is ScoreGateError {
  return typeof err === 'object' && err !== null && 'isScoreGate' in err;
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
 * Build an authenticated SSE URL for the clip's render events stream.
 * EventSource cannot send custom headers, so the JWT rides the query string.
 */
export function getClipEventsUrl(clipId: number): string {
  const token = getAccessToken();
  const query = token ? `?token=${encodeURIComponent(token)}` : '';
  return `${API_URL}/api/v1/clips/${clipId}/events${query}`;
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

/** Batch export: enqueue rendering for all draft clips in a video project. */
export interface BatchExportResponse {
  video_project_id: number;
  queued: number;
  already_rendering: number;
  already_ready: number;
}

export async function exportAllClips(videoId: number): Promise<BatchExportResponse> {
  const { data } = await api.post<BatchExportResponse>(
    `/videos/${videoId}/export-all`,
  );
  return data;
}
