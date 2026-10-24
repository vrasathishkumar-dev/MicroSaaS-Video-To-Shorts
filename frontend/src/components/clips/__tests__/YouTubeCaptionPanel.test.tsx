import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { YouTubeCaptionPanel } from '@/components/clips/YouTubeCaptionPanel';
import * as exportService from '@/services/exportService';
import type { YouTubeCaptionPackage } from '@/types';

vi.mock('@/services/exportService');

const mockedGetPackage = vi.mocked(exportService.getYouTubeCaptionPackage);
const mockedGeneratePackage = vi.mocked(exportService.generateYouTubeCaptionPackage);

const MOCK_PACKAGE: YouTubeCaptionPackage = {
  clip_id: 7,
  tone: 'viral',
  youtube_title: 'Why 90% of Creators Miss This Hook 🔥 #Shorts',
  youtube_description:
    'Why 90% of creators miss this simple hook.\n\n📌 Key Highlights:\n• Visual hook in 2s\n\n#Shorts #YouTubeShorts',
  hashtags: ['#Shorts', '#YouTubeShorts', '#ViralShorts', '#Creators'],
  tags: ['shorts', 'youtube shorts', 'creators'],
  caption_text: 'Why 90% of creators miss this simple hook in the first two seconds.',
  timed_captions: [
    {
      start_time: 0,
      end_time: 4.5,
      timestamp_label: '0:00 - 0:05',
      text: 'Why 90% of creators miss this',
    },
    {
      start_time: 4.5,
      end_time: 9.0,
      timestamp_label: '0:05 - 0:09',
      text: 'simple hook in the first two seconds.',
    },
  ],
  srt_content:
    '1\n00:00:00,000 --> 00:00:04,500\nWhy 90% of creators miss this\n',
  specs_check: {
    is_youtube_short_ready: true,
    aspect_ratio: '9:16 (Vertical)',
    resolution: '1080x1920 HD',
    fps: 30,
    duration_seconds: 9.0,
    max_duration_seconds: 60.0,
    video_codec: 'H.264 (High@L4.2, yuv420p, BT.709)',
    audio_codec: 'AAC-LC Stereo 48kHz (-14 LUFS)',
    has_burned_captions: true,
    caption_style: 'hormozi',
    framing_mode: 'speaker_focus',
    broll_count: 1,
    status: 'ready',
  },
};

describe('YouTubeCaptionPanel', () => {
  beforeEach(() => {
    mockedGetPackage.mockReset();
    mockedGeneratePackage.mockReset();
  });

  it('loads and displays the YouTube title, description, hashtags, and readiness badge', async () => {
    mockedGetPackage.mockResolvedValueOnce(MOCK_PACKAGE);

    render(<YouTubeCaptionPanel clipId={7} />);

    expect(
      await screen.findByDisplayValue(/Why 90% of Creators Miss This Hook/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/YouTube Shorts Ready/i)).toBeInTheDocument();
    expect(screen.getByText('#Creators')).toBeInTheDocument();
  });

  it('switches to See Content & Subtitles tab and shows timed subtitle cues', async () => {
    const user = userEvent.setup();
    mockedGetPackage.mockResolvedValueOnce(MOCK_PACKAGE);

    render(<YouTubeCaptionPanel clipId={7} />);
    await screen.findByDisplayValue(/Why 90% of Creators Miss This Hook/i);

    const contentTab = screen.getByRole('button', {
      name: /see content & subtitles/i,
    });
    await user.click(contentTab);

    expect(screen.getByText('0:00 - 0:05')).toBeInTheDocument();
    expect(
      screen.getByText('simple hook in the first two seconds.'),
    ).toBeInTheDocument();
  });

  it('regenerates the YouTube caption package when a new tone is clicked', async () => {
    const user = userEvent.setup();
    mockedGetPackage.mockResolvedValueOnce(MOCK_PACKAGE);
    mockedGeneratePackage.mockResolvedValueOnce({
      ...MOCK_PACKAGE,
      tone: 'educational',
      youtube_title: 'Why This Matters: Creator Hooks #Shorts',
    });

    render(<YouTubeCaptionPanel clipId={7} />);
    await screen.findByDisplayValue(/Why 90% of Creators Miss This Hook/i);

    const eduButton = screen.getByRole('button', { name: /educational/i });
    await user.click(eduButton);

    await waitFor(() =>
      expect(mockedGeneratePackage).toHaveBeenCalledWith(
        7,
        expect.objectContaining({ tone: 'educational' }),
      ),
    );
    expect(
      await screen.findByDisplayValue('Why This Matters: Creator Hooks #Shorts'),
    ).toBeInTheDocument();
  });
});
