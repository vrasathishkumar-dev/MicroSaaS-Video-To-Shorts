import { useCallback, useEffect, useState } from 'react';
import { CheckSquare, Download, Film, Loader2, Square, Zap } from 'lucide-react';
import { Link } from 'react-router-dom';
import { AnimatedList } from '@/components/ui/AnimatedList';
import { GradientButton } from '@/components/ui/GradientButton';
import { ClipCard } from '@/components/clips/ClipCard';
import { cn } from '@/lib/utils';
import { deleteClip, listClips } from '@/services/clipService';
import { downloadClip, triggerExport } from '@/services/exportService';
import type { Clip } from '@/types';

export interface ClipGridProps {
  /** Optional filter — when set, only clips for this video project load. */
  videoProjectId?: number;
  className?: string;
  /** When true, shows checkbox selectors on each card for bulk operations. */
  selectionMode?: boolean;
  selectedIds?: Set<number>;
  onSelectionChange?: (ids: Set<number>) => void;
}

/**
 * Responsive grid of clip tiles. Fetches clips itself (optionally scoped
 * to a video project), stagger-animates them in via AnimatedList, and
 * shows a "generate clips" call to action when there are none yet.
 *
 * When selectionMode is true, checkboxes appear on each card and bulk
 * actions (export selected, download ready) are enabled.
 */
export function ClipGrid({
  videoProjectId,
  className,
  selectionMode = false,
  selectedIds,
  onSelectionChange,
}: ClipGridProps) {
  const [clips, setClips] = useState<Clip[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exportingIds, setExportingIds] = useState<Set<number>>(new Set());
  const [bulkActionMessage, setBulkActionMessage] = useState<string | null>(null);

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

  const toggleSelected = (id: number) => {
    if (!onSelectionChange || !selectedIds) return;
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    onSelectionChange(next);
  };

  const handleExportSelected = async () => {
    if (!selectedIds || selectedIds.size === 0) return;
    setBulkActionMessage(null);
    const ids = [...selectedIds];
    setExportingIds(new Set(ids));

    let queued = 0;
    for (const id of ids) {
      try {
        await triggerExport(id, true); // force=true bypasses score gate for bulk
        queued++;
      } catch {
        // Continue with the rest
      }
    }

    setExportingIds(new Set());
    setBulkActionMessage(
      `Started rendering ${queued}/${ids.length} clip${queued !== 1 ? 's' : ''}. Refresh to see progress.`,
    );
    void loadClips();
  };

  const handleDownloadReady = async () => {
    const readyClips = clips.filter((c) => c.status === 'ready');
    setBulkActionMessage(null);
    for (const clip of readyClips) {
      try {
        await downloadClip(clip.id);
        // Small stagger so browser doesn't block multiple simultaneous downloads
        await new Promise((r) => setTimeout(r, 800));
      } catch {
        // Continue
      }
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
          No clips yet. Generate clips from one of your videos to get started.
        </p>
        <Link to="/videos">
          <GradientButton type="button">Generate clips from a video</GradientButton>
        </Link>
      </div>
    );
  }

  const readyCount = clips.filter((c) => c.status === 'ready').length;
  const selectedCount = selectedIds?.size ?? 0;

  return (
    <div className="space-y-4">
      {/* Bulk action bar — only shown when selectionMode is active */}
      {selectionMode && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-glass-border bg-background/60 p-3">
          <span className="text-xs text-muted-foreground">
            {selectedCount === 0
              ? 'Click clips to select'
              : `${selectedCount} clip${selectedCount !== 1 ? 's' : ''} selected`}
          </span>

          <div className="ml-auto flex gap-2">
            {readyCount > 0 && (
              <button
                id="bulk-download-ready"
                type="button"
                onClick={handleDownloadReady}
                className="flex items-center gap-1.5 rounded-lg border border-glass-border bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-400 hover:bg-emerald-500/20 transition-colors"
              >
                <Download className="h-3.5 w-3.5" />
                Download ready ({readyCount})
              </button>
            )}

            {selectedCount > 0 && (
              <GradientButton
                id="bulk-export-selected"
                onClick={handleExportSelected}
                disabled={exportingIds.size > 0}
                className="flex items-center gap-1.5 py-1.5 px-3 text-xs font-semibold"
              >
                {exportingIds.size > 0 ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Zap className="h-3.5 w-3.5" />
                )}
                Export selected ({selectedCount})
              </GradientButton>
            )}
          </div>
        </div>
      )}

      {bulkActionMessage && (
        <p className="rounded-lg bg-primary/10 px-3 py-2 text-xs text-primary">
          {bulkActionMessage}
        </p>
      )}

      <AnimatedList
        className={cn(
          'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3',
          className,
        )}
      >
        {clips.map((clip) => {
          const isSelected = selectedIds?.has(clip.id) ?? false;
          const isExporting = exportingIds.has(clip.id);
          return (
            <div key={clip.id} className="relative">
              {selectionMode && (
                <button
                  type="button"
                  id={`select-clip-${clip.id}`}
                  aria-label={isSelected ? `Deselect ${clip.title}` : `Select ${clip.title}`}
                  onClick={() => toggleSelected(clip.id)}
                  className="absolute left-3 top-3 z-30 rounded-full bg-black/70 p-1 backdrop-blur-md transition-colors hover:bg-primary/80"
                >
                  {isSelected ? (
                    <CheckSquare className="h-4 w-4 text-primary" />
                  ) : (
                    <Square className="h-4 w-4 text-white" />
                  )}
                </button>
              )}
              {isExporting && (
                <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-black/50 backdrop-blur-sm">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </div>
              )}
              <ClipCard
                clip={clip}
                onDelete={selectionMode ? undefined : handleDelete}
                className={cn(isSelected && 'ring-2 ring-primary ring-offset-2 ring-offset-background')}
              />
            </div>
          );
        })}
      </AnimatedList>
    </div>
  );
}
