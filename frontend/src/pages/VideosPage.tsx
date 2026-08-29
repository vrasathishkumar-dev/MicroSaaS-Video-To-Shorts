import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AnimatedList } from '@/components/ui/AnimatedList';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { VideoProjectCard } from '@/components/videos/VideoProjectCard';
import { deleteVideo, listVideos } from '@/services/videoService';
import type { VideoProject } from '@/types';

/** Lists the current user's video projects with upload and delete actions. */
export function VideosPage() {
  const [videos, setVideos] = useState<VideoProject[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const loadVideos = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const page = await listVideos();
      setVideos(page.items);
    } catch {
      setError('Failed to load your videos. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadVideos();
  }, [loadVideos]);

  async function handleDelete(id: number) {
    setDeletingId(id);
    try {
      await deleteVideo(id);
      setVideos((current) => current.filter((video) => video.id !== id));
    } catch {
      setError('Failed to delete that video. Please try again.');
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <PageWrapper className="mx-auto max-w-5xl px-4 py-10">
      <div className="mb-8 flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold">Videos</h1>
        <Link to="/videos/new">
          <GradientButton>Upload video</GradientButton>
        </Link>
      </div>

      {error && (
        <GlassCard className="mb-6 border-destructive/30">
          <p className="text-sm text-destructive">{error}</p>
        </GlassCard>
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading your videos&hellip;</p>
      ) : videos.length === 0 ? (
        <GlassCard className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="text-lg font-medium">No videos yet</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Upload a video file or submit a source URL to start turning
            long-form content into short clips.
          </p>
          <Link to="/videos/new">
            <GradientButton className="mt-2">Upload your first video</GradientButton>
          </Link>
        </GlassCard>
      ) : (
        <AnimatedList className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {videos.map((video) => (
            <VideoProjectCard
              key={video.id}
              video={video}
              onDelete={handleDelete}
              isDeleting={deletingId === video.id}
            />
          ))}
        </AnimatedList>
      )}
    </PageWrapper>
  );
}
