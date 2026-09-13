import { useState } from 'react';
import { ListChecks } from 'lucide-react';
import { ClipGrid } from '@/components/clips/ClipGrid';
import { GlassCard } from '@/components/ui/GlassCard';
import { PageWrapper } from '@/components/ui/PageWrapper';

/** Lists every clip generated across the user's video projects. */
export function ClipsPage() {
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const toggleSelectionMode = () => {
    setSelectionMode((prev) => {
      if (prev) setSelectedIds(new Set());
      return !prev;
    });
  };

  return (
    <PageWrapper className="mx-auto max-w-5xl px-4 py-10">
      <GlassCard>
        <div className="flex items-center justify-between mb-2">
          <div>
            <h1 className="text-xl font-semibold text-foreground">Clips</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              All clips generated from your videos.
            </p>
          </div>
          <button
            id="toggle-selection-mode"
            type="button"
            onClick={toggleSelectionMode}
            className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
              selectionMode
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-glass-border bg-background/60 text-muted-foreground hover:text-foreground'
            }`}
          >
            <ListChecks className="h-4 w-4" />
            {selectionMode ? 'Done selecting' : 'Select clips'}
          </button>
        </div>
        <div className="mt-6">
          <ClipGrid
            selectionMode={selectionMode}
            selectedIds={selectedIds}
            onSelectionChange={setSelectedIds}
          />
        </div>
      </GlassCard>
    </PageWrapper>
  );
}
