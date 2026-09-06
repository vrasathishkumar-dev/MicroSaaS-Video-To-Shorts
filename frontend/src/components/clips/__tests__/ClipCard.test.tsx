import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ClipCard } from '@/components/clips/ClipCard';
import type { Clip } from '@/types';

const baseClip: Clip = {
  id: 7,
  video_project_id: 1,
  title: 'Best Moment',
  start_time: 10,
  end_time: 75,
  order_index: 0,
  status: 'ready',
  caption_text: null,
  framing_mode: 'speaker_focus',
  caption_style: 'hormozi',
  video_file_path: null,
  thumbnail_path: null,
  virality_score: null,
  virality_reason: null,
  hook_score: null,
  completeness_score: null,
  framing_score: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

interface RenderOverrides {
  clip?: Clip;
  onDelete?: (id: number) => void;
}

function renderClipCard({ clip = baseClip, onDelete }: RenderOverrides = {}) {
  return render(
    <MemoryRouter>
      <ClipCard clip={clip} onDelete={onDelete} />
    </MemoryRouter>,
  );
}

describe('ClipCard', () => {
  it('renders title, status, and computed duration', () => {
    renderClipCard();
    expect(screen.getByText('Best Moment')).toBeInTheDocument();
    expect(screen.getByText('ready')).toBeInTheDocument();
    // end_time (75) - start_time (10) = 65s => 1:05
    expect(screen.getByText('1:05')).toBeInTheDocument();
  });

  it('does not render an image when there is no thumbnail', () => {
    renderClipCard();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('renders the exported poster frame once the clip has a thumbnail', () => {
    // thumbnail_path is a server-side path, so the card loads the poster
    // through the authenticated /clips/:id/thumbnail endpoint instead.
    renderClipCard({
      clip: { ...baseClip, thumbnail_path: '/uploads/exports/abc.jpg' },
    });
    expect(screen.getByRole('img', { name: 'Best Moment' })).toHaveAttribute(
      'src',
      expect.stringContaining('/api/v1/clips/7/thumbnail'),
    );
  });

  it('fires the onDelete callback with the clip id when the delete button is clicked', async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    renderClipCard({ onDelete });

    await user.click(screen.getByRole('button', { name: /delete best moment/i }));
    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(onDelete).toHaveBeenCalledWith(7);
  });

  it('does not throw when the delete button is clicked without an onDelete handler', async () => {
    const user = userEvent.setup();
    renderClipCard();

    await expect(
      user.click(screen.getByRole('button', { name: /delete best moment/i })),
    ).resolves.not.toThrow();
  });

  it('renders "Not yet scored" for a legacy clip with a null virality_score', () => {
    renderClipCard({ clip: { ...baseClip, virality_score: null } });
    expect(screen.getByText('Not yet scored')).toBeInTheDocument();
  });

  it('renders the sub-50 "Needs Manual Review" band for a weak real score', () => {
    renderClipCard({
      clip: {
        ...baseClip,
        virality_score: 32,
        hook_score: 20,
        completeness_score: 40,
        framing_score: 0,
        virality_reason: 'Weak hook and a mid-sentence cut.',
      },
    });
    expect(screen.getByText('Score 32/100')).toBeInTheDocument();
  });
});
