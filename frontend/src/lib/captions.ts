/**
 * Caption preview.
 *
 * The renderer builds its own caption timeline from the transcript (or the
 * user's own caption text) and burns it in — see
 * backend/app/services/video_render.py. The editor asks for that same
 * timeline rather than rebuilding it, so the preview shows the words the
 * export will show, at the moments it will show them, down to which word
 * is lit up.
 */
import type { CaptionFrame, CaptionStylePreset } from '@/types';

/** The caption on screen at `timeIntoClip` seconds, if any. */
export function activeCaptionFrame(
  events: CaptionFrame[],
  timeIntoClip: number,
): CaptionFrame | null {
  return (
    events.find(
      (event) =>
        timeIntoClip >= event.start_time && timeIntoClip < event.end_time,
    ) ?? null
  );
}

export interface CaptionPreviewStyle {
  /** Classes for the caption block. */
  block: string;
  /** Classes for the word being spoken, where the preset highlights one. */
  activeWord: string;
}

/**
 * How each preset looks, as close as Tailwind gets to the burned-in
 * version (Pillow draws the real thing: panels, glow, stroke and all).
 */
export const CAPTION_PREVIEW_STYLES: Record<
  CaptionStylePreset,
  CaptionPreviewStyle
> = {
  hormozi: {
    block:
      'bg-[#08080a]/95 text-[#ffe600] font-black uppercase tracking-wide border-2 border-[#a3e635]',
    activeWord: 'text-[#a3e635]',
  },
  neon: {
    block:
      'bg-[#06141e]/90 text-[#22d3ee] font-extrabold uppercase tracking-wide border border-[#22d3ee] shadow-[0_0_14px_rgba(34,211,238,0.7)]',
    activeWord: 'text-[#e879f9]',
  },
  bold_box: {
    block: 'bg-[#0a0a0c]/85 text-white font-bold',
    activeWord: '',
  },
  karaoke: {
    block:
      'bg-[#06080a]/75 text-[#e2fff0] font-extrabold uppercase border-b-2 border-[#34d399]',
    activeWord: 'text-[#34d399]',
  },
  minimal: {
    block: 'text-white font-semibold drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)]',
    activeWord: '',
  },
};
