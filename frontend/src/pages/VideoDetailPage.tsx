import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { ProcessingProgress } from '@/components/videos/ProcessingProgress';
import { StatusBadge } from '@/components/videos/StatusBadge';
import { cn } from '@/lib/utils';
import { generateClips, listClips } from '@/services/clipService';
import { getTranscript, getVideo, reprocessVideo } from '@/services/videoService';
import type { TranscriptSegment, VideoProject, VideoProjectStatus } from '@/types';

const POLL_INTERVAL_MS = 4000;
const TERMINAL_STATUSES: VideoProjectStatus[] = ['ready', 'failed'];

function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Video project detail page. Polls the backend while the pipeline is
 * running and renders the transcript once the project is ready.
 */
export function VideoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const videoId = Number(id);
  const navigate = useNavigate();

  const [video, setVideo] = useState<VideoProject | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [transcript, setTranscript] = useState<TranscriptSegment[] | null>(
    null,
  );
  const [transcriptError, setTranscriptError] = useState<string | null>(null);

  const [isReprocessing, setIsReprocessing] = useState(false);
  const [reprocessError, setReprocessError] = useState<string | null>(null);

  const [hasClips, setHasClips] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  // Poll the video project while its pipeline is still running.
  useEffect(() => {
    if (!Number.isFinite(videoId)) return;

    let cancelled = false;
    let intervalId: ReturnType<typeof setInterval> | undefined;

    async function fetchVideo() {
      try {
        const data = await getVideo(videoId);
        if (cancelled) return;
        setVideo(data);
        setError(null);
        if (TERMINAL_STATUSES.includes(data.status) && intervalId) {
          clearInterval(intervalId);
        }
      } catch {
        if (!cancelled) setError('Failed to load this video project.');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void fetchVideo();
    intervalId = setInterval(() => void fetchVideo(), POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [videoId]);

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

    // Check if clips already exist for this project
    listClips(video.id)
      .then((response) => {
        if (!cancelled) setHasClips(response.items.length > 0);
      })
      .catch(() => {
        // Non-critical — just leave hasClips false
      });

    return () => {
      cancelled = true;
    };
    // Re-run only when the id or status changes, not on every poll tick
    // (polling replaces `video` with a new object each time it succeeds).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [video?.id, video?.status]);

  async function handleStartProcessing() {
    if (!video) return;
    setIsReprocessing(true);
    setReprocessError(null);
    try {
      const updated = await reprocessVideo(video.id);
      setVideo(updated);
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
      await generateClips(video.id);
      navigate(`/clips`);
    } catch {
      setGenerateError('Failed to generate clips. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  }

  if (isLoading) {
    return (
      <PageWrapper className="mx-auto max-w-3xl px-4 py-10">
        <p className="text-sm text-muted-foreground">Loading video&hellip;</p>
      </PageWrapper>
    );
  }

  if (error || !video) {
    return (
      <PageWrapper className="mx-auto max-w-3xl px-4 py-10">
        <GlassCard>
          <p className="text-sm text-destructive">
            {error ?? 'Video project not found.'}
          </p>
        </GlassCard>
      </PageWrapper>
    );
  }

  const isProcessing = !TERMINAL_STATUSES.includes(video.status);

  return (
    <PageWrapper className="mx-auto max-w-3xl px-4 py-10">
      <ProcessingProgress
        status={video.status}
        isGeneratingClips={isGenerating}
        className="mb-6"
      />

      <GlassCard className="mb-6">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-xl font-semibold">{video.title}</h1>
          <StatusBadge status={video.status} />
        </div>

        <dl className="grid grid-cols-2 gap-3 text-sm text-muted-foreground sm:grid-cols-3">
          <div>
            <dt className="font-medium text-foreground">Source</dt>
            <dd className="capitalize">{video.source_type}</dd>
          </div>
          <div>
            <dt className="font-medium text-foreground">Duration</dt>
            <dd>
              {video.duration_seconds !== null
                ? formatTimestamp(video.duration_seconds)
                : '--:--'}
            </dd>
          </div>
          <div>
            <dt className="font-medium text-foreground">Created</dt>
            <dd>{new Date(video.created_at).toLocaleDateString()}</dd>
          </div>
        </dl>

        {video.status === 'failed' && video.error_message && (
          <p className="mt-3 text-sm text-destructive">
            {video.error_message}
          </p>
        )}

        {isProcessing && (
          <p className="mt-3 text-sm text-muted-foreground">
            Processing is in progress&mdash;this page refreshes
            automatically every few seconds.
          </p>
        )}

        {reprocessError && (
          <p className="mt-3 text-sm text-destructive">{reprocessError}</p>
        )}

        {generateError && (
          <p className="mt-3 text-sm text-destructive">{generateError}</p>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          {video.status === 'ready' ? (
            hasClips ? (
              <Link to="/clips">
                <GradientButton>View Clips &rarr;</GradientButton>
              </Link>
            ) : (
              <GradientButton
                onClick={handleGenerateClips}
                disabled={isGenerating}
              >
                {isGenerating ? 'Generating…' : 'Generate Clips'}
              </GradientButton>
            )
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
        </div>
      </GlassCard>

      {video.status === 'ready' && (
        <GlassCard>
          <h2 className="mb-4 text-lg font-semibold">Transcript</h2>

          {transcriptError && (
            <p className="text-sm text-destructive">{transcriptError}</p>
          )}

          {!transcript && !transcriptError && (
            <p className="text-sm text-muted-foreground">
              Loading transcript&hellip;
            </p>
          )}

          {transcript && transcript.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No transcript segments available.
            </p>
          )}

          {transcript && transcript.length > 0 && (
            <ul className="flex flex-col gap-2">
              {transcript.map((segment) => (
                <li
                  key={segment.id}
                  className={cn(
                    'rounded-lg border border-transparent px-3 py-2 text-sm',
                    segment.is_highlight
                      ? 'border-primary/30 bg-primary/10 font-medium'
                      : 'text-muted-foreground',
                  )}
                >
                  <span className="mr-2 font-mono text-xs text-muted-foreground">
                    {formatTimestamp(segment.start_time)}&ndash;
                    {formatTimestamp(segment.end_time)}
                  </span>
                  {segment.text}
                  {segment.is_highlight && segment.highlight_score !== null && (
                    <span className="ml-2 rounded-full bg-primary/20 px-2 py-0.5 text-xs text-primary">
                      {Math.round(segment.highlight_score * 100)}% highlight
                    </span>
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
