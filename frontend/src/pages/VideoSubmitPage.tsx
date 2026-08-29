import { useNavigate } from 'react-router-dom';
import { GlassCard } from '@/components/ui/GlassCard';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { VideoSubmitForm } from '@/components/videos/VideoSubmitForm';
import type { VideoProject } from '@/types';

/** Hosts the upload/URL submission form for creating a new video project. */
export function VideoSubmitPage() {
  const navigate = useNavigate();

  function handleSuccess(video: VideoProject) {
    navigate(`/videos/${video.id}`);
  }

  return (
    <PageWrapper className="mx-auto max-w-xl px-4 py-10">
      <GlassCard>
        <h1 className="mb-1 text-xl font-semibold">Upload a video</h1>
        <p className="mb-6 text-sm text-muted-foreground">
          Upload a file directly or submit a source URL. We&rsquo;ll
          transcribe it and find the best highlights automatically.
        </p>
        <VideoSubmitForm onSuccess={handleSuccess} />
      </GlassCard>
    </PageWrapper>
  );
}
