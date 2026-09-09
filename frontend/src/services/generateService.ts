import api from '@/services/api';
import type { CaptionStylePreset, Clip, VideoProject } from '@/types';

export interface GenerateRequest {
  title: string;
  description: string;
  shorts_count: number;
  caption_style?: CaptionStylePreset;
  auto_broll?: boolean;
}

export interface GenerateResponse {
  project: VideoProject;
  clips: Clip[];
}

/**
 * Trigger AI generation of shorts from a title + description prompt.
 * Returns HTTP 202 with the created project and initial clip stubs.
 */
export async function generateFromText(
  payload: GenerateRequest,
): Promise<GenerateResponse> {
  const { data } = await api.post<GenerateResponse>('/generate', {
    title: payload.title,
    description: payload.description,
    shorts_count: payload.shorts_count,
    caption_style: payload.caption_style ?? 'hormozi',
    auto_broll: payload.auto_broll ?? true,
  });
  return data;
}

/**
 * Poll a video project until it reaches a terminal status ('ready' or 'failed').
 */
export async function pollVideoProject(
  id: number,
  onUpdate?: (project: VideoProject) => void,
  intervalMs = 3000,
  maxAttempts = 120,
): Promise<VideoProject> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const { data } = await api.get<VideoProject>(`/videos/${id}`);
    if (onUpdate) {
      onUpdate(data);
    }
    if (data.status === 'ready' || data.status === 'failed') {
      return data;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error('Timed out waiting for video generation to complete.');
}
