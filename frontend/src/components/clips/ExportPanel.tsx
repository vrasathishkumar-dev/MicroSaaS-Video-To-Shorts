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
    } catch {
      setErrorMessage('Failed to download the clip. Please try again.');
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <GlassCard className="space-y-4">
      <h3 className="text-lg font-semibold">Export</h3>

      {isCheckingStatus ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Checking export status…</span>
        </div>
      ) : (
        <>
          {status === 'idle' && (
            <GradientButton onClick={handleExport} disabled={isStarting}>
              {isStarting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : null}
              Export (9:16)
            </GradientButton>
          )}

          {status === 'rendering' && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Rendering your 9:16 clip…</span>
            </div>
          )}

          {status === 'ready' && (
            <GradientButton onClick={handleDownload} disabled={isDownloading}>
              {isDownloading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Download
            </GradientButton>
          )}

          {status === 'failed' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm text-destructive">
                <AlertCircle className="h-4 w-4" />
                <span>{errorMessage ?? 'Export failed.'}</span>
              </div>
              <GradientButton
                variant="outline"
                onClick={handleExport}
                disabled={isStarting}
              >
                {isStarting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : null}
                Retry export
              </GradientButton>
            </div>
          )}

          {errorMessage && status !== 'failed' && (
            <p className="text-sm text-destructive">{errorMessage}</p>
          )}
        </>
      )}
    </GlassCard>
  );
}
