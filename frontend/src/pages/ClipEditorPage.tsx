import { useCallback, useEffect, useState } from 'react';
import { Film } from 'lucide-react';
import { useParams } from 'react-router-dom';
import { BrollPanel } from '@/components/clips/BrollPanel';
import { CaptionEditor } from '@/components/clips/CaptionEditor';
import { ExportPanel } from '@/components/clips/ExportPanel';
import { TrimControls } from '@/components/clips/TrimControls';
import { GlassCard } from '@/components/ui/GlassCard';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { getClip, getClipPreviewUrl, updateClip } from '@/services/clipService';
import type { Clip } from '@/types';

/**
 * Single-clip editor: preview, trim controls, caption editor, plus the
 * B-roll and export panels owned by their respective module teams.
 */
export function ClipEditorPage() {
  const { id } = useParams<{ id: string }>();
  const clipId = id ? Number(id) : NaN;

  const [clip, setClip] = useState<Clip | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewFailed, setPreviewFailed] = useState(false);

  const loadClip = useCallback(async () => {
    if (!Number.isFinite(clipId)) {
      setError('Invalid clip id.');
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    setPreviewFailed(false);
    try {
      const data = await getClip(clipId);
      setClip(data);
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

  if (isLoading) {
    return (
      <PageWrapper className="mx-auto max-w-5xl px-4 py-10">
        <GlassCard>
          <p className="text-sm text-muted-foreground">Loading clip...</p>
        </GlassCard>
      </PageWrapper>
    );
  }

  if (error || !clip) {
    return (
      <PageWrapper className="mx-auto max-w-5xl px-4 py-10">
        <GlassCard>
          <p className="text-sm text-destructive">
            {error ?? 'Clip not found.'}
          </p>
        </GlassCard>
      </PageWrapper>
    );
  }

  return (
    <PageWrapper className="mx-auto max-w-5xl space-y-6 px-4 py-10">
      <GlassCard>
        <h1 className="text-xl font-semibold text-foreground">
          {clip.title}
        </h1>
        <p className="mt-1 text-sm capitalize text-muted-foreground">
          Status: {clip.status}
        </p>

        <div className="mt-6 flex aspect-video items-center justify-center overflow-hidden rounded-xl bg-muted">
          {previewFailed ? (
            <div className="flex flex-col items-center gap-2 text-muted-foreground">
              <Film className="h-12 w-12" />
              <p className="text-xs">Preview unavailable for this clip.</p>
            </div>
          ) : (
            <video
              key={clip.id}
              src={getClipPreviewUrl(clip.id)}
              controls
              className="h-full w-full object-contain"
              onError={() => setPreviewFailed(true)}
              onLoadedMetadata={(event) => {
                // A `ready` clip's export is already trimmed to
                // [start_time, end_time]; a draft/rendering/failed clip is
                // previewed from the full source video, so seek to the
                // clip's own start.
                if (clip.status !== 'ready') {
                  event.currentTarget.currentTime = clip.start_time;
                }
              }}
              onTimeUpdate={(event) => {
                if (clip.status !== 'ready' && event.currentTarget.currentTime >= clip.end_time) {
                  event.currentTarget.pause();
                  event.currentTarget.currentTime = clip.start_time;
                }
              }}
            />
          )}
        </div>
      </GlassCard>

      <GlassCard>
        <h2 className="text-lg font-semibold text-foreground">Trim</h2>
        <div className="mt-4">
          <TrimControls
            startTime={clip.start_time}
            endTime={clip.end_time}
            onSave={handleTrimSave}
          />
        </div>
      </GlassCard>

      <GlassCard>
        <h2 className="text-lg font-semibold text-foreground">Caption</h2>
        <div className="mt-4">
          <CaptionEditor
            captionText={clip.caption_text}
            onSave={handleCaptionSave}
          />
        </div>
      </GlassCard>

      <GlassCard>
        <h2 className="text-lg font-semibold text-foreground">B-roll</h2>
        <div className="mt-4">
          <BrollPanel clipId={clip.id} />
        </div>
      </GlassCard>

      <GlassCard>
        <h2 className="text-lg font-semibold text-foreground">Export</h2>
        <div className="mt-4">
          <ExportPanel clipId={clip.id} />
        </div>
      </GlassCard>
    </PageWrapper>
  );
}
