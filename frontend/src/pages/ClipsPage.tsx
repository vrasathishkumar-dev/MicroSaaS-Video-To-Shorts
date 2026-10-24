import { PlaySquare, Upload } from 'lucide-react';
import { Link } from 'react-router-dom';
import { ClipGrid } from '@/components/clips/ClipGrid';
import { GlassCard } from '@/components/ui/GlassCard';
import { PageWrapper } from '@/components/ui/PageWrapper';

/** Lists every clip generated across the user's video projects. */
export function ClipsPage() {
  return (
    <PageWrapper className="mx-auto max-w-5xl px-4 py-10">
      <GlassCard>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-foreground">Clips &amp; Shorts Library</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Open any Short to edit 9:16 framing, burn in animated subtitles, generate YouTube captions &amp; preview content.
            </p>
          </div>
          <Link
            to="/videos/new"
            className="inline-flex items-center gap-2 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-2.5 text-xs font-bold text-rose-300 transition-all hover:bg-rose-500/20"
          >
            <Upload className="h-3.5 w-3.5 text-rose-400" />
            <PlaySquare className="h-3.5 w-3.5 text-rose-400" />
            <span>Upload Short &amp; Generate YouTube Caption</span>
          </Link>
        </div>
        <div className="mt-6">
          <ClipGrid />
        </div>
      </GlassCard>
    </PageWrapper>
  );
}
