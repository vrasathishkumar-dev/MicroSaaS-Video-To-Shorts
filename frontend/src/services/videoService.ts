import type { AxiosProgressEvent } from 'axios';
import api from '@/services/api';
import type {
  CaptionStylePreset,
  ClipLength,
  FramingMode,
  PaginatedResponse,
  TranscriptSegment,
  VideoProject,
  VideoSourceType,
} from '@/types';

/** Payload accepted by `submitVideo`. Exactly one of `file`/`sourceUrl` is required. */
export interface SubmitVideoPayload {
  title: string;
  sourceType: VideoSourceType;
  file?: File;
  sourceUrl?: string;
  /** The submit form's AI options -- see submitVideo. */
  targetClipLength: ClipLength;
  framingMode: FramingMode;
  captionStyle: CaptionStylePreset;
  autoBroll: boolean;
}

/** Fetch a page of the current user's video projects. */
export async function listVideos(
  page = 1,
): Promise<PaginatedResponse<VideoProject>> {
  const { data } = await api.get<PaginatedResponse<VideoProject>>('/videos', {
    params: { page },
  });
  return data;
}

/** Fetch a single video project by id. */
export async function getVideo(id: number): Promise<VideoProject> {
  const { data } = await api.get<VideoProject>(`/videos/${id}`);
  return data;
}

/**
 * Create a new video project, either from an uploaded file or a source URL.
 * Sent as multipart/form-data; axios sets the boundary automatically as
 * long as we don't set Content-Type ourselves.
 */
export async function submitVideo(
  payload: SubmitVideoPayload,
  onUploadProgress?: (progressEvent: AxiosProgressEvent) => void,
): Promise<VideoProject> {
  const formData = new FormData();
  formData.append('title', payload.title);
  formData.append('source_type', payload.sourceType);

  if (payload.file) {
    formData.append('file', payload.file);
  }
  if (payload.sourceUrl) {
    formData.append('source_url', payload.sourceUrl);
  }
  // What the shorts should come out as. Sent at submission because the
  // length decides how the highlights are cut, and the rest become every
  // generated clip's own settings (still editable per clip afterwards).
  formData.append('target_clip_length', payload.targetClipLength);
  formData.append('framing_mode', payload.framingMode);
  formData.append('caption_style', payload.captionStyle);
  formData.append('auto_broll', String(payload.autoBroll));

  const { data } = await api.post<VideoProject>('/videos', formData, {
    onUploadProgress,
  });
  return data;
}

/** Delete a video project. */
export async function deleteVideo(id: number): Promise<void> {
  await api.delete(`/videos/${id}`);
}

/** Kick off (re)processing of a video project's pipeline. */
export async function reprocessVideo(id: number): Promise<VideoProject> {
  const { data } = await api.post<VideoProject>(`/videos/${id}/process`);
  return data;
}

/** Fetch the transcript segments for a video project. */
export async function getTranscript(
  id: number,
): Promise<TranscriptSegment[]> {
  const { data } = await api.get<TranscriptSegment[]>(
    `/videos/${id}/transcript`,
  );
  return data;
}
