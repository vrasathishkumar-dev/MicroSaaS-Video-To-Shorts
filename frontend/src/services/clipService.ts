import api, { API_URL, getAccessToken } from '@/services/api';
import type { Clip, PaginatedResponse } from '@/types';

export interface UpdateClipPayload {
  title?: string;
  start_time?: number;
  end_time?: number;
  caption_text?: string;
}

/**
 * List clips, optionally scoped to a single video project.
 */
export async function listClips(
  videoProjectId?: number,
  page = 1,
): Promise<PaginatedResponse<Clip>> {
  const { data } = await api.get<PaginatedResponse<Clip>>('/clips', {
    params: {
      video_project_id: videoProjectId,
      page,
    },
  });
  return data;
}

export async function getClip(id: number): Promise<Clip> {
  const { data } = await api.get<Clip>(`/clips/${id}`);
  return data;
}

/**
 * URL for inline `<video>` preview playback of a clip. Serves the rendered
 * export once ready, or the original source video otherwise (the caller is
 * responsible for seeking to [start_time, end_time] for a draft clip).
 * Uses a `?token=` query param since <video> elements can't send an
 * Authorization header.
 */
export function getClipPreviewUrl(clipId: number): string {
  const token = getAccessToken();
  const query = token ? `?token=${encodeURIComponent(token)}` : '';
  return `${API_URL}/api/v1/clips/${clipId}/preview${query}`;
}

/**
 * Kick off clip generation for a video project. Returns the newly
 * created clips.
 */
export async function generateClips(videoProjectId: number): Promise<Clip[]> {
  const { data } = await api.post<Clip[]>('/clips/generate', {
    video_project_id: videoProjectId,
  });
  return data;
}

export async function updateClip(
  id: number,
  data: UpdateClipPayload,
): Promise<Clip> {
  const { data: clip } = await api.put<Clip>(`/clips/${id}`, data);
  return clip;
}

export async function reorderClip(id: number, orderIndex: number): Promise<Clip> {
  const { data } = await api.patch<Clip>(`/clips/${id}/reorder`, {
    order_index: orderIndex,
  });
  return data;
}

export async function deleteClip(id: number): Promise<void> {
  await api.delete(`/clips/${id}`);
}
