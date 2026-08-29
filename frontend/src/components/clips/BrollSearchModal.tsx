import * as Dialog from '@radix-ui/react-dialog';
import { Loader2, Search, X } from 'lucide-react';
import { useState } from 'react';
import type { FormEvent } from 'react';
import { GradientButton } from '@/components/ui/GradientButton';
import { cn } from '@/lib/utils';
import { insertBroll, searchBroll } from '@/services/brollService';
import type { BrollSearchResult } from '@/services/brollService';
import type { BrollAsset, BrollSource } from '@/types';

type SourceFilter = 'all' | BrollSource;

const SOURCE_FILTERS: { value: SourceFilter; label: string }[] = [
  { value: 'all', label: 'All sources' },
  { value: 'pexels', label: 'Pexels' },
  { value: 'pixabay', label: 'Pixabay' },
];

export interface BrollSearchModalProps {
  clipId: number;
  isOpen: boolean;
  onClose: () => void;
  onInserted: (asset: BrollAsset) => void;
}

/**
 * Modal for manually searching Pexels/Pixabay for B-roll and attaching a
 * chosen result to the current clip. Self-contained: manages its own
 * search/insert state independent of its parent (BrollPanel).
 */
export function BrollSearchModal({
  clipId,
  isOpen,
  onClose,
  onInserted,
}: BrollSearchModalProps) {
  const [query, setQuery] = useState('');
  const [source, setSource] = useState<SourceFilter>('all');
  const [results, setResults] = useState<BrollSearchResult[]>([]);
  const [positionStart, setPositionStart] = useState(0);
  const [positionEnd, setPositionEnd] = useState(3);
  const [isSearching, setIsSearching] = useState(false);
  const [insertingKey, setInsertingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const resultKey = (result: BrollSearchResult): string =>
    `${result.source}:${result.source_asset_id}`;

  const handleSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!query.trim()) {
      return;
    }

    setIsSearching(true);
    setError(null);
    try {
      const data = await searchBroll(query.trim(), source === 'all' ? undefined : source);
      setResults(data);
    } catch {
      setError('Search failed. Please try again.');
    } finally {
      setIsSearching(false);
    }
  };

  const handleInsert = async (result: BrollSearchResult) => {
    if (positionEnd <= positionStart) {
      setError('End time must be after start time.');
      return;
    }

    setInsertingKey(resultKey(result));
    setError(null);
    try {
      const asset = await insertBroll(clipId, {
        source: result.source,
        source_asset_id: result.source_asset_id,
        asset_url: result.asset_url,
        keyword: result.keyword,
        position_start: positionStart,
        position_end: positionEnd,
      });
      onInserted(asset);
      onClose();
    } catch {
      setError('Could not insert that clip. Please try again.');
    } finally {
      setInsertingKey(null);
    }
  };

  return (
    <Dialog.Root open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[85vh] w-[95vw] max-w-2xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl border border-glass-border bg-glass-bg p-6 shadow-2xl backdrop-blur-lg">
          <div className="mb-4 flex items-center justify-between">
            <Dialog.Title className="text-lg font-semibold">
              Search B-roll
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                className="rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </Dialog.Close>
          </div>

          <form onSubmit={handleSearch} className="mb-4 flex flex-wrap gap-2">
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search keyword, e.g. city skyline"
              className="min-w-[10rem] flex-1 rounded-full border border-glass-border bg-background/50 px-4 py-2 text-sm outline-none focus:border-primary"
            />
            <select
              value={source}
              onChange={(event) => setSource(event.target.value as SourceFilter)}
              className="rounded-full border border-glass-border bg-background/50 px-3 py-2 text-sm outline-none focus:border-primary"
            >
              {SOURCE_FILTERS.map((filter) => (
                <option key={filter.value} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </select>
            <GradientButton type="submit" disabled={isSearching} className="px-4 py-2">
              {isSearching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              Search
            </GradientButton>
          </form>

          <div className="mb-4 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <label className="flex items-center gap-2">
              Start (s)
              <input
                type="number"
                min={0}
                value={positionStart}
                onChange={(event) => setPositionStart(Number(event.target.value))}
                className="w-20 rounded-md border border-glass-border bg-background/50 px-2 py-1 outline-none focus:border-primary"
              />
            </label>
            <label className="flex items-center gap-2">
              End (s)
              <input
                type="number"
                min={0}
                value={positionEnd}
                onChange={(event) => setPositionEnd(Number(event.target.value))}
                className="w-20 rounded-md border border-glass-border bg-background/50 px-2 py-1 outline-none focus:border-primary"
              />
            </label>
          </div>

          {error && (
            <p className="mb-4 rounded-lg bg-destructive/15 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}

          {results.length === 0 && !isSearching ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Search for a keyword to see B-roll suggestions.
            </p>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {results.map((result) => {
                const key = resultKey(result);
                const isInserting = insertingKey === key;
                return (
                  <div
                    key={key}
                    className="flex flex-col overflow-hidden rounded-xl border border-glass-border bg-background/40"
                  >
                    <img
                      src={result.asset_url}
                      alt={result.keyword}
                      className="h-24 w-full object-cover"
                    />
                    <div className="flex flex-1 flex-col gap-2 p-2">
                      <div>
                        <p className="truncate text-xs font-medium">{result.keyword}</p>
                        <span
                          className={cn(
                            'inline-block rounded-full px-2 py-0.5 text-[10px] font-medium capitalize',
                            result.source === 'pexels'
                              ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                              : 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
                          )}
                        >
                          {result.source}
                        </span>
                      </div>
                      <GradientButton
                        type="button"
                        disabled={insertingKey !== null}
                        onClick={() => handleInsert(result)}
                        className="mt-auto px-3 py-1.5 text-xs"
                      >
                        {isInserting ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          'Insert'
                        )}
                      </GradientButton>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
