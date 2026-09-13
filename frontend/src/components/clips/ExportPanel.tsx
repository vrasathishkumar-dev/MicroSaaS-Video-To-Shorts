import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, Download, Loader2, Zap } from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import {
  downloadClip,
  getClipEventsUrl,
  getExportStatus,
  isScoreGate,
  triggerExport,
  type ExportStatusResponse,
  type ScoreGateDetail,
} from '@/services/exportService';

type ExportState = 'idle' | 'rendering' | 'ready' | 'failed';

/** SSE event payload from the backend /clips/{id}/events stream. */
interface ClipEvent {
  type: 'status_update' | 'error' | 'timeout';
  status?: ExportState;
  pct?: number;
  virality_score?: number | null;
  message?: string;
}

/**
 * Self-contained export widget for a single clip. Fetches its own status on
 * mount, drives export + SSE progress, shows the soft score-gate confirmation
 * dialog, and offers download/retry.
 */
export function ExportPanel({ clipId }: { clipId: number }) {
  const [status, setStatus] = useState<ExportState>('idle');
  const [isCheckingStatus, setIsCheckingStatus] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [progressPct, setProgressPct] = useState(0);

  // Score gate state
  const [gateDetail, setGateDetail] = useState<ScoreGateDetail | null>(null);
  const [showGateDialog, setShowGateDialog] = useState(false);
  const [isConfirmingForce, setIsConfirmingForce] = useState(false);

  const eventSourceRef = useRef<EventSource | null>(null);

  // ----- SSE helpers -----

  const closeEventSource = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const openEventSource = useCallback(
    (id: number) => {
      closeEventSource();
      if (typeof EventSource === 'undefined') {
        return;
      }
      try {
        const url = getClipEventsUrl(id);
        const es = new EventSource(url);

      es.onmessage = (e: MessageEvent<string>) => {
        try {
          const event = JSON.parse(e.data) as ClipEvent;
          if (event.type === 'status_update' && event.status) {
            setStatus(event.status);
            if (event.pct !== undefined) setProgressPct(event.pct);
            if (event.status === 'ready' || event.status === 'failed') {
              closeEventSource();
            }
          } else if (event.type === 'error' || event.type === 'timeout') {
            // Fall back to polling on SSE errors
            closeEventSource();
          }
        } catch {
          // Malformed event — ignore
        }
      };

      es.onerror = () => {
        // EventSource auto-reconnects on transient errors; don't close.
        // If the stream is genuinely gone (clip rendered, server closed it),
        // the `status_update` with ready/failed has already been received.
      };

      eventSourceRef.current = es;
      } catch {
        closeEventSource();
      }
    },
    [closeEventSource],
  );

  // ----- Mount: fetch initial status -----

  useEffect(() => {
    let isMounted = true;

    getExportStatus(clipId)
      .then((data: ExportStatusResponse) => {
        if (!isMounted) return;
        setStatus(data.status);
        if (data.status === 'rendering') {
          setProgressPct(40);
          openEventSource(clipId);
        } else if (data.status === 'ready') {
          setProgressPct(100);
        }
      })
      .catch(() => {
        if (isMounted) setStatus('idle');
      })
      .finally(() => {
        if (isMounted) setIsCheckingStatus(false);
      });

    return () => {
      isMounted = false;
      closeEventSource();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clipId]);

  // ----- Export handlers -----

  const handleExport = async (force = false) => {
    setErrorMessage(null);
    setIsStarting(true);
    try {
      const data = force ? await triggerExport(clipId, true) : await triggerExport(clipId);
      setStatus(data.status);
      if (data.status === 'rendering') {
        setProgressPct(10);
        openEventSource(clipId);
      }
    } catch (err: unknown) {
      if (isScoreGate(err)) {
        setGateDetail(err.detail);
        setShowGateDialog(true);
      } else {
        setStatus('failed');
        setErrorMessage('Failed to start export. Please try again.');
      }
    } finally {
      setIsStarting(false);
    }
  };

  const handleConfirmForce = async () => {
    setShowGateDialog(false);
    setIsConfirmingForce(true);
    try {
      await handleExport(true);
    } finally {
      setIsConfirmingForce(false);
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

  // ----- Render -----

  return (
    <GlassCard className="space-y-5">
      <div className="flex items-center justify-between border-b border-glass-border pb-3">
        <div>
          <h3 className="text-base font-bold text-foreground">9:16 Video Export &amp; Download</h3>
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

      {/* Score Gate Confirmation Dialog */}
      {showGateDialog && gateDetail && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 space-y-3">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="h-5 w-5 text-amber-400 mt-0.5 shrink-0" />
            <div className="space-y-1">
              <p className="text-sm font-semibold text-amber-300">Low Virality Score</p>
              <p className="text-xs text-muted-foreground leading-relaxed">
                This clip scored{' '}
                <span className="font-bold text-amber-400">
                  {Math.round(gateDetail.virality_score)}/100
                </span>{' '}
                — below the {gateDetail.threshold}-point review threshold. The hook or sentence
                completeness may need work for maximum impact.
              </p>
            </div>
          </div>
          <div className="flex gap-2 pt-1">
            <button
              id={`export-cancel-gate-${clipId}`}
              type="button"
              onClick={() => setShowGateDialog(false)}
              className="flex-1 rounded-lg border border-glass-border bg-background/60 px-3 py-2 text-xs font-medium text-foreground hover:bg-background/80 transition-colors"
            >
              Review clip first
            </button>
            <GradientButton
              id={`export-force-${clipId}`}
              onClick={handleConfirmForce}
              disabled={isConfirmingForce}
              className="flex-1 py-2 text-xs font-semibold"
            >
              {isConfirmingForce ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
              ) : (
                <Zap className="h-3.5 w-3.5 mr-1" />
              )}
              Export anyway
            </GradientButton>
          </div>
        </div>
      )}

      {isCheckingStatus ? (
        <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span>Checking export status…</span>
        </div>
      ) : (
        <div className="space-y-4">
          {status === 'idle' && !showGateDialog && (
            <div className="space-y-3">
              <GradientButton
                id={`export-trigger-${clipId}`}
                onClick={() => handleExport(false)}
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
              {/* Animated progress bar driven by SSE events */}
              <div className="relative h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-primary to-violet-500 transition-all duration-700 ease-out"
                  style={{ width: `${Math.max(progressPct, 8)}%` }}
                />
              </div>
              <p className="text-[10px] text-muted-foreground font-mono">{progressPct}%</p>
            </div>
          )}

          {status === 'ready' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3.5 text-xs text-emerald-400 font-medium">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>Your 9:16 vertical Short is rendered and ready for download!</span>
              </div>
              <GradientButton
                id={`export-download-${clipId}`}
                onClick={handleDownload}
                disabled={isDownloading}
                className="w-full py-3 text-sm font-bold shadow-lg"
                style={{ background: 'linear-gradient(to right, #10b981, #14b8a6)' }}
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
                id={`export-re-render-${clipId}`}
                onClick={() => handleExport(false)}
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
                <span>{errorMessage ?? 'Export failed. Please try again.'}</span>
              </div>
              <GradientButton
                variant="outline"
                id={`export-retry-${clipId}`}
                onClick={() => handleExport(false)}
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
