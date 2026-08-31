import { describe, expect, it } from 'vitest';

import { CAPTION_PREVIEW_STYLES, activeCaptionFrame } from '@/lib/captions';
import type { CaptionFrame } from '@/types';

const frame = (
  start: number,
  end: number,
  text: string,
  activeWord: number | null = null,
): CaptionFrame => ({
  start_time: start,
  end_time: end,
  text,
  active_word: activeWord,
});

describe('activeCaptionFrame', () => {
  const events = [
    frame(0, 1.2, 'Nobody tells you', 0),
    frame(1.2, 2.4, 'Nobody tells you', 1),
    frame(4, 6, 'how simple this is'),
  ];

  it('picks the caption on screen at the playhead', () => {
    expect(activeCaptionFrame(events, 0.5)).toBe(events[0]);
    expect(activeCaptionFrame(events, 1.2)).toBe(events[1]);
    expect(activeCaptionFrame(events, 5.9)).toBe(events[2]);
  });

  it('shows nothing in the gaps between captions', () => {
    expect(activeCaptionFrame(events, 3)).toBeNull();
    expect(activeCaptionFrame(events, 9)).toBeNull();
    expect(activeCaptionFrame([], 1)).toBeNull();
  });

  it('advances the highlighted word within one caption', () => {
    expect(activeCaptionFrame(events, 0.5)?.active_word).toBe(0);
    expect(activeCaptionFrame(events, 1.5)?.active_word).toBe(1);
  });
});

describe('CAPTION_PREVIEW_STYLES', () => {
  it('covers every preset the picker offers', () => {
    expect(Object.keys(CAPTION_PREVIEW_STYLES).sort()).toEqual([
      'bold_box',
      'hormozi',
      'karaoke',
      'minimal',
      'neon',
    ]);
  });

  it('gives the word-highlighting presets a colour to highlight with', () => {
    expect(CAPTION_PREVIEW_STYLES.hormozi.activeWord).not.toBe('');
    expect(CAPTION_PREVIEW_STYLES.neon.activeWord).not.toBe('');
    expect(CAPTION_PREVIEW_STYLES.karaoke.activeWord).not.toBe('');
  });
});
