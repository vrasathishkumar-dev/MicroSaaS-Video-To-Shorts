/**
 * Shared TypeScript interfaces mirroring the backend SQLAlchemy models.
 * Keep these in sync with backend/app/models and backend/app/schemas.
 *
 * Timestamps are ISO 8601 date strings (as returned by FastAPI/Pydantic).
 */

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  is_admin: boolean;
}

export type VideoSourceType = 'upload' | 'url';

export type VideoProjectStatus =
  | 'pending'
  | 'downloading'
  | 'transcribing'
  | 'analyzing'
  | 'ready'
  | 'failed';

export interface VideoProject {
  id: number;
  title: string;
  source_type: VideoSourceType;
  source_url: string | null;
  status: VideoProjectStatus;
  duration_seconds: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface TranscriptSegment {
  id: number;
  video_project_id: number;
  start_time: number;
  end_time: number;
  text: string;
  is_highlight: boolean;
  highlight_score: number | null;
}

export type ClipStatus = 'draft' | 'rendering' | 'ready' | 'failed';

export interface Clip {
  id: number;
  video_project_id: number;
  title: string;
  start_time: number;
  end_time: number;
  order_index: number;
  status: ClipStatus;
  caption_text: string | null;
  video_file_path: string | null;
  thumbnail_path: string | null;
  broll_assets?: BrollAsset[];
  virality_score?: number;
  virality_reason?: string;
  hook_score?: number;
  engagement_score?: number;
  caption_style?: CaptionStylePreset;
  created_at: string;
  updated_at: string;
}

/** One Speaker Focus crop window, as fractions (0-1) of the source frame. */
export interface SpeakerFocusWindow {
  start_time: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * A stretch of the clip shown as stacked panes, one per speaker, with each
 * pane filling the width and `1 / panes.length` of the height.
 */
export interface SplitScreenSection {
  start_time: number;
  end_time: number;
  panes: SpeakerFocusWindow[];
}

/**
 * Where the speaker is in a clip's source footage.
 *
 * `speaker_focus` means crop the preview to `windows`; `rendered` means the
 * clip has already been exported to 9:16 and needs no further cropping;
 * `unavailable` means no confident subject was found, and both preview and
 * export fall back to blurred-fill framing.
 *
 * `split_sections` covers the stretches where more than one person is in
 * the conversation: those play as stacked panes instead of `windows`.
 */
export interface ClipFraming {
  clip_id: number;
  mode: 'speaker_focus' | 'rendered' | 'unavailable';
  windows: SpeakerFocusWindow[];
  split_sections: SplitScreenSection[];
}

export type CaptionStylePreset =
  | 'hormozi'
  | 'neon'
  | 'minimal'
  | 'karaoke'
  | 'bold_box'
  | 'cyberpunk';

export type BrollSource = 'pexels' | 'pixabay';

export interface BrollAsset {
  id: number;
  clip_id: number;
  source: BrollSource;
  source_asset_id: string;
  asset_url: string;
  keyword: string;
  position_start: number;
  position_end: number;
}

/** Generic paginated API response envelope. */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/** Standard error payload returned by the FastAPI backend. */
export interface ApiError {
  detail: string;
}

/** Auth token pair returned by /auth/login and /auth/refresh. */
export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
