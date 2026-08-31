import type { AxiosError, AxiosProgressEvent } from 'axios';
import { useState, useRef } from 'react';
import {
  Upload,
  Link as LinkIcon,
  Sparkles,
  Tv,
  Film,
  Video,
  Sliders,
  PlaySquare,
} from 'lucide-react';
import { GradientButton } from '@/components/ui/GradientButton';
import { cn } from '@/lib/utils';
import { submitVideo } from '@/services/videoService';
import type {
  ApiError,
  CaptionStylePreset,
  ClipLength,
  FramingMode,
  VideoProject,
  VideoSourceType,
} from '@/types';

export interface VideoSubmitFormProps {
  onSuccess: (video: VideoProject) => void;
}

type SubmitMode = Extract<VideoSourceType, 'upload' | 'url'>;

const PLATFORMS = [
  { name: 'YouTube', icon: PlaySquare, example: 'https://youtube.com/watch?v=...' },
  { name: 'TikTok', icon: Video, example: 'https://tiktok.com/@user/video/...' },
  { name: 'Twitch', icon: Tv, example: 'https://twitch.tv/videos/...' },
  { name: 'Vimeo', icon: Film, example: 'https://vimeo.com/...' },
];

export function VideoSubmitForm({ onSuccess }: VideoSubmitFormProps) {
  const [mode, setMode] = useState<SubmitMode>('url');
  const [title, setTitle] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [showAiSettings, setShowAiSettings] = useState(false);
  const [clipLength, setClipLength] = useState<ClipLength>('auto');
  const [subtitleStyle, setSubtitleStyle] = useState<CaptionStylePreset>('hormozi');
  const [framingMode, setFramingMode] = useState<FramingMode>('speaker_focus');
  const [autoBroll, setAutoBroll] = useState(true);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const canSubmit =
    title.trim().length > 0 &&
    ((mode === 'upload' && file !== null) ||
      (mode === 'url' && sourceUrl.trim().length > 0));

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const dropped = e.dataTransfer.files[0];
      setFile(dropped);
      setMode('upload');
      if (!title) {
        setTitle(dropped.name.replace(/\.[^/.]+$/, ''));
      }
    }
  };

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
          targetClipLength: clipLength,
          framingMode,
          captionStyle: subtitleStyle,
          autoBroll,
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
      {/* Mode switcher tabs */}
      <div className="flex gap-2 rounded-xl bg-muted/60 p-1.5 border border-glass-border">
        <button
          type="button"
          onClick={() => setMode('url')}
          className={cn(
            'flex-1 flex items-center justify-center gap-2 rounded-lg py-2.5 text-xs font-semibold transition-all',
            mode === 'url'
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <LinkIcon className="h-3.5 w-3.5" />
          Paste Video URL
        </button>
        <button
          type="button"
          onClick={() => setMode('upload')}
          className={cn(
            'flex-1 flex items-center justify-center gap-2 rounded-lg py-2.5 text-xs font-semibold transition-all',
            mode === 'upload'
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <Upload className="h-3.5 w-3.5" />
          Upload MP4 Video
        </button>
      </div>

      {/* Title */}
      <div className="flex flex-col gap-1.5">
        <label htmlFor="video-title" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Project Title
        </label>
        <input
          id="video-title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Masterclass Podcast Ep #4 - AI Revolution"
          className="w-full rounded-xl border border-glass-border bg-background/60 px-4 py-3 text-sm text-foreground outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary"
          required
        />
      </div>

      {/* Ingestion Source */}
      {mode === 'url' ? (
        <div className="flex flex-col gap-2">
          <label htmlFor="video-url" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Video Link
          </label>
          <div className="relative">
            <input
              id="video-url"
              type="url"
              value={sourceUrl}
              onChange={(e) => {
                setSourceUrl(e.target.value);
                if (!title && e.target.value) {
                  setTitle('Repurposed Short Clips');
                }
              }}
              placeholder="Paste YouTube, TikTok, Twitch, or Vimeo link..."
              className="w-full rounded-xl border border-glass-border bg-background/60 pl-4 pr-10 py-3 text-sm text-foreground outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary"
            />
            <Sparkles className="absolute right-3.5 top-3.5 h-4 w-4 text-primary pointer-events-none" />
          </div>

          {/* Supported platform badges */}
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="text-[11px]">Supported:</span>
            {PLATFORMS.map((plat) => (
              <span
                key={plat.name}
                className="inline-flex items-center gap-1 rounded-md bg-muted/60 px-2 py-0.5 text-[11px] font-medium"
              >
                <plat.icon className="h-3 w-3 text-primary" />
                {plat.name}
              </span>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Drop Video File
          </label>
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              'flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center cursor-pointer transition-all',
              isDragging
                ? 'border-primary bg-primary/10'
                : file
                  ? 'border-emerald-500/40 bg-emerald-500/5'
                  : 'border-glass-border bg-background/40 hover:border-primary/40 hover:bg-muted/30',
            )}
          >
            <input
              ref={fileInputRef}
              id="video-file"
              type="file"
              accept="video/*"
              className="hidden"
              onChange={(e) => {
                const selected = e.target.files?.[0] ?? null;
                setFile(selected);
                if (selected && !title) {
                  setTitle(selected.name.replace(/\.[^/.]+$/, ''));
                }
              }}
            />
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary mb-3">
              <Upload className="h-6 w-6" />
            </div>
            {file ? (
              <div className="space-y-1">
                <p className="text-sm font-semibold text-foreground truncate max-w-xs">
                  {file.name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {(file.size / (1024 * 1024)).toFixed(1)} MB &bull; Ready to process
                </p>
              </div>
            ) : (
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">
                  Drag & drop your video file here, or browse
                </p>
                <p className="text-xs text-muted-foreground">
                  MP4, MOV, MKV, or WEBM up to 2GB
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* AI Settings Toggle */}
      <div className="rounded-xl border border-glass-border bg-glass-bg p-3 backdrop-blur-md">
        <button
          type="button"
          onClick={() => setShowAiSettings(!showAiSettings)}
          className="flex w-full items-center justify-between text-xs font-semibold text-foreground"
        >
          <span className="flex items-center gap-1.5 text-primary">
            <Sliders className="h-3.5 w-3.5" />
            AI Clip Customization Options
          </span>
          <span className="text-muted-foreground text-[11px]">
            {showAiSettings ? 'Hide Options ▲' : 'Show Options ▼'}
          </span>
        </button>

        {showAiSettings && (
          <div className="mt-4 space-y-4 pt-3 border-t border-glass-border">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Target Short Length
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: 'auto', label: 'Auto (30-50s)' },
                  { id: 'fast', label: 'Fast (15-30s)' },
                  { id: 'in_depth', label: 'In-Depth (45-60s)' },
                ].map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setClipLength(opt.id as ClipLength)}
                    className={cn(
                      'rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all',
                      clipLength === opt.id
                        ? 'border-primary bg-primary/15 text-primary'
                        : 'border-glass-border bg-background/50 text-muted-foreground hover:text-foreground',
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Default Caption Style Preset
              </label>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {[
                  { id: 'hormozi', name: 'Hormozi Pop (Yellow/Lime)' },
                  { id: 'neon', name: 'Neon Cyber (Glowing Cyan)' },
                  { id: 'karaoke', name: 'Karaoke Wave (Word Highlight)' },
                  { id: 'bold_box', name: 'Viral Box (Clean Overlay)' },
                ].map((style) => (
                  <button
                    key={style.id}
                    type="button"
                    onClick={() => setSubtitleStyle(style.id as CaptionStylePreset)}
                    className={cn(
                      'rounded-lg border px-2.5 py-2 text-left text-xs font-medium transition-all',
                      subtitleStyle === style.id
                        ? 'border-primary bg-primary/15 text-primary'
                        : 'border-glass-border bg-background/50 text-muted-foreground hover:text-foreground',
                    )}
                  >
                    {style.name}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Vertical Framing
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: 'speaker_focus', label: 'Speaker Focus' },
                  { id: 'dynamic_blur', label: 'Dynamic Blur' },
                  { id: 'fit', label: 'Fit (Letterbox)' },
                ].map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setFramingMode(opt.id as FramingMode)}
                    className={cn(
                      'rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all',
                      framingMode === opt.id
                        ? 'border-primary bg-primary/15 text-primary'
                        : 'border-glass-border bg-background/50 text-muted-foreground hover:text-foreground',
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="button"
              onClick={() => setAutoBroll((on) => !on)}
              aria-pressed={autoBroll}
              className={cn(
                'flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-left transition-all',
                autoBroll
                  ? 'border-primary bg-primary/15'
                  : 'border-glass-border bg-background/50',
              )}
            >
              <span className="space-y-0.5">
                <span className="block text-xs font-medium text-foreground">
                  Auto B-Roll
                </span>
                <span className="block text-[11px] text-muted-foreground">
                  Adds matching Pexels &amp; Pixabay footage to each short
                </span>
              </span>
              <span
                className={cn(
                  'ml-3 flex h-5 w-9 shrink-0 items-center rounded-full px-0.5 transition-colors',
                  autoBroll ? 'bg-primary' : 'bg-muted',
                )}
              >
                <span
                  className={cn(
                    'h-4 w-4 rounded-full bg-white transition-transform',
                    autoBroll ? 'translate-x-4' : 'translate-x-0',
                  )}
                />
              </span>
            </button>
          </div>
        )}
      </div>

      {uploadProgress !== null && (
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Uploading media to processing engine...</span>
            <span className="font-semibold text-primary">{uploadProgress}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-gradient-to-r from-gradient-from to-gradient-to transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <p className="rounded-xl bg-destructive/15 p-3 text-xs text-destructive">
          {error}
        </p>
      )}

      <GradientButton
        type="submit"
        disabled={!canSubmit || isSubmitting}
        className="w-full py-3.5 text-sm font-bold gap-2 shadow-lg shadow-primary/20"
      >
        <Sparkles className="h-4 w-4" />
        {isSubmitting ? 'Ingesting & Generating Shorts…' : 'Generate Viral Shorts'}
      </GradientButton>
    </form>
  );
}
