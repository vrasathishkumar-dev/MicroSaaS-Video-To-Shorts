import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle, Download, Loader2 } from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import {
  downloadClip,
  getExportStatus,
  triggerExport,
  type ExportStatusResponse,
} from '@/services/exportService';

const POLL_INTERVAL_MS = 3000;

type ExportState = 'idle' | 'rendering' | 'ready' | 'failed';

/**
 * Self-contained export widget for a single clip. Fetches its own status on
 * mount, drives export + polling, and offers download/retry. Designed to be
 * dropped into any parent layout as `<ExportPanel clipId={clip.id} />`.
 */
export function ExportPanel({ clipId }: { clipId: number }) {
  const [status, setStatus] = useState<ExportState>('idle');
  const [isCheckingStatus, setIsCheckingStatus] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearPolling = useCallback(() => {
    if (pollIntervalRef.current !== null) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  const applyStatus = useCallback(
    (data: ExportStatusResponse) => {
      setStatus(data.status);
      if (data.status === 'ready' || data.status === 'failed') {
        clearPolling();
      }
    },
    [clearPolling],
  );

  const startPolling = useCallback(() => {
    clearPolling();
    pollIntervalRef.current = setInterval(() => {
      getExportStatus(clipId)
        .then(applyStatus)
        .catch(() => {
          clearPolling();
          setStatus('failed');
          setErrorMessage('Lost connection while checking export status.');
        });
    }, POLL_INTERVAL_MS);
  }, [applyStatus, clearPolling, clipId]);

  useEffect(() => {
    let isMounted = true;

    getExportStatus(clipId)
      .then((data) => {
        if (!isMounted) return;
        applyStatus(data);
        if (data.status === 'rendering') {
          startPolling();
        }
      })
      .catch(() => {
        // No export has been triggered yet (or the check failed) — default
        // to idle so the user can start one.
        if (isMounted) setStatus('idle');
      })
      .finally(() => {
        if (isMounted) setIsCheckingStatus(false);
      });

    return () => {
      isMounted = false;
      clearPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clipId]);

  const handleExport = async () => {
    setErrorMessage(null);
    setIsStarting(true);
    try {
      const data = await triggerExport(clipId);
      applyStatus(data);
      if (data.status === 'rendering' || data.status === 'idle') {
        setStatus('rendering');
        startPolling();
      }
    } catch {
      setStatus('failed');
      setErrorMessage('Failed to start export. Please try again.');
    } finally {
      setIsStarting(false);
    }
  };

  const handleDownload = async () => {
    setErrorMessage(null);
    setIsDownloading(true);
    try {
      await downloadClip(clipId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to download the clip. Please try again.';
      setErrorMessage(msg);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <GlassCard className="space-y-5">
      <div className="flex items-center justify-between border-b border-glass-border pb-3">
        <div>
          <h3 className="text-base font-bold text-foreground">9:16 Video Export & Download</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Render vertical Short with burned-in animated subtitles and B-roll.
          </p>
        </div>
        <span className="rounded-full bg-primary/10 px-2.5 py-1 text-[11px] font-semibold text-primary">
          1080 &times; 1920 HD
        </span>
      </div>

      {/* Export Specifications Box */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 rounded-xl bg-background/50 border border-glass-border p-3 text-xs">
        <div>
          <span className="text-muted-foreground block text-[10px]">Aspect Ratio</span>
          <span className="font-semibold text-foreground">9:16 (Shorts / Reels)</span>
        </div>
        <div>
          <span className="text-muted-foreground block text-[10px]">Resolution</span>
          <span className="font-semibold text-foreground">1080 &times; 1920 MP4</span>
        </div>
        <div>
          <span className="text-muted-foreground block text-[10px]">Audio</span>
          <span className="font-semibold text-foreground">Stereo AAC 48kHz</span>
        </div>
      </div>

      {isCheckingStatus ? (
        <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span>Checking export status…</span>
        </div>
      ) : (
        <div className="space-y-4">
          {status === 'idle' && (
            <div className="space-y-3">
              <GradientButton
                onClick={handleExport}
                disabled={isStarting}
                className="w-full py-3 text-sm font-semibold shadow-lg"
              >
                {isStarting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                ) : (
                  <Download className="h-4 w-4 mr-1.5" />
                )}
                Export (9:16)
              </GradientButton>
              <p className="text-center text-[11px] text-muted-foreground">
                Renders high-quality 9:16 MP4 with selected caption style and B-roll overlays.
              </p>
            </div>
          )}

          {status === 'rendering' && (
            <div className="rounded-xl border border-primary/30 bg-primary/10 p-5 text-center space-y-3">
              <div className="flex items-center justify-center gap-2 text-primary font-semibold text-sm">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>Rendering your 9:16 clip…</span>
              </div>
              <p className="text-xs text-muted-foreground">
                FFmpeg is compositing video, burning subtitles, and overlaying B-roll footage.
              </p>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div className="h-full w-2/3 animate-pulse rounded-full bg-primary" />
              </div>
            </div>
          )}

          {status === 'ready' && (
            <div className="space-y-3">
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3.5 text-center text-xs text-emerald-400 font-medium">
                ✨ Your 9:16 vertical Short is rendered and ready for download!
              </div>
              <GradientButton
                onClick={handleDownload}
                disabled={isDownloading}
                className="w-full py-3 text-sm font-bold bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow-lg hover:opacity-95"
              >
                {isDownloading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                ) : (
                  <Download className="h-4 w-4 mr-1.5" />
                )}
                Download
              </GradientButton>
              <button
                type="button"
                onClick={handleExport}
                disabled={isStarting}
                className="w-full text-center text-xs text-muted-foreground hover:text-foreground transition-colors underline pt-1"
              >
                Re-export with new edits
              </button>
            </div>
          )}

          {status === 'failed' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 rounded-xl bg-destructive/15 p-3 text-xs text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{errorMessage ?? 'Export failed.'}</span>
              </div>
              <GradientButton
                variant="outline"
                onClick={handleExport}
                disabled={isStarting}
                className="w-full"
              >
                {isStarting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                ) : null}
                Retry export
              </GradientButton>
            </div>
          )}

          {errorMessage && status !== 'failed' && (
            <p className="text-xs text-destructive bg-destructive/10 p-2.5 rounded-lg">{errorMessage}</p>
          )}
        </div>
      )}
    </GlassCard>
  );
}
