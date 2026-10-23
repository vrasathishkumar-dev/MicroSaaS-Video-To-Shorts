import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ExportPanel } from '@/components/clips/ExportPanel';
import * as exportService from '@/services/exportService';

vi.mock('@/services/exportService');

const mockedGetExportStatus = vi.mocked(exportService.getExportStatus);
const mockedTriggerExport = vi.mocked(exportService.triggerExport);
const mockedDownloadClip = vi.mocked(exportService.downloadClip);

describe('ExportPanel', () => {
  beforeEach(() => {
    mockedGetExportStatus.mockReset();
    mockedTriggerExport.mockReset();
    mockedDownloadClip.mockReset();
  });

  it('shows the export button once no prior export is found', async () => {
    mockedGetExportStatus.mockRejectedValueOnce(new Error('no export yet'));
    render(<ExportPanel clipId={1} />);

    expect(
      await screen.findByRole('button', { name: /export \(9:16\)/i }),
    ).toBeInTheDocument();
  });

  it('shows a download button when the export is already ready', async () => {
    mockedGetExportStatus.mockResolvedValueOnce({
      clip_id: 1,
      status: 'ready',
      video_file_path: '/files/1.mp4',
    });
    render(<ExportPanel clipId={1} />);

    expect(await screen.findByRole('button', { name: /download/i })).toBeInTheDocument();
  });

  it('starts an export and shows the rendering state', async () => {
    const user = userEvent.setup();
    mockedGetExportStatus.mockRejectedValueOnce(new Error('no export yet'));
    mockedTriggerExport.mockResolvedValueOnce({
      clip_id: 1,
      status: 'rendering',
      video_file_path: null,
    });

    render(<ExportPanel clipId={1} />);
    const exportButton = await screen.findByRole('button', { name: /export \(9:16\)/i });
    await user.click(exportButton);

    expect(await screen.findByText(/rendering your 9:16 clip/i)).toBeInTheDocument();
    expect(mockedTriggerExport).toHaveBeenCalledWith(1);
  });

  it('calls downloadClip when the download button is clicked', async () => {
    const user = userEvent.setup();
    mockedGetExportStatus.mockResolvedValueOnce({
      clip_id: 1,
      status: 'ready',
      video_file_path: '/files/1.mp4',
    });
    mockedDownloadClip.mockResolvedValueOnce(undefined);

    render(<ExportPanel clipId={1} />);
    const downloadButton = await screen.findByRole('button', { name: /download/i });
    await user.click(downloadButton);

    await waitFor(() => expect(mockedDownloadClip).toHaveBeenCalledWith(1));
  });

  it('shows a failed state with a retry button when the export errors', async () => {
    const user = userEvent.setup();
    mockedGetExportStatus.mockRejectedValueOnce(new Error('no export yet'));
    mockedTriggerExport.mockRejectedValueOnce(new Error('start failed'));

    render(<ExportPanel clipId={1} />);
    const exportButton = await screen.findByRole('button', { name: /export \(9:16\)/i });
    await user.click(exportButton);

    expect(await screen.findByText(/failed to start export/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry export/i })).toBeInTheDocument();
  });

  it('shows the score gate confirmation dialog when virality score is below 50', async () => {
    const user = userEvent.setup();
    mockedGetExportStatus.mockRejectedValueOnce(new Error('no export yet'));

    render(<ExportPanel clipId={1} viralityScore={42} />);
    const exportButton = await screen.findByRole('button', { name: /export \(9:16\)/i });
    await user.click(exportButton);

    expect(await screen.findByText(/viral content gate: low virality score/i)).toBeInTheDocument();
    expect(screen.getByText(/42\/100/i)).toBeInTheDocument();
    expect(mockedTriggerExport).not.toHaveBeenCalled();

    // User can click "Render anyway" to force export
    mockedTriggerExport.mockResolvedValueOnce({
      clip_id: 1,
      status: 'rendering',
      video_file_path: null,
    });

    const renderAnywayButton = screen.getByRole('button', { name: /render anyway/i });
    await user.click(renderAnywayButton);

    expect(mockedTriggerExport).toHaveBeenCalledWith(1, true);
  });

  it('passes copyrightSafe=true when the Copyright-Safe Fair-Use Mode toggle is enabled', async () => {
    const user = userEvent.setup();
    mockedGetExportStatus.mockRejectedValueOnce(new Error('no export yet'));
    mockedTriggerExport.mockResolvedValueOnce({
      clip_id: 1,
      status: 'rendering',
      video_file_path: null,
      copyright_safe: true,
    });

    render(<ExportPanel clipId={1} />);
    const toggle = await screen.findByRole('checkbox', {
      name: /copyright-safe fair-use mode/i,
    });
    await user.click(toggle);

    const exportButton = screen.getByRole('button', { name: /export \(9:16\)/i });
    await user.click(exportButton);

    expect(mockedTriggerExport).toHaveBeenCalledWith(1, false, true);
  });
});
