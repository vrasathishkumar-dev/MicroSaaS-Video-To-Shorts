import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { BrollPanel } from '@/components/clips/BrollPanel';
import * as brollService from '@/services/brollService';
import type { BrollAsset } from '@/types';

vi.mock('@/services/brollService');

const mockedGetClipBrollAssets = vi.mocked(brollService.getClipBrollAssets);
const mockedAutoSourceBroll = vi.mocked(brollService.autoSourceBroll);

const assets: BrollAsset[] = [
  {
    id: 1,
    clip_id: 5,
    source: 'pexels',
    source_asset_id: 'abc',
    asset_url: 'https://example.com/a.jpg',
    keyword: 'city skyline',
    position_start: 0,
    position_end: 3,
  },
];

describe('BrollPanel', () => {
  beforeEach(() => {
    mockedGetClipBrollAssets.mockReset();
    mockedAutoSourceBroll.mockReset();
  });

  it('shows a loading state, then the empty state when there is no B-roll', async () => {
    mockedGetClipBrollAssets.mockResolvedValueOnce([]);
    render(<BrollPanel clipId={5} />);

    expect(screen.getByText(/loading b-roll/i)).toBeInTheDocument();
    expect(await screen.findByText(/no b-roll attached yet/i)).toBeInTheDocument();
  });

  it('renders fetched B-roll assets', async () => {
    mockedGetClipBrollAssets.mockResolvedValueOnce(assets);
    render(<BrollPanel clipId={5} />);

    expect(await screen.findByText('city skyline')).toBeInTheDocument();
    expect(screen.getByText('pexels')).toBeInTheDocument();
  });

  it('shows an error message when loading fails', async () => {
    mockedGetClipBrollAssets.mockRejectedValueOnce(new Error('boom'));
    render(<BrollPanel clipId={5} />);

    expect(await screen.findByText(/could not load b-roll/i)).toBeInTheDocument();
  });

  it('auto-sources B-roll and refreshes the list', async () => {
    const user = userEvent.setup();
    mockedGetClipBrollAssets.mockResolvedValueOnce([]).mockResolvedValueOnce(assets);
    mockedAutoSourceBroll.mockResolvedValueOnce(assets);

    render(<BrollPanel clipId={5} />);
    await screen.findByText(/no b-roll attached yet/i);

    await user.click(screen.getByRole('button', { name: /auto-insert b-roll/i }));

    expect(await screen.findByText('city skyline')).toBeInTheDocument();
    expect(mockedAutoSourceBroll).toHaveBeenCalledWith(5);
  });
});
