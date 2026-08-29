import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  Film,
  Sparkles,
  Scissors,
  Flame,
  AlertCircle,
} from 'lucide-react';
import { ClipCard } from '@/components/clips/ClipCard';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { ProcessingProgress } from '@/components/videos/ProcessingProgress';
import { StatusBadge } from '@/components/videos/StatusBadge';
import { cn } from '@/lib/utils';
import { generateClips, listClips, deleteClip } from '@/services/clipService';
import { getTranscript, getVideo, reprocessVideo } from '@/services/videoService';
import { getExpectedShortsCount } from '@/lib/virality';
import type { Clip, TranscriptSegment, VideoProject, VideoProjectStatus } from '@/types';

const POLL_INTERVAL_MS = 3000;
const TERMINAL_STATUSES: VideoProjectStatus[] = ['ready', 'failed'];

function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function VideoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const videoId = Number(id);

  const [video, setVideo] = useState<VideoProject | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [transcript, setTranscript] = useState<TranscriptSegment[] | null>(null);
  const [transcriptError, setTranscriptError] = useState<string | null>(null);

  const [isReprocessing, setIsReprocessing] = useState(false);
  const [reprocessError, setReprocessError] = useState<string | null>(null);

  const [clips, setClips] = useState<Clip[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  const [pollTrigger, setPollTrigger] = useState(0);

  // Poll the video project while its pipeline is still running.
  useEffect(() => {
    if (!Number.isFinite(videoId)) return;

    let cancelled = false;
    let intervalId: ReturnType<typeof setInterval> | undefined;

    async function checkVideo() {
      try {
        const data = await getVideo(videoId);
        if (cancelled) return;
        setVideo(data);
        setError(null);

        // If the project finished processing, stop active interval and refresh data
        if (TERMINAL_STATUSES.includes(data.status)) {
          if (intervalId) clearInterval(intervalId);
        }
      } catch {
        if (!cancelled) setError('Failed to load this video project.');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void checkVideo();
    intervalId = setInterval(() => void checkVideo(), POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [videoId, pollTrigger]);

  // Once the project is ready, load its transcript and check for existing clips.
  useEffect(() => {
    if (!video || video.status !== 'ready') return;

    let cancelled = false;
    getTranscript(video.id)
      .then((segments) => {
        if (!cancelled) setTranscript(segments);
      })
      .catch(() => {
        if (!cancelled) {
          setTranscriptError('Failed to load the transcript.');
        }
      });

    listClips(video.id)
      .then((response) => {
        if (!cancelled) setClips(response.items);
      })
      .catch(() => {
        // Non-critical
      });

    return () => {
      cancelled = true;
    };
  }, [video?.id, video?.status]);

  async function handleStartProcessing() {
    if (!video) return;
    setIsReprocessing(true);
    setReprocessError(null);
    try {
      const updated = await reprocessVideo(video.id);
      setVideo(updated);
      // Restart active polling
      setPollTrigger((prev) => prev + 1);
    } catch {
      setReprocessError('Failed to start processing. Please try again.');
    } finally {
      setIsReprocessing(false);
    }
  }

  async function handleGenerateClips() {
    if (!video) return;
    setIsGenerating(true);
    setGenerateError(null);
    try {
      const generated = await generateClips(video.id);
      setClips(generated);
    } catch {
      setGenerateError('Failed to generate clips. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  }

  const handleDeleteClip = async (clipId: number) => {
    try {
      await deleteClip(clipId);
      setClips((current) => current.filter((c) => c.id !== clipId));
    } catch {
      // Non-blocking
    }
  };

  if (isLoading) {
    return (
      <PageWrapper className="mx-auto max-w-5xl px-4 py-10">
        <GlassCard className="flex items-center justify-center py-16">
          <p className="text-sm text-muted-foreground animate-pulse">Loading video project&hellip;</p>
        </GlassCard>
      </PageWrapper>
    );
  }

  if (error || !video) {
    return (
      <PageWrapper className="mx-auto max-w-5xl px-4 py-10">
        <GlassCard>
          <p className="text-sm text-destructive">{error ?? 'Video project not found.'}</p>
          <Link to="/videos" className="mt-3 inline-block text-xs text-primary underline">
            &larr; Back to video library
          </Link>
        </GlassCard>
      </PageWrapper>
    );
  }

  const isProcessing = !TERMINAL_STATUSES.includes(video.status);
  const highlightsCount = transcript?.filter((t) => t.is_highlight).length ?? 0;

  return (
    <PageWrapper className="mx-auto max-w-5xl px-4 py-8 space-y-6">
      <ProcessingProgress
        status={video.status}
        isGeneratingClips={isGenerating}
      />

      {/* Project Overview Card */}
      <GlassCard className="p-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <span className="text-xs font-mono text-muted-foreground uppercase">Project #{video.id}</span>
            <h1 className="text-2xl font-bold text-foreground">{video.title}</h1>
          </div>
          <StatusBadge status={video.status} />
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 py-3 px-4 rounded-xl bg-background/50 border border-glass-border text-xs">
          <div>
            <span className="text-muted-foreground block text-[11px]">Source</span>
            <span className="font-semibold uppercase text-foreground">{video.source_type}</span>
          </div>
          <div>
            <span className="text-muted-foreground block text-[11px]">Duration</span>
            <span className="font-semibold text-foreground">
              {video.duration_seconds !== null ? formatTimestamp(video.duration_seconds) : '--:--'}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block text-[11px]">AI Highlights</span>
            <span className="font-semibold text-emerald-400">
              {highlightsCount > 0 ? `${highlightsCount} detected` : 'Analyzing'}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block text-[11px]">Shorts Output</span>
            <span className="font-semibold text-primary">
              {clips.length > 0
                ? `${clips.length} Clips`
                : `~${getExpectedShortsCount(video.duration_seconds)}`}
            </span>
          </div>
        </div>

        {video.status === 'failed' && video.error_message && (
          <div className="mt-4 flex items-center gap-2 rounded-xl bg-destructive/15 p-3 text-xs text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{video.error_message}</span>
          </div>
        )}

        {isProcessing && (
          <div className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-3 text-xs text-primary flex items-center gap-2">
            <Sparkles className="h-4 w-4 animate-spin shrink-0" />
            <span>AI transcription & highlight detection is actively processing...</span>
          </div>
        )}

        {reprocessError && (
          <p className="mt-3 text-xs text-destructive">{reprocessError}</p>
        )}

        {generateError && (
          <p className="mt-3 text-xs text-destructive">{generateError}</p>
        )}

        <div className="mt-6 flex flex-wrap items-center gap-3">
          {video.status === 'ready' ? (
            <GradientButton
              onClick={handleGenerateClips}
              disabled={isGenerating}
              className="gap-2 shadow-lg shadow-primary/20"
            >
              <Scissors className="h-4 w-4" />
              {isGenerating
                ? 'Generating Shorts…'
                : clips.length > 0
                  ? 'Re-generate Clips'
                  : 'Generate Viral Shorts'}
            </GradientButton>
          ) : (
            <GradientButton
              onClick={handleStartProcessing}
              disabled={isReprocessing || isProcessing}
            >
              {isReprocessing
                ? 'Starting…'
                : isProcessing
                  ? 'Processing…'
                  : 'Start processing'}
            </GradientButton>
          )}

          {clips.length > 0 && (
            <Link to="/clips">
              <GradientButton variant="outline" className="gap-1.5">
                <Film className="h-4 w-4" />
                View All Clips ({clips.length})
              </GradientButton>
            </Link>
          )}
        </div>
      </GlassCard>

      {/* Generated Clips Grid Section */}
      {clips.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Film className="h-5 w-5 text-primary" />
              <h2 className="text-lg font-bold text-foreground">
                Generated Shorts ({clips.length})
              </h2>
            </div>
            <span className="text-xs text-muted-foreground">Click any short to edit in Studio</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {clips.map((clip) => (
              <ClipCard
                key={clip.id}
                clip={clip}
                onDelete={handleDeleteClip}
              />
            ))}
          </div>
        </div>
      )}

      {/* Transcript & Highlights Breakdown */}
      {video.status === 'ready' && (
        <GlassCard className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-foreground flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              Timestamped Transcript & AI Highlights
            </h2>
            <span className="text-xs text-muted-foreground">
              {transcript?.length ?? 0} Segments
            </span>
          </div>

          {transcriptError && (
            <p className="text-xs text-destructive">{transcriptError}</p>
          )}

          {!transcript && !transcriptError && (
            <p className="text-xs text-muted-foreground py-4 text-center">
              Loading transcript data&hellip;
            </p>
          )}

          {transcript && transcript.length > 0 && (
            <ul className="flex flex-col gap-2 max-h-96 overflow-y-auto pr-1">
              {transcript.map((segment) => (
                <li
                  key={segment.id}
                  className={cn(
                    'rounded-xl border p-3 text-xs transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-2',
                    segment.is_highlight
                      ? 'border-emerald-500/40 bg-emerald-500/10 font-medium'
                      : 'border-glass-border bg-background/40 text-muted-foreground',
                  )}
                >
                  <div className="flex items-start gap-2.5">
                    <span className="shrink-0 font-mono text-[11px] text-muted-foreground bg-muted/60 px-2 py-0.5 rounded">
                      {formatTimestamp(segment.start_time)}&ndash;{formatTimestamp(segment.end_time)}
                    </span>
                    <span className="text-foreground leading-relaxed">{segment.text}</span>
                  </div>

                  {segment.is_highlight && (
                    <div className="shrink-0 inline-flex items-center gap-1 rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-[10px] font-bold text-emerald-400">
                      <Flame className="h-3 w-3" />
                      <span>
                        {segment.highlight_score !== null
                          ? `${Math.round(segment.highlight_score * 100)}% Viral Hook`
                          : 'Top Highlight'}
                      </span>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </GlassCard>
      )}
    </PageWrapper>
  );
}
