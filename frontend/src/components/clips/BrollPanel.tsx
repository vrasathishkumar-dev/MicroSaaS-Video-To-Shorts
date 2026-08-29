import { Film, Loader2, Search, Sparkles, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { BrollSearchModal } from '@/components/clips/BrollSearchModal';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { cn } from '@/lib/utils';
import {
  autoSourceBroll,
  getClipBrollAssets,
  removeBroll,
} from '@/services/brollService';
import type { BrollAsset } from '@/types';

export interface BrollPanelProps {
  clipId: number;
}

/**
 * Self-contained B-roll management panel for a single clip. Fetches its own
 * data on mount, lets the user auto-source B-roll, search for it manually,
 * or remove an attached asset. Meant to be dropped into a clip editor layout
 * as `<BrollPanel clipId={clip.id} />`.
 */
export function BrollPanel({ clipId }: BrollPanelProps) {
  const [assets, setAssets] = useState<BrollAsset[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAutoSourcing, setIsAutoSourcing] = useState(false);
  const [removingId, setRemovingId] = useState<number | null>(null);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAssets = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getClipBrollAssets(clipId);
      setAssets(data);
    } catch {
      setError('Could not load B-roll for this clip.');
    } finally {
      setIsLoading(false);
    }
  }, [clipId]);

  useEffect(() => {
    void loadAssets();
  }, [loadAssets]);

  const handleAutoSource = async () => {
    setIsAutoSourcing(true);
    setError(null);
    try {
      await autoSourceBroll(clipId);
      await loadAssets();
    } catch {
      setError('Auto-insert failed. Please try again.');
    } finally {
      setIsAutoSourcing(false);
    }
  };

  const handleRemove = async (brollId: number) => {
    setRemovingId(brollId);
    setError(null);
    try {
      await removeBroll(clipId, brollId);
      setAssets((current) => current.filter((asset) => asset.id !== brollId));
    } catch {
      setError('Could not remove that B-roll asset.');
    } finally {
      setRemovingId(null);
    }
  };

  const handleInserted = (asset: BrollAsset) => {
    setAssets((current) => [...current, asset]);
  };

  return (
    <GlassCard className="w-full">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-base font-semibold">
          <Film className="h-4 w-4" />
          B-roll
        </h3>
        <div className="flex gap-2">
          <GradientButton
            type="button"
            variant="outline"
            onClick={() => setIsSearchOpen(true)}
            className="px-3 py-1.5 text-xs"
          >
            <Search className="h-3.5 w-3.5" />
            Search manually
          </GradientButton>
          <GradientButton
            type="button"
            onClick={handleAutoSource}
            disabled={isAutoSourcing}
            className="px-3 py-1.5 text-xs"
          >
            {isAutoSourcing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            Auto-insert B-roll
          </GradientButton>
        </div>
      </div>

      {error && (
        <p className="mb-3 rounded-lg bg-destructive/15 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading B-roll…
        </div>
      ) : assets.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No B-roll attached yet. Auto-insert or search manually to add some.
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {assets.map((asset) => (
            <div
              key={asset.id}
              className="flex flex-col overflow-hidden rounded-xl border border-glass-border bg-background/40"
            >
              <img
                src={asset.asset_url}
                alt={asset.keyword}
                className="h-20 w-full object-cover"
              />
              <div className="flex flex-1 flex-col gap-1.5 p-2">
                <p className="truncate text-xs font-medium">{asset.keyword}</p>
                <span
                  className={cn(
                    'inline-block w-fit rounded-full px-2 py-0.5 text-[10px] font-medium capitalize',
                    asset.source === 'pexels'
                      ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                      : 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
                  )}
                >
                  {asset.source}
                </span>
                <button
                  type="button"
                  onClick={() => handleRemove(asset.id)}
                  disabled={removingId === asset.id}
                  className="mt-auto flex items-center justify-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium text-destructive transition-colors hover:bg-destructive/15 disabled:pointer-events-none disabled:opacity-50"
                >
                  {removingId === asset.id ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Trash2 className="h-3 w-3" />
                  )}
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <BrollSearchModal
        clipId={clipId}
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        onInserted={handleInserted}
      />
    </GlassCard>
  );
}
