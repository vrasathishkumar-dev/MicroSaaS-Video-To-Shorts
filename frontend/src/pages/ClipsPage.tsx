import { ClipGrid } from '@/components/clips/ClipGrid';
import { GlassCard } from '@/components/ui/GlassCard';
import { PageWrapper } from '@/components/ui/PageWrapper';

/** Lists every clip generated across the user's video projects. */
export function ClipsPage() {
  return (
    <PageWrapper className="mx-auto max-w-5xl px-4 py-10">
      <GlassCard>
        <h1 className="text-xl font-semibold text-foreground">Clips</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          All clips generated from your videos.
        </p>
        <div className="mt-6">
          <ClipGrid />
        </div>
      </GlassCard>
    </PageWrapper>
  );
}
