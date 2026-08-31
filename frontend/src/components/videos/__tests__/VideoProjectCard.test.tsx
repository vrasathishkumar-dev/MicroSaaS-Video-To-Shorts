import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { VideoProjectCard } from '@/components/videos/VideoProjectCard';
import type { VideoProject } from '@/types';

const baseVideo: VideoProject = {
  id: 1,
  title: 'My Great Video',
  source_type: 'upload',
  source_url: null,
  status: 'ready',
  duration_seconds: 125,
  error_message: null,
  target_clip_length: 'auto',
  framing_mode: 'speaker_focus',
  caption_style: 'hormozi',
  auto_broll: true,
  created_at: '2024-01-15T00:00:00Z',
  updated_at: '2024-01-15T00:00:00Z',
};

interface RenderOverrides {
  video?: VideoProject;
  onDelete?: (id: number) => void;
  isDeleting?: boolean;
}

function renderCard({ video = baseVideo, onDelete, isDeleting }: RenderOverrides = {}) {
  return render(
    <MemoryRouter>
      <VideoProjectCard video={video} onDelete={onDelete} isDeleting={isDeleting} />
    </MemoryRouter>,
  );
}

describe('VideoProjectCard', () => {
  it('renders title, status, and formatted duration', () => {
    renderCard();
    expect(screen.getByText('My Great Video')).toBeInTheDocument();
    expect(screen.getByText('Ready')).toBeInTheDocument();
    expect(screen.getByText('2:05')).toBeInTheDocument();
  });

  it('shows a placeholder duration when duration is null', () => {
    renderCard({ video: { ...baseVideo, duration_seconds: null } });
    expect(screen.getByText('--:--')).toBeInTheDocument();
  });

  it('shows the error message for failed videos', () => {
    renderCard({
      video: { ...baseVideo, status: 'failed', error_message: 'Download failed' },
    });
    expect(screen.getByText('Download failed')).toBeInTheDocument();
  });

  it('does not show an error message for non-failed videos even if one is set', () => {
    renderCard({ video: { ...baseVideo, status: 'ready', error_message: 'stale error' } });
    expect(screen.queryByText('stale error')).not.toBeInTheDocument();
  });

  it('calls onDelete with the video id when the delete button is clicked', async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    renderCard({ onDelete });

    await user.click(screen.getByRole('button', { name: /delete my great video/i }));
    expect(onDelete).toHaveBeenCalledWith(1);
  });

  it('does not render a delete button when onDelete is not provided', () => {
    renderCard();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('disables the delete button while isDeleting is true', () => {
    renderCard({ onDelete: vi.fn(), isDeleting: true });
    expect(screen.getByRole('button', { name: /delete my great video/i })).toBeDisabled();
  });
});
