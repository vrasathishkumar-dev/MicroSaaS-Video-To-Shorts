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
  video_file_path: null,
  thumbnail_path: null,
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

  it('renders the thumbnail image when provided', () => {
    renderClipCard({
      clip: { ...baseClip, thumbnail_path: 'https://example.com/thumb.jpg' },
    });
    expect(screen.getByRole('img', { name: 'Best Moment' })).toHaveAttribute(
      'src',
      'https://example.com/thumb.jpg',
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
});
