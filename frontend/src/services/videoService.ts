import type { AxiosProgressEvent } from 'axios';
import api from '@/services/api';
import type {
  BrollPlacement,
  CaptionStylePreset,
  Clip,
  ClipLength,
  FramingMode,
  PaginatedResponse,
  TranscriptSegment,
  UploadShortResponse,
  VideoProject,
  VideoSourceType,
  YouTubeCaptionTone,
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
  brollPlacement?: BrollPlacement;
  /** When true, automatically generates clips, adds B-roll, and renders 9:16 MP4s. */
  autoProduce?: boolean;
}

export interface UploadShortPayload {
  file: File;
  title?: string;
  captionText?: string;
  tone?: YouTubeCaptionTone;
  framingMode?: FramingMode;
  captionStyle?: CaptionStylePreset;
  autoBroll?: boolean;
  brollPlacement?: BrollPlacement;
  autoRender?: boolean;
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
  formData.append('target_clip_length', payload.targetClipLength);
  formData.append('framing_mode', payload.framingMode);
  formData.append('caption_style', payload.captionStyle);
  formData.append('auto_broll', String(payload.autoBroll));
  if (payload.brollPlacement) {
    formData.append('broll_placement', payload.brollPlacement);
  }
  if (payload.autoProduce !== undefined) {
    formData.append('auto_produce', String(payload.autoProduce));
  }

  const { data } = await api.post<VideoProject>('/videos', formData, {
    onUploadProgress,
  });
  return data;
}

/**
 * Upload an existing Short video directly to extract/generate YouTube captions,
 * see the spoken & timed subtitle content, and prepare a 9:16 export.
 */
export async function uploadShortVideo(
  payload: UploadShortPayload,
  onUploadProgress?: (progressEvent: AxiosProgressEvent) => void,
): Promise<UploadShortResponse> {
  const formData = new FormData();
  formData.append('file', payload.file);
  if (payload.title) {
    formData.append('title', payload.title);
  }
  if (payload.captionText) {
    formData.append('caption_text', payload.captionText);
  }
  formData.append('tone', payload.tone ?? 'viral');
  formData.append('framing_mode', payload.framingMode ?? 'speaker_focus');
  formData.append('caption_style', payload.captionStyle ?? 'hormozi');
  formData.append('auto_broll', String(payload.autoBroll ?? false));
  formData.append('broll_placement', payload.brollPlacement ?? 'bottom');
  formData.append('auto_render', String(payload.autoRender ?? true));

  const { data } = await api.post<UploadShortResponse>(
    '/videos/upload-short',
    formData,
    { onUploadProgress },
  );
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

/** Produce all viral shorts (generate clips + auto B-roll + 9:16 render) for a project. */
export async function produceVideo(id: number): Promise<Clip[]> {
  const { data } = await api.post<Clip[]>(`/videos/${id}/produce`);
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
