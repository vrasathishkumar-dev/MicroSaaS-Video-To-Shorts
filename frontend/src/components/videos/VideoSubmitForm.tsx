import type { AxiosError, AxiosProgressEvent } from 'axios';
import { useState } from 'react';
import { GradientButton } from '@/components/ui/GradientButton';
import { cn } from '@/lib/utils';
import { submitVideo } from '@/services/videoService';
import type { ApiError, VideoProject, VideoSourceType } from '@/types';

export interface VideoSubmitFormProps {
  onSuccess: (video: VideoProject) => void;
}

type SubmitMode = Extract<VideoSourceType, 'upload' | 'url'>;

const TABS: { mode: SubmitMode; label: string }[] = [
  { mode: 'upload', label: 'Upload file' },
  { mode: 'url', label: 'From URL' },
];

/**
 * Tabbed form for creating a video project either by uploading a file
 * or submitting a source URL. Shows upload progress for file uploads.
 */
export function VideoSubmitForm({ onSuccess }: VideoSubmitFormProps) {
  const [mode, setMode] = useState<SubmitMode>('upload');
  const [title, setTitle] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canSubmit =
    title.trim().length > 0 &&
    ((mode === 'upload' && file !== null) ||
      (mode === 'url' && sourceUrl.trim().length > 0));

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);
    setUploadProgress(mode === 'upload' ? 0 : null);

    try {
      const video = await submitVideo(
        {
          title: title.trim(),
          sourceType: mode,
          file: mode === 'upload' ? (file ?? undefined) : undefined,
          sourceUrl: mode === 'url' ? sourceUrl.trim() : undefined,
        },
        (progressEvent: AxiosProgressEvent) => {
          if (progressEvent.total) {
            setUploadProgress(
              Math.round((progressEvent.loaded / progressEvent.total) * 100),
            );
          }
        },
      );
      onSuccess(video);
    } catch (err) {
      const axiosError = err as AxiosError<ApiError>;
      setError(
        axiosError.response?.data?.detail ??
          'Something went wrong submitting your video. Please try again.',
      );
    } finally {
      setIsSubmitting(false);
      setUploadProgress(null);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <div className="flex gap-2 rounded-full bg-muted p-1">
        {TABS.map((tab) => (
          <button
            key={tab.mode}
            type="button"
            onClick={() => setMode(tab.mode)}
            className={cn(
              'flex-1 rounded-full px-4 py-2 text-sm font-medium transition-colors',
              mode === tab.mode
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="video-title" className="text-sm font-medium">
          Title
        </label>
        <input
          id="video-title"
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="My awesome video"
          className="w-full rounded-xl border border-input bg-background px-4 py-2.5 text-sm outline-none focus:border-ring"
          required
        />
      </div>

      {mode === 'upload' ? (
        <div className="flex flex-col gap-1.5">
          <label htmlFor="video-file" className="text-sm font-medium">
            Video file
          </label>
          <input
            id="video-file"
            type="file"
            accept="video/*"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="w-full rounded-xl border border-input bg-background px-4 py-2.5 text-sm outline-none file:mr-3 file:rounded-full file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-primary-foreground"
          />
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          <label htmlFor="video-url" className="text-sm font-medium">
            Source URL
          </label>
          <input
            id="video-url"
            type="url"
            value={sourceUrl}
            onChange={(event) => setSourceUrl(event.target.value)}
            placeholder="https://youtube.com/watch?v=..."
            className="w-full rounded-xl border border-input bg-background px-4 py-2.5 text-sm outline-none focus:border-ring"
          />
        </div>
      )}

      {uploadProgress !== null && (
        <div className="flex flex-col gap-1">
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-gradient-to-r from-gradient-from to-gradient-to transition-all"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
          <span className="text-xs text-muted-foreground">
            Uploading&hellip; {uploadProgress}%
          </span>
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      <GradientButton type="submit" disabled={!canSubmit || isSubmitting}>
        {isSubmitting ? 'Submitting…' : 'Submit video'}
      </GradientButton>
    </form>
  );
}
