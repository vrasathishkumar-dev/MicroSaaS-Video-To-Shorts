import { getApiErrorMessage } from '@/lib/apiError';
import type { AxiosProgressEvent } from 'axios';
import { useState, useRef, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Upload,
  Link as LinkIcon,
  Sparkles,
  Tv,
  Film,
  Video,
  Sliders,
  PlaySquare,
  Wand2,
  PanelBottom,
  PanelTop,
  PictureInPicture2,
  Rows2,
  CheckCircle2,
  ExternalLink,
} from 'lucide-react';
import { YouTubeCaptionPanel } from '@/components/clips/YouTubeCaptionPanel';
import { GradientButton } from '@/components/ui/GradientButton';
import { cn } from '@/lib/utils';
import { getClipPreviewUrl } from '@/services/clipService';
import { submitVideo, uploadShortVideo } from '@/services/videoService';
import type {
  BrollPlacement,
  CaptionStylePreset,
  ClipLength,
  FramingMode,
  UploadShortResponse,
  VideoProject,
  YouTubeCaptionTone,
} from '@/types';

export interface ShortCustomizationSettings {
  clipLength: ClipLength;
  subtitleStyle: CaptionStylePreset;
  framingMode: FramingMode;
  autoBroll: boolean;
  brollPlacement: BrollPlacement;
  autoProduce: boolean;
}

export interface VideoSubmitFormProps {
  onSuccess: (video: VideoProject) => void;
  onCustomizationChange?: (settings: ShortCustomizationSettings) => void;
}

const BROLL_PLACEMENT_OPTIONS: Array<{
  id: BrollPlacement;
  label: string;
  sub: string;
  icon: typeof PanelBottom;
}> = [
  {
    id: 'bottom',
    label: 'Bottom Split (25%)',
    sub: 'Bottom 25% cinematic strip',
    icon: PanelBottom,
  },
  {
    id: 'split',
    label: 'Split Screen (50/50)',
    sub: '50/50 dual video stack',
    icon: Rows2,
  },
  {
    id: 'bottom_right',
    label: 'Corner PIP',
    sub: 'Floating picture-in-picture',
    icon: PictureInPicture2,
  },
  {
    id: 'top',
    label: 'Top Split (25%)',
    sub: 'Top 25% header banner',
    icon: PanelTop,
  },
];

type SubmitMode = 'url' | 'upload' | 'short';

const PLATFORMS = [
  { name: 'YouTube', icon: PlaySquare, example: 'https://youtube.com/watch?v=...' },
  { name: 'TikTok', icon: Video, example: 'https://tiktok.com/@user/video/...' },
  { name: 'Twitch', icon: Tv, example: 'https://twitch.tv/videos/...' },
  { name: 'Vimeo', icon: Film, example: 'https://vimeo.com/...' },
];

export function VideoSubmitForm({
  onSuccess,
  onCustomizationChange,
}: VideoSubmitFormProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialUrl = searchParams.get('url')?.trim() ?? '';

  const [mode, setMode] = useState<SubmitMode>('url');
  const [title, setTitle] = useState(initialUrl ? 'Repurposed Short Clips' : '');
  const [file, setFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState(initialUrl);
  const [customShortCaption, setCustomShortCaption] = useState('');
  const [shortTone, setShortTone] = useState<YouTubeCaptionTone>('viral');
  const [uploadedShortResult, setUploadedShortResult] =
    useState<UploadShortResponse | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [showAiSettings, setShowAiSettings] = useState(false);
  const [clipLength, setClipLength] = useState<ClipLength>('auto');
  const [subtitleStyle, setSubtitleStyle] = useState<CaptionStylePreset>('hormozi');
  const [framingMode, setFramingMode] = useState<FramingMode>('speaker_focus');
  const [autoBroll, setAutoBroll] = useState(true);
  const [brollPlacement, setBrollPlacement] = useState<BrollPlacement>('bottom');
  const [autoProduce, setAutoProduce] = useState(true);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    onCustomizationChange?.({
      clipLength,
      subtitleStyle,
      framingMode,
      autoBroll,
      brollPlacement,
      autoProduce,
    });
  }, [
    clipLength,
    subtitleStyle,
    framingMode,
    autoBroll,
    brollPlacement,
    autoProduce,
    onCustomizationChange,
  ]);

  useEffect(() => {
    const paramUrl = searchParams.get('url')?.trim();
    if (paramUrl) {
      setMode('url');
      setSourceUrl(paramUrl);
      setTitle((prev) => prev || 'Repurposed Short Clips');
    }
  }, [searchParams]);

  const canSubmit =
    mode === 'short'
      ? file !== null
      : title.trim().length > 0 &&
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
      if (mode === 'url') {
        setMode('upload');
      }
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
    setUploadProgress(mode === 'upload' || mode === 'short' ? 0 : null);

    try {
      if (mode === 'short' && file) {
        const res = await uploadShortVideo(
          {
            file,
            title: title.trim() || file.name.replace(/\.[^/.]+$/, ''),
            captionText: customShortCaption.trim() || undefined,
            tone: shortTone,
            framingMode,
            captionStyle: subtitleStyle,
            autoBroll: false,
            brollPlacement,
            autoRender: true,
          },
          (progressEvent: AxiosProgressEvent) => {
            if (progressEvent.total) {
              setUploadProgress(
                Math.round((progressEvent.loaded / progressEvent.total) * 100),
              );
            }
          },
        );
        setUploadedShortResult(res);
        return;
      }

      const video = await submitVideo(
        {
          title: title.trim(),
          sourceType: mode === 'url' ? 'url' : 'upload',
          file: mode === 'upload' ? (file ?? undefined) : undefined,
          sourceUrl: mode === 'url' ? sourceUrl.trim() : undefined,
          targetClipLength: clipLength,
          framingMode,
          captionStyle: subtitleStyle,
          autoBroll,
          brollPlacement,
          autoProduce,
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
      setError(
        getApiErrorMessage(
          err,
          'Something went wrong submitting your video. Please try again.',
        ),
      );
    } finally {
      setIsSubmitting(false);
      setUploadProgress(null);
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        {/* Mode switcher tabs */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-1.5 rounded-xl bg-muted/60 p-1.5 border border-glass-border">
          <button
            type="button"
            onClick={() => {
              setMode('url');
              setUploadedShortResult(null);
            }}
            className={cn(
              'flex items-center justify-center gap-1.5 rounded-lg py-2.5 px-2 text-xs font-semibold transition-all cursor-pointer',
              mode === 'url'
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <LinkIcon className="h-3.5 w-3.5 shrink-0" />
            <span>Paste Video URL</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setMode('upload');
              setUploadedShortResult(null);
            }}
            className={cn(
              'flex items-center justify-center gap-1.5 rounded-lg py-2.5 px-2 text-xs font-semibold transition-all cursor-pointer',
              mode === 'upload'
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Upload className="h-3.5 w-3.5 shrink-0" />
            <span>Upload MP4 Video</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setMode('short');
              setUploadedShortResult(null);
            }}
            className={cn(
              'flex items-center justify-center gap-1.5 rounded-lg py-2.5 px-2 text-xs font-semibold transition-all cursor-pointer',
              mode === 'short'
                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <PlaySquare className="h-3.5 w-3.5 shrink-0 text-rose-400" />
            <span>Upload Short &amp; Caption</span>
          </button>
        </div>

        {mode === 'short' && (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-200 space-y-1">
            <p className="font-bold flex items-center gap-1.5 text-rose-300">
              <PlaySquare className="h-3.5 w-3.5" />
              Direct Short Upload: Generate YouTube Caption &amp; See Content
            </p>
            <p className="text-[11px] text-muted-foreground">
              Uploading an already-trimmed Short (&le;60s)? Drop it below to automatically extract/generate YouTube captions, preview spoken subtitles, and copy ready-to-post YouTube title, description, and hashtags.
            </p>
          </div>
        )}

        {/* Title */}
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="video-title"
            className="text-xs font-semibold text-muted-foreground uppercase tracking-wider"
          >
            {mode === 'short' ? 'Short Title (Optional)' : 'Project Title'}
          </label>
          <input
            id="video-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={
              mode === 'short'
                ? 'e.g. 3 AI Secrets Nobody Tells You'
                : 'e.g. Masterclass Podcast Ep #4 - AI Revolution'
            }
            className="w-full rounded-xl border border-glass-border bg-background/60 px-4 py-3 text-sm text-foreground outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary"
            required={mode !== 'short'}
          />
        </div>

        {/* Ingestion Source */}
        {mode === 'url' ? (
          <div className="flex flex-col gap-2">
            <label
              htmlFor="video-url"
              className="text-xs font-semibold text-muted-foreground uppercase tracking-wider"
            >
              Podcast / YouTube Video Link
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
                placeholder="Paste YouTube podcast, TikTok, Twitch, or Vimeo link..."
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
          <div className="flex flex-col gap-3">
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              {mode === 'short' ? 'Drop Your Short Video (MP4 / MOV)' : 'Drop Video File'}
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
                    Drag &amp; drop your video file here, or browse
                  </p>
                  <p className="text-xs text-muted-foreground">
                    MP4, MOV, MKV, or WEBM up to 2GB
                  </p>
                </div>
              )}
            </div>

            {mode === 'short' && (
              <div className="space-y-3 rounded-xl border border-glass-border bg-background/40 p-3.5">
                <div className="space-y-1.5">
                  <label
                    htmlFor="short-custom-caption"
                    className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block"
                  >
                    Custom Spoken Script / Caption Text (Optional — leave blank to auto-transcribe)
                  </label>
                  <textarea
                    id="short-custom-caption"
                    rows={2}
                    value={customShortCaption}
                    onChange={(e) => setCustomShortCaption(e.target.value)}
                    placeholder="Optional: Paste or type the spoken script if you want exact custom subtitles burned in..."
                    className="w-full rounded-xl border border-glass-border bg-background/60 p-3 text-xs text-foreground outline-none focus:border-primary"
                  />
                </div>

                <div className="space-y-1.5">
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block">
                    YouTube Caption Tone
                  </span>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {(
                      [
                        { id: 'viral', label: '🔥 Viral' },
                        { id: 'educational', label: '🧠 Educational' },
                        { id: 'storytelling', label: '📖 Story' },
                        { id: 'professional', label: '💼 Pro' },
                      ] as const
                    ).map((t) => (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => setShortTone(t.id)}
                        className={cn(
                          'rounded-lg border py-1.5 px-2 text-xs font-semibold transition-all cursor-pointer',
                          shortTone === t.id
                            ? 'border-primary bg-primary/15 text-primary'
                            : 'border-glass-border bg-background/60 text-muted-foreground hover:text-foreground',
                        )}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* End-to-End Viral Production + B-Roll Toggle (for long-form URL/Upload) */}
        {mode !== 'short' && (
          <button
            type="button"
            onClick={() => setAutoProduce((on) => !on)}
            aria-pressed={autoProduce}
            className={cn(
              'flex w-full items-center justify-between rounded-xl border px-3.5 py-3 text-left transition-all',
              autoProduce
                ? 'border-primary/50 bg-primary/10 shadow-sm'
                : 'border-glass-border bg-background/50',
            )}
          >
            <span className="flex items-center gap-2.5">
              <Wand2 className="h-4 w-4 text-primary shrink-0" />
              <span className="space-y-0.5">
                <span className="block text-xs font-semibold text-foreground">
                  End-to-End Viral Production + B-Roll
                </span>
                <span className="block text-[11px] text-muted-foreground">
                  Automatically cut viral hooks, insert keyword-synced B-roll &amp;
                  render 9:16 MP4s
                </span>
              </span>
            </span>
            <span
              className={cn(
                'ml-3 flex h-5 w-9 shrink-0 items-center rounded-full px-0.5 transition-colors',
                autoProduce ? 'bg-primary' : 'bg-muted',
              )}
            >
              <span
                className={cn(
                  'h-4 w-4 rounded-full bg-white transition-transform',
                  autoProduce ? 'translate-x-4' : 'translate-x-0',
                )}
              />
            </span>
          </button>
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

              {autoBroll && (
                <div className="space-y-2 rounded-xl border border-primary/20 bg-primary/5 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                      <Film className="h-3.5 w-3.5 text-primary" />
                      B-Roll Layout / Positioning
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      Where footage appears in 9:16 canvas
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {BROLL_PLACEMENT_OPTIONS.map((opt) => {
                      const Icon = opt.icon;
                      const isSelected = brollPlacement === opt.id;
                      return (
                        <button
                          key={opt.id}
                          type="button"
                          onClick={() => setBrollPlacement(opt.id)}
                          className={cn(
                            'flex flex-col items-start gap-1 rounded-lg border p-2.5 text-left transition-all',
                            isSelected
                              ? 'border-primary bg-primary/20 text-primary shadow-sm ring-1 ring-primary/40'
                              : 'border-glass-border bg-background/60 text-muted-foreground hover:border-glass-border/80 hover:text-foreground',
                          )}
                        >
                          <div className="flex w-full items-center justify-between">
                            <Icon
                              className={cn(
                                'h-4 w-4 shrink-0',
                                isSelected ? 'text-primary' : 'text-muted-foreground',
                              )}
                            />
                            {isSelected && (
                              <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                            )}
                          </div>
                          <span className="text-xs font-bold leading-tight text-foreground">
                            {opt.label}
                          </span>
                          <span className="text-[10px] leading-tight text-muted-foreground">
                            {opt.sub}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
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
          {isSubmitting
            ? mode === 'short'
              ? 'Uploading Short & Generating YouTube Captions…'
              : 'Ingesting & Producing Viral Shorts…'
            : mode === 'short'
              ? 'Upload Short & Generate YouTube Caption'
              : autoProduce
                ? 'Produce Viral Shorts + B-Roll'
                : 'Generate Viral Shorts'}
        </GradientButton>
      </form>

      {/* Instant Content & YouTube Caption Result when uploading a Short directly */}
      {uploadedShortResult && (
        <div className="space-y-4 pt-4 border-t border-glass-border animate-in fade-in duration-300">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
              <div>
                <h3 className="text-sm font-bold text-foreground">
                  Short Uploaded &amp; YouTube Captions Generated!
                </h3>
                <p className="text-xs text-muted-foreground">
                  Preview your Short content below, copy your YouTube metadata, or open in the full 9:16 Clip Studio.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() =>
                navigate(`/clips/${uploadedShortResult.clip.id}?tab=youtube`)
              }
              className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-3.5 py-2 text-xs font-bold text-white shadow hover:opacity-90 cursor-pointer"
            >
              <span>Open in Clip Studio</span>
              <ExternalLink className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Inline 9:16 Video Content Preview */}
          <div className="rounded-2xl border border-glass-border bg-black/80 p-4 flex flex-col items-center gap-3">
            <span className="text-xs font-semibold text-muted-foreground">
              Uploaded Short Video Content Preview ({uploadedShortResult.clip.title})
            </span>
            <div className="aspect-[9/16] w-full max-w-[260px] overflow-hidden rounded-xl border border-glass-border bg-black">
              <video
                src={getClipPreviewUrl(uploadedShortResult.clip.id)}
                controls
                playsInline
                className="h-full w-full object-contain"
              />
            </div>
          </div>

          <YouTubeCaptionPanel
            clipId={uploadedShortResult.clip.id}
            initialPackage={uploadedShortResult.youtube_package}
          />
        </div>
      )}
    </div>
  );
}
