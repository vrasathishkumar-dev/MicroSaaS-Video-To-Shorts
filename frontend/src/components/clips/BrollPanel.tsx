import {
  Film,
  Loader2,
  PanelBottom,
  PanelTop,
  PictureInPicture2,
  Rows2,
  Search,
  Sparkles,
  Trash2,
} from 'lucide-react';
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
import type { BrollAsset, BrollPlacement } from '@/types';

export interface BrollPanelProps {
  clipId: number;
  /** Where B-roll sits on screen for this clip -- one choice for the whole clip. */
  placement: BrollPlacement;
  onPlacementChange: (placement: BrollPlacement) => void;
}

const PLACEMENT_OPTIONS: Array<{
  value: BrollPlacement;
  label: string;
  icon: typeof PictureInPicture2;
}> = [
  { value: 'bottom_right', label: 'Corner', icon: PictureInPicture2 },
  { value: 'top', label: 'Top', icon: PanelTop },
  { value: 'bottom', label: 'Bottom', icon: PanelBottom },
  { value: 'split', label: 'Split', icon: Rows2 },
];

/**
 * Self-contained B-roll management panel for a single clip. Fetches its own
 * data on mount, lets the user auto-source B-roll, search for it manually,
 * remove an attached asset, or change where B-roll sits on screen. Meant to
 * be dropped into a clip editor layout as
 * `<BrollPanel clipId={clip.id} placement={p} onPlacementChange={fn} />`.
 */
export function BrollPanel({ clipId, placement, onPlacementChange }: BrollPanelProps) {
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

      <div className="mb-4 flex items-center gap-1.5 p-1 w-fit rounded-full bg-muted/60 border border-glass-border text-[11px] font-medium">
        <span className="pl-2 pr-1 text-muted-foreground">Placement:</span>
        {PLACEMENT_OPTIONS.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            type="button"
            onClick={() => onPlacementChange(value)}
            className={cn(
              'flex items-center gap-1 px-3 py-1 rounded-full transition-all',
              placement === value
                ? 'bg-primary text-white shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <Icon className="h-3 w-3" />
            {label}
          </button>
        ))}
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
              <div
                className="relative h-20 w-full overflow-hidden bg-muted"
                onMouseEnter={(event) => {
                  const video = event.currentTarget.querySelector('video');
                  void video?.play().catch(() => undefined);
                }}
                onMouseLeave={(event) => {
                  const video = event.currentTarget.querySelector('video');
                  video?.pause();
                }}
              >
                {/* Only the first frame is fetched until the tile is
                    hovered: `asset_url` is the full-resolution render
                    file, and autoplaying one per attached asset makes the
                    panel crawl. */}
                <video
                  src={asset.asset_url}
                  muted
                  loop
                  playsInline
                  preload="metadata"
                  className="h-full w-full object-cover"
                />
                <div className="absolute top-1.5 left-1.5 rounded bg-black/60 px-1.5 py-0.5 text-[9px] font-mono text-white/90">
                  {asset.position_start}s - {asset.position_end}s
                </div>
              </div>
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
