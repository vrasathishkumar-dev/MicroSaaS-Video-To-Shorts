import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { GlassCard } from '@/components/ui/GlassCard';
import { PageWrapper } from '@/components/ui/PageWrapper';
import {
  VideoSubmitForm,
  type ShortCustomizationSettings,
} from '@/components/videos/VideoSubmitForm';
import { ShortSamplePreview } from '@/components/videos/ShortSamplePreview';
import type { VideoProject } from '@/types';

/** Hosts the upload/URL submission form with a real-time 9:16 short sample preview. */
export function VideoSubmitPage() {
  const navigate = useNavigate();

  const [customization, setCustomization] = useState<ShortCustomizationSettings>({
    clipLength: 'auto',
    subtitleStyle: 'hormozi',
    framingMode: 'speaker_focus',
    autoBroll: true,
    brollPlacement: 'bottom',
    autoProduce: true,
  });

  function handleSuccess(video: VideoProject) {
    navigate(`/videos/${video.id}`);
  }

  return (
    <PageWrapper className="mx-auto max-w-6xl px-4 py-8">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Submission Form with AI Customization Options */}
        <div className="lg:col-span-7">
          <GlassCard>
            <div className="mb-6">
              <h1 className="text-xl font-bold tracking-tight">Create Viral Shorts</h1>
              <p className="text-sm text-muted-foreground mt-1">
                Upload a video or paste a link. Our AI will automatically detect viral hooks, transcribe, apply face-tracking 9:16 framing, insert keyword B-roll, and burn in animated captions.
              </p>
            </div>
            <VideoSubmitForm
              onSuccess={handleSuccess}
              onCustomizationChange={setCustomization}
            />
          </GlassCard>
        </div>

        {/* Right Column: Live 9:16 Short Sample Preview */}
        <div className="lg:col-span-5 lg:sticky lg:top-6">
          <ShortSamplePreview
            clipLength={customization.clipLength}
            subtitleStyle={customization.subtitleStyle}
            framingMode={customization.framingMode}
            autoBroll={customization.autoBroll}
            brollPlacement={customization.brollPlacement}
            autoProduce={customization.autoProduce}
          />
        </div>
      </div>
    </PageWrapper>
  );
}
