/**
 * Speaker Focus framing math.
 *
 * The backend analyses the source footage and returns the crop windows the
 * renderer will use (see backend/app/services/reframe.py), normalised to
 * 0-1 of the source frame. The preview scales the <video> up so that one
 * window exactly fills the 9:16 phone frame, and shifts it so the speaker
 * lands inside it -- the same picture the export produces, without waiting
 * for a render.
 */
import type { CSSProperties } from 'react';
import type { SpeakerFocusWindow, SplitScreenSection } from '@/types';

/**
 * The window in force at `timeIntoClip` seconds.
 *
 * Windows step at the source's own cuts, so the one that applies is the
 * last one that has started. Before the first window (a negative time
 * while the player is still seeking into the clip) the first window holds.
 */
export function activeSpeakerWindow(
  windows: SpeakerFocusWindow[],
  timeIntoClip: number,
): SpeakerFocusWindow | null {
  if (windows.length === 0) return null;

  let active = windows[0];
  for (const window of windows) {
    if (window.start_time > timeIntoClip) break;
    active = window;
  }
  return active;
}

/** How long the crop takes to travel when it moves mid-shot. */
export const PAN_MS = 500;

/**
 * Smoothstep, as near as a CSS curve gets: the crop accelerates away and
 * settles instead of sliding at a constant rate and stopping dead. Matches
 * the `p * p * (3 - 2p)` ramp the renderer burns into the export.
 */
const PAN_EASING = 'cubic-bezier(0.33, 0, 0.67, 1)';

/**
 * Sizing/offset for the preview <video> so `window` fills its container.
 *
 * The window carries the target's 9:16 aspect, so blowing the video up by
 * 1/width and sliding it left by x of its own new width crops to exactly
 * that region with no distortion. Returns undefined when there is nothing
 * to apply, so the caller can fall back to its default framing.
 *
 * A window that lands on a cut snaps; one that moves mid-shot eases, so
 * the preview travels the way the export will. Animating through a cut
 * would slide the crop over footage that has already changed.
 */
export function speakerFocusStyle(
  window: SpeakerFocusWindow | null,
): CSSProperties | undefined {
  if (!window || window.width <= 0 || window.height <= 0) return undefined;

  return {
    position: 'absolute',
    width: `${100 / window.width}%`,
    height: `${100 / window.height}%`,
    left: `${(-window.x * 100) / window.width}%`,
    top: `${(-window.y * 100) / window.height}%`,
    maxWidth: 'none',
    transitionProperty: 'left, top, width, height',
    transitionDuration: window.at_cut ? '0ms' : `${PAN_MS}ms`,
    transitionTimingFunction: PAN_EASING,
  };
}

/**
 * The split-screen section covering `timeIntoClip`, if there is one.
 *
 * Sections come from the same analysis the renderer uses, so a preview
 * that stacks these panes shows what the export will cut to: everyone in
 * the conversation on screen at once, instead of one of them chosen and
 * the other dropped.
 */
export function activeSplitSection(
  sections: SplitScreenSection[],
  timeIntoClip: number,
): SplitScreenSection | null {
  return (
    sections.find(
      (section) =>
        timeIntoClip >= section.start_time && timeIntoClip < section.end_time,
    ) ?? null
  );
}
