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

/** How long the shorts cut from a video should aim to be. */
export type ClipLength = 'auto' | 'fast' | 'in_depth';

export interface VideoProject {
  id: number;
  title: string;
  source_type: VideoSourceType;
  source_url: string | null;
  status: VideoProjectStatus;
  duration_seconds: number | null;
  error_message: string | null;
  /**
   * What the submitter asked for. The length shapes how highlights are cut;
   * framing, captions and B-roll become every generated clip's own settings.
   */
  target_clip_length: ClipLength;
  framing_mode: FramingMode;
  caption_style: CaptionStylePreset;
  auto_broll: boolean;
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
  /** How the export fills the 9:16 canvas -- the editor's framing toggle. */
  framing_mode: FramingMode;
  video_file_path: string | null;
  thumbnail_path: string | null;
  broll_assets?: BrollAsset[];
  virality_score?: number;
  virality_reason?: string;
  hook_score?: number;
  engagement_score?: number;
  /** Which caption look burns into the export. */
  caption_style: CaptionStylePreset;
  created_at: string;
  updated_at: string;
}

/**
 * One caption exactly as the renderer will draw it, timed from the clip's
 * own start. `active_word` is the index of the word lit up during this
 * frame, for the presets that highlight word by word.
 */
export interface CaptionFrame {
  start_time: number;
  end_time: number;
  text: string;
  active_word: number | null;
}

/** The caption timeline a clip will be exported with. */
export interface ClipCaptions {
  clip_id: number;
  style: CaptionStylePreset;
  events: CaptionFrame[];
}

/**
 * One Speaker Focus crop window, as fractions (0-1) of the source frame.
 *
 * `at_cut` mirrors the renderer: snap into place (the source cut here too)
 * or ease across (the crop moved mid-shot, following the conversation).
 */
export interface SpeakerFocusWindow {
  start_time: number;
  x: number;
  y: number;
  width: number;
  height: number;
  at_cut: boolean;
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

/** How a clip fills the 9:16 canvas. Mirrors the backend's ClipFraming. */
export type FramingMode = 'speaker_focus' | 'dynamic_blur' | 'fit';

/**
 * Caption looks the renderer can actually burn in. Mirrors the backend's
 * ClipCaptionStyle -- a preset listed here that the renderer doesn't know
 * would export as something the user never picked.
 */
export type CaptionStylePreset =
  | 'hormozi'
  | 'neon'
  | 'minimal'
  | 'karaoke'
  | 'bold_box';

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
