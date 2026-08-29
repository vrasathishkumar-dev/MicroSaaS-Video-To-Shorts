import { Link } from 'react-router-dom';
import { GlassCard } from '@/components/ui/GlassCard';
import { PageWrapper } from '@/components/ui/PageWrapper';

export function NotFoundPage() {
  return (
    <PageWrapper className="flex items-center justify-center px-4">
      <GlassCard className="text-center">
        <h1 className="mb-2 text-2xl font-semibold">Page not found</h1>
        <Link to="/" className="text-primary underline">
          Go home
        </Link>
      </GlassCard>
    </PageWrapper>
  );
}
