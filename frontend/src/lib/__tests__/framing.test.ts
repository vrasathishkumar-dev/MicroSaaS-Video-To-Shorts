import { describe, expect, it } from 'vitest';

import {
  activeSpeakerWindow,
  activeSplitSection,
  speakerFocusStyle,
} from '@/lib/framing';
import type { SpeakerFocusWindow, SplitScreenSection } from '@/types';

const windowAt = (start: number, x: number): SpeakerFocusWindow => ({
  start_time: start,
  x,
  y: 0.25,
  width: 0.2,
  height: 0.63,
});

describe('activeSpeakerWindow', () => {
  it('returns null when the backend found no windows', () => {
    expect(activeSpeakerWindow([], 3)).toBeNull();
  });

  it('holds a window until the next one starts', () => {
    const windows = [windowAt(0, 0.1), windowAt(4, 0.7), windowAt(9, 0.3)];

    expect(activeSpeakerWindow(windows, 3.9)).toBe(windows[0]);
    expect(activeSpeakerWindow(windows, 4)).toBe(windows[1]);
    expect(activeSpeakerWindow(windows, 8.5)).toBe(windows[1]);
    expect(activeSpeakerWindow(windows, 12)).toBe(windows[2]);
  });

  it('uses the first window while the player is still seeking into the clip', () => {
    const windows = [windowAt(0, 0.1), windowAt(4, 0.7)];

    expect(activeSpeakerWindow(windows, -1.2)).toBe(windows[0]);
  });
});

describe('speakerFocusStyle', () => {
  it('scales the video so the window fills the frame and shifts it into place', () => {
    const style = speakerFocusStyle({
      start_time: 0,
      x: 0.5,
      y: 0.25,
      width: 0.2,
      height: 0.5,
    });

    // 1/0.2 of the container wide, slid left by half of the source width,
    // which is 250% of its own new width.
    expect(style).toEqual({
      position: 'absolute',
      width: '500%',
      height: '200%',
      left: '-250%',
      top: '-50%',
      maxWidth: 'none',
    });
  });

  it('declines to style anything without a usable window', () => {
    expect(speakerFocusStyle(null)).toBeUndefined();
    expect(
      speakerFocusStyle({ start_time: 0, x: 0, y: 0, width: 0, height: 0.5 }),
    ).toBeUndefined();
  });
});

describe('activeSplitSection', () => {
  const section = (start: number, end: number): SplitScreenSection => ({
    start_time: start,
    end_time: end,
    panes: [windowAt(start, 0.05), windowAt(start, 0.6)],
  });

  it('finds the stretch covering the playhead', () => {
    const sections = [section(0, 12), section(20, 30)];

    expect(activeSplitSection(sections, 5)).toBe(sections[0]);
    expect(activeSplitSection(sections, 25)).toBe(sections[1]);
  });

  it('returns null between stretches, where one speaker holds the frame', () => {
    const sections = [section(0, 12), section(20, 30)];

    expect(activeSplitSection(sections, 15)).toBeNull();
    expect(activeSplitSection(sections, 40)).toBeNull();
    expect(activeSplitSection([], 5)).toBeNull();
  });

  it('ends a stretch at its end time rather than one frame late', () => {
    const sections = [section(0, 12)];

    expect(activeSplitSection(sections, 11.9)).toBe(sections[0]);
    expect(activeSplitSection(sections, 12)).toBeNull();
  });

  it('gives each pane a style that fills its half of the frame', () => {
    const [top, bottom] = section(0, 12).panes;

    expect(speakerFocusStyle(top)?.height).toBe(speakerFocusStyle(bottom)?.height);
    expect(speakerFocusStyle(top)?.left).not.toBe(speakerFocusStyle(bottom)?.left);
  });
});
