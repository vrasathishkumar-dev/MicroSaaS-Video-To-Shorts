import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ShortSamplePreview } from '@/components/videos/ShortSamplePreview';

describe('ShortSamplePreview', () => {
  it('renders correctly with default settings', () => {
    render(
      <ShortSamplePreview
        clipLength="auto"
        subtitleStyle="hormozi"
        framingMode="speaker_focus"
        autoBroll={true}
        brollPlacement="bottom"
      />
    );

    expect(screen.getByText('Live 9:16 Short Preview')).toBeInTheDocument();
    expect(screen.getByText('Speaker Focus')).toBeInTheDocument();
    expect(screen.getByText('Hormozi Pop')).toBeInTheDocument();
    expect(screen.getByText('Bottom Third B-Roll')).toBeInTheDocument();
    expect(screen.getByText('Auto (30-50s)')).toBeInTheDocument();
    expect(screen.getByText(/Viral Score/i)).toBeInTheDocument();
  });

  it('renders different framing modes accurately', () => {
    const { rerender } = render(
      <ShortSamplePreview
        clipLength="fast"
        subtitleStyle="neon"
        framingMode="dynamic_blur"
        autoBroll={false}
        brollPlacement="split"
      />
    );

    expect(screen.getByText('Dynamic Blur')).toBeInTheDocument();
    expect(screen.getByText('Neon Cyber')).toBeInTheDocument();
    expect(screen.getByText('B-Roll Disabled')).toBeInTheDocument();
    expect(screen.getByText('Fast (15-30s)')).toBeInTheDocument();

    rerender(
      <ShortSamplePreview
        clipLength="in_depth"
        subtitleStyle="karaoke"
        framingMode="fit"
        autoBroll={true}
        brollPlacement="split"
      />
    );

    expect(screen.getByText('Fit (Letterbox)')).toBeInTheDocument();
    expect(screen.getByText('Karaoke Wave')).toBeInTheDocument();
    expect(screen.getByText('Split Screen (50/50)')).toBeInTheDocument();
    expect(screen.getByText('In-Depth (45-60s)')).toBeInTheDocument();
  });

  it('toggles like button on click', async () => {
    const user = userEvent.setup();
    render(
      <ShortSamplePreview
        clipLength="auto"
        subtitleStyle="hormozi"
        framingMode="speaker_focus"
        autoBroll={true}
        brollPlacement="bottom_right"
      />
    );

    const initialLike = screen.getByText('84.2K');
    expect(initialLike).toBeInTheDocument();

    const likeButton = initialLike.closest('button');
    expect(likeButton).not.toBeNull();
    if (likeButton) {
      await user.click(likeButton);
      expect(screen.getByText('84.2K')).toBeInTheDocument();
    }
  });

  it('cycles hook scripts on button click', async () => {
    const user = userEvent.setup();
    render(
      <ShortSamplePreview
        clipLength="auto"
        subtitleStyle="hormozi"
        framingMode="speaker_focus"
        autoBroll={true}
        brollPlacement="top"
      />
    );

    const cycleButton = screen.getByTitle('Cycle sample viral quote');
    expect(cycleButton).toBeInTheDocument();
    await user.click(cycleButton);
    expect(screen.getByText(/THIS ONE SECRET/i)).toBeInTheDocument();
  });
});
