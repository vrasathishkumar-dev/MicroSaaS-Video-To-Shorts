import { useCallback, useEffect, useState } from 'react';
import { Film } from 'lucide-react';
import { Link } from 'react-router-dom';
import { AnimatedList } from '@/components/ui/AnimatedList';
import { GradientButton } from '@/components/ui/GradientButton';
import { ClipCard } from '@/components/clips/ClipCard';
import { cn } from '@/lib/utils';
import { deleteClip, listClips } from '@/services/clipService';
import type { Clip } from '@/types';

export interface ClipGridProps {
  /** Optional filter — when set, only clips for this video project load. */
  videoProjectId?: number;
  className?: string;
}

/**
 * Responsive grid of clip tiles. Fetches clips itself (optionally scoped
 * to a video project), stagger-animates them in via AnimatedList, and
 * shows a "generate clips" call to action when there are none yet.
 */
export function ClipGrid({ videoProjectId, className }: ClipGridProps) {
  const [clips, setClips] = useState<Clip[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadClips = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await listClips(videoProjectId);
      setClips(response.items);
    } catch {
      setError('Could not load clips. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [videoProjectId]);

  useEffect(() => {
    void loadClips();
  }, [loadClips]);

  const handleDelete = async (id: number) => {
    const previousClips = clips;
    setClips((current) => current.filter((clip) => clip.id !== id));
    try {
      await deleteClip(id);
    } catch {
      setClips(previousClips);
      setError('Could not delete that clip. Please try again.');
    }
  };

  if (isLoading) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Loading clips...
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-16 text-center text-sm text-destructive">{error}</div>
    );
  }

  if (clips.length === 0) {
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-center">
        <Film className="h-10 w-10 text-muted-foreground" />
        <p className="max-w-sm text-sm text-muted-foreground">
          No clips yet. Generate clips from one of your videos to get
          started.
        </p>
        <Link to="/videos">
          <GradientButton type="button">
            Generate clips from a video
          </GradientButton>
        </Link>
      </div>
    );
  }

  return (
    <AnimatedList
      className={cn(
        'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3',
        className,
      )}
    >
      {clips.map((clip) => (
        <ClipCard key={clip.id} clip={clip} onDelete={handleDelete} />
      ))}
    </AnimatedList>
  );
}
