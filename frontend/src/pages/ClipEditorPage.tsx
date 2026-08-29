import { useCallback, useEffect, useState, useRef } from 'react';
import {
  Film,
  Sparkles,
  Sliders,
  FileText,
  Download,
  Play,
  Pause,
  RotateCcw,
  UserCheck,
  Maximize2,
  Layers,
  Loader2,
} from 'lucide-react';
import { useParams, Link } from 'react-router-dom';
import { BrollPanel } from '@/components/clips/BrollPanel';
import { CaptionEditor } from '@/components/clips/CaptionEditor';
import { CaptionStyleSelector } from '@/components/clips/CaptionStyleSelector';
import { ExportPanel } from '@/components/clips/ExportPanel';
import { TextBasedTrimmer } from '@/components/clips/TextBasedTrimmer';
import { TrimControls } from '@/components/clips/TrimControls';
import { ViralityScoreBadge } from '@/components/clips/ViralityScoreBadge';
import { GlassCard } from '@/components/ui/GlassCard';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { computeViralityInsights } from '@/lib/virality';
import { cn } from '@/lib/utils';
import { getClip, getClipPreviewUrl, updateClip } from '@/services/clipService';
import { getClipBrollAssets } from '@/services/brollService';
import { getTranscript } from '@/services/videoService';
import {
  triggerExport,
  getExportStatus,
  downloadClip,
} from '@/services/exportService';
import type { CaptionStylePreset, Clip, TranscriptSegment, BrollAsset } from '@/types';

export type FramingMode = 'speaker_focus' | 'dynamic_blur' | 'fit';

export function ClipEditorPage() {
  const { id } = useParams<{ id: string }>();
  const clipId = id ? Number(id) : NaN;

  const [clip, setClip] = useState<Clip | null>(null);
  const [transcriptSegments, setTranscriptSegments] = useState<TranscriptSegment[]>([]);
  const [brollAssets, setBrollAssets] = useState<BrollAsset[]>([]);
  const [framingMode, setFramingMode] = useState<FramingMode>('speaker_focus');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewFailed, setPreviewFailed] = useState(false);
  const [activeTab, setActiveTab] = useState<'captions' | 'trim' | 'broll' | 'export'>('captions');
  const [captionPreset, setCaptionPreset] = useState<CaptionStylePreset>('hormozi');
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);

  // Direct Header Export & Download state
  const [exportStatus, setExportStatus] = useState<'idle' | 'rendering' | 'ready' | 'failed'>('idle');
  const [isExporting, setIsExporting] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);

  // Load initial export status
  useEffect(() => {
    if (!Number.isFinite(clipId)) return;
    getExportStatus(clipId)
      .then((data) => {
        setExportStatus(data.status);
      })
      .catch(() => {
        setExportStatus('idle');
      });
  }, [clipId]);

  const loadClip = useCallback(async () => {
    if (!Number.isFinite(clipId)) {
      setError('Invalid clip ID.');
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await getClip(clipId);
      setClip(data);
      if (data.video_project_id) {
        try {
          const segments = await getTranscript(data.video_project_id);
          setTranscriptSegments(segments);
        } catch {
          // Non-blocking
        }
      }
      try {
        const brolls = await getClipBrollAssets(clipId);
        setBrollAssets(brolls);
      } catch {
        // Non-blocking
      }
    } catch {
      setError('Could not load this clip.');
    } finally {
      setIsLoading(false);
    }
  }, [clipId]);

  useEffect(() => {
    void loadClip();
  }, [loadClip]);

  const handleTrimSave = async (startTime: number, endTime: number) => {
    if (!clip) return;
    const updated = await updateClip(clip.id, {
      start_time: startTime,
      end_time: endTime,
    });
    setClip(updated);
  };

  const handleCaptionSave = async (captionText: string) => {
    if (!clip) return;
    const updated = await updateClip(clip.id, { caption_text: captionText });
    setClip(updated);
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      void videoRef.current.play();
      setIsPlaying(true);
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  };

  const resetPlayhead = () => {
    if (!videoRef.current || !clip) return;
    videoRef.current.currentTime = clip.status === 'ready' ? 0 : clip.start_time;
    void videoRef.current.play();
    setIsPlaying(true);
  };

  const handleHeaderExportAndDownload = async () => {
    if (!clip) return;

    if (exportStatus === 'ready') {
      setIsDownloading(true);
      try {
        await downloadClip(clip.id);
      } catch {
        setError('Failed to download video file. Please try again.');
      } finally {
        setIsDownloading(false);
      }
      return;
    }

    setIsExporting(true);
    try {
      await triggerExport(clip.id);
      setExportStatus('rendering');

      const intervalId = setInterval(async () => {
        try {
          const res = await getExportStatus(clip.id);
          if (res.status === 'ready') {
            clearInterval(intervalId);
            setExportStatus('ready');
            setIsExporting(false);
            setIsDownloading(true);
            try {
              await downloadClip(clip.id);
            } catch {
              setError('Render finished! Click Download to save your MP4.');
            } finally {
              setIsDownloading(false);
            }
          } else if (res.status === 'failed') {
            clearInterval(intervalId);
            setExportStatus('failed');
            setIsExporting(false);
            setError('Export rendering failed. Please try again.');
          }
        } catch {
          clearInterval(intervalId);
          setExportStatus('failed');
          setIsExporting(false);
        }
      }, 2500);
    } catch {
      setIsExporting(false);
      setExportStatus('failed');
      setError('Could not start export.');
    }
  };

  if (isLoading) {
    return (
      <PageWrapper className="mx-auto max-w-6xl px-4 py-10">
        <GlassCard className="flex items-center justify-center py-16">
          <p className="text-sm text-muted-foreground animate-pulse">
            Loading AI Clip Studio&hellip;
          </p>
        </GlassCard>
      </PageWrapper>
    );
  }

  if (error || !clip) {
    return (
      <PageWrapper className="mx-auto max-w-6xl px-4 py-10">
        <GlassCard>
          <p className="text-sm text-destructive">{error ?? 'Clip not found.'}</p>
          <Link to="/clips" className="mt-4 inline-block text-xs text-primary underline">
            &larr; Back to Clips Library
          </Link>
        </GlassCard>
      </PageWrapper>
    );
  }

  const duration = Math.max(0, clip.end_time - clip.start_time);
  const virality = computeViralityInsights(
    clip.caption_text || clip.title,
    duration,
  );

  // Determine relative time for word-synced B-roll overlay
  const relativeTime = clip.status === 'ready' ? currentTime : Math.max(0, currentTime - clip.start_time);
  const activeBroll = brollAssets.find(
    (b) => relativeTime >= b.position_start && relativeTime <= b.position_end
  );

  return (
    <PageWrapper className="mx-auto max-w-6xl px-4 py-8 space-y-6">
      {/* Studio Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-glass-border pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link to="/clips" className="text-xs text-muted-foreground hover:text-foreground">
              Clips
            </Link>
            <span className="text-muted-foreground text-xs">&gt;</span>
            <span className="text-xs font-semibold text-primary">Clip #{clip.id}</span>
          </div>
          <h1 className="text-2xl font-bold text-foreground">{clip.title}</h1>
        </div>

        <div className="flex items-center gap-3">
          <ViralityScoreBadge insights={virality} size="md" />
          <button
            type="button"
            onClick={handleHeaderExportAndDownload}
            disabled={isExporting || isDownloading}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-bold text-white shadow-lg transition-all cursor-pointer",
              exportStatus === 'ready'
                ? "bg-gradient-to-r from-emerald-500 to-teal-500 hover:opacity-90 animate-pulse"
                : "bg-gradient-to-r from-gradient-from to-gradient-to hover:opacity-90",
              (isExporting || isDownloading) && "opacity-75 cursor-wait"
            )}
          >
            {isExporting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Rendering 9:16...</span>
              </>
            ) : isDownloading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Downloading MP4...</span>
              </>
            ) : exportStatus === 'ready' ? (
              <>
                <Download className="h-4 w-4" />
                <span>Download MP4 (9:16)</span>
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                <span>Export &amp; Download (9:16)</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Studio Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: 9:16 Vertical Shorts Player Canvas */}
        <div className="lg:col-span-5 flex flex-col items-center">
          {/* Speaker Focus & Framing Mode Selector */}
          <div className="flex items-center gap-1.5 p-1 mb-3 rounded-full bg-muted/60 border border-glass-border text-[11px] font-medium">
            <button
              type="button"
              onClick={() => setFramingMode('speaker_focus')}
              className={cn(
                'flex items-center gap-1 px-3 py-1 rounded-full transition-all',
                framingMode === 'speaker_focus'
                  ? 'bg-primary text-white shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <UserCheck className="h-3 w-3" />
              Speaker Focus (9:16)
            </button>
            <button
              type="button"
              onClick={() => setFramingMode('dynamic_blur')}
              className={cn(
                'flex items-center gap-1 px-3 py-1 rounded-full transition-all',
                framingMode === 'dynamic_blur'
                  ? 'bg-primary text-white shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <Layers className="h-3 w-3" />
              Dynamic Blur
            </button>
            <button
              type="button"
              onClick={() => setFramingMode('fit')}
              className={cn(
                'flex items-center gap-1 px-3 py-1 rounded-full transition-all',
                framingMode === 'fit'
                  ? 'bg-primary text-white shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <Maximize2 className="h-3 w-3" />
              Fit
            </button>
          </div>

          <div className="relative w-full max-w-[340px] aspect-[9/16] rounded-3xl overflow-hidden border-4 border-muted/80 bg-black shadow-2xl flex flex-col justify-center">
            {previewFailed ? (
              <div className="flex flex-col items-center gap-3 text-muted-foreground p-6 text-center">
                <Film className="h-12 w-12 text-primary opacity-60" />
                <p className="text-xs font-medium">9:16 Preview Rendering</p>
                <p className="text-[11px] text-muted-foreground">
                  The raw video is available for trimming below.
                </p>
              </div>
            ) : (
              <>
                {/* Optional Blurred Background Canvas for Dynamic Blur Mode */}
                {framingMode === 'dynamic_blur' && (
                  <div className="absolute inset-0 overflow-hidden opacity-70 filter blur-xl scale-125 pointer-events-none">
                    <video
                      src={getClipPreviewUrl(clip.id)}
                      playsInline
                      muted
                      className="h-full w-full object-cover"
                    />
                  </div>
                )}

                {/* Main Video Element with Speaker Centering */}
                <video
                  ref={videoRef}
                  key={clip.id}
                  src={getClipPreviewUrl(clip.id)}
                  playsInline
                  className={cn(
                    'h-full w-full transition-transform duration-500',
                    framingMode === 'speaker_focus'
                      ? 'object-cover scale-125 object-center'
                      : framingMode === 'dynamic_blur'
                        ? 'object-contain relative z-10'
                        : 'object-contain'
                  )}
                  onError={() => setPreviewFailed(true)}
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  onLoadedMetadata={(event) => {
                    if (clip.status !== 'ready') {
                      event.currentTarget.currentTime = clip.start_time;
                    }
                  }}
                  onTimeUpdate={(event) => {
                    const curr = event.currentTarget.currentTime;
                    setCurrentTime(curr);
                    if (clip.status !== 'ready' && curr >= clip.end_time) {
                      event.currentTarget.pause();
                      event.currentTarget.currentTime = clip.start_time;
                    }
                  }}
                />

                {/* Live Word-Synced B-Roll Overlay */}
                {activeBroll && (
                  <div className="absolute top-4 right-4 z-20 w-32 aspect-video rounded-xl overflow-hidden border-2 border-primary shadow-2xl animate-in fade-in zoom-in-95 duration-200">
                    <video
                      src={activeBroll.asset_url}
                      muted
                      autoPlay
                      loop
                      playsInline
                      className="h-full w-full object-cover"
                    />
                    <div className="absolute bottom-1 inset-x-1 flex items-center justify-between bg-black/80 backdrop-blur-sm rounded px-1.5 py-0.5 text-[9px] text-white">
                      <span className="font-semibold truncate">✨ {activeBroll.keyword}</span>
                      <span className="text-primary font-mono text-[8px]">Word Sync</span>
                    </div>
                  </div>
                )}

                {/* Subtitle Simulation Overlay with Word Highlight */}
                {clip.caption_text && (
                  <div className="absolute inset-x-4 bottom-14 z-20 pointer-events-none text-center">
                    <span
                      className={cn(
                        'inline-block px-3 py-1.5 rounded-lg text-xs leading-tight transition-all',
                        captionPreset === 'hormozi'
                          ? 'bg-black/90 text-yellow-300 font-black uppercase tracking-wider border-2 border-lime-400 shadow-lg'
                          : captionPreset === 'neon'
                            ? 'bg-black/80 text-cyan-300 font-extrabold tracking-wide border border-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.7)]'
                            : captionPreset === 'karaoke'
                              ? 'bg-black/70 text-emerald-300 font-extrabold uppercase border-b-2 border-emerald-400'
                              : captionPreset === 'bold_box'
                                ? 'bg-black/80 text-white font-bold'
                                : 'text-white font-semibold drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)]',
                      )}
                    >
                      {activeBroll ? (
                        <span>
                          {clip.caption_text.split(new RegExp(`(${activeBroll.keyword})`, 'gi')).map((part, idx) =>
                            part.toLowerCase() === activeBroll.keyword.toLowerCase() ? (
                              <span key={idx} className="text-lime-300 bg-lime-500/30 px-1 rounded underline">
                                {part}
                              </span>
                            ) : (
                              part
                            )
                          )}
                        </span>
                      ) : (
                        clip.caption_text
                      )}
                    </span>
                  </div>
                )}

                {/* Player Controls Bar */}
                <div className="absolute bottom-3 inset-x-4 z-20 flex items-center justify-between bg-black/60 backdrop-blur-md rounded-full px-3 py-1 text-white text-xs">
                  <button
                    type="button"
                    onClick={togglePlay}
                    className="p-1 hover:text-primary transition-colors"
                  >
                    {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                  </button>

                  <span className="font-mono text-[11px] text-muted-foreground">
                    {currentTime.toFixed(1)}s / {clip.end_time.toFixed(1)}s
                  </span>

                  <button
                    type="button"
                    onClick={resetPlayhead}
                    title="Replay"
                    className="p-1 hover:text-primary transition-colors"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                  </button>
                </div>
              </>
            )}
          </div>

          <p className="mt-3 text-xs text-muted-foreground text-center">
            9:16 Vertical Short Preview &bull; {duration.toFixed(1)}s Duration
          </p>
        </div>

        {/* Right: Studio Editing Tabs */}
        <div className="lg:col-span-7 space-y-5">
          {/* Tab Navigation */}
          <div className="flex gap-2 rounded-xl bg-muted/60 p-1.5 border border-glass-border">
            {[
              { id: 'captions', label: 'Captions & Style', icon: Sparkles },
              { id: 'trim', label: 'Trim Timeline', icon: Sliders },
              { id: 'broll', label: 'B-Roll Media', icon: Film },
              { id: 'export', label: 'Render & Export', icon: Download },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id as any)}
                className={cn(
                  'flex-1 flex items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-semibold transition-all',
                  activeTab === tab.id
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <tab.icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab 1: Captions & Style */}
          {activeTab === 'captions' && (
            <div className="space-y-5">
              <GlassCard className="space-y-4">
                <CaptionStyleSelector
                  selectedPreset={captionPreset}
                  onSelect={setCaptionPreset}
                />
              </GlassCard>

              <GlassCard className="space-y-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5 text-primary" />
                  Edit Caption Subtitle Text
                </h3>
                <CaptionEditor
                  captionText={clip.caption_text}
                  onSave={handleCaptionSave}
                />
              </GlassCard>
            </div>
          )}

          {/* Tab 2: Trim Timeline */}
          {activeTab === 'trim' && (
            <div className="space-y-5">
              <GlassCard>
                <TextBasedTrimmer
                  segments={transcriptSegments}
                  clipStartTime={clip.start_time}
                  clipEndTime={clip.end_time}
                  onApplyTrim={handleTrimSave}
                />
              </GlassCard>

              <GlassCard className="space-y-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <Sliders className="h-3.5 w-3.5 text-primary" />
                  Fine-Tune Timestamps (Seconds)
                </h3>
                <TrimControls
                  startTime={clip.start_time}
                  endTime={clip.end_time}
                  onSave={handleTrimSave}
                />
              </GlassCard>
            </div>
          )}

          {/* Tab 3: B-Roll Media */}
          {activeTab === 'broll' && (
            <BrollPanel clipId={clip.id} />
          )}

          {/* Tab 4: Export */}
          {activeTab === 'export' && (
            <div className="space-y-5">
              <ExportPanel clipId={clip.id} />

              <GlassCard>
                <ViralityScoreBadge insights={virality} showDetails size="lg" />
              </GlassCard>
            </div>
          )}
        </div>
      </div>
    </PageWrapper>
  );
}
