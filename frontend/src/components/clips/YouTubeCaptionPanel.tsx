import { useCallback, useEffect, useState } from 'react';
import {
  Check,
  CheckCircle2,
  Copy,
  Download,
  Eye,
  FileText,
  Hash,
  Loader2,
  PlaySquare,
  RefreshCw,
  Sparkles,
  Tag,
} from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { cn } from '@/lib/utils';
import {
  generateYouTubeCaptionPackage,
  getYouTubeCaptionPackage,
} from '@/services/exportService';
import type { YouTubeCaptionPackage, YouTubeCaptionTone } from '@/types';

export interface YouTubeCaptionPanelProps {
  clipId: number;
  initialPackage?: YouTubeCaptionPackage | null;
  onCaptionApplied?: (newCaptionText: string) => void;
}

const TONE_OPTIONS: Array<{ id: YouTubeCaptionTone; label: string; desc: string }> = [
  { id: 'viral', label: '🔥 Viral Hook', desc: 'High-CTR curiosity title & punchy tags' },
  { id: 'educational', label: '🧠 Educational', desc: 'Clear value takeaways & structured notes' },
  { id: 'storytelling', label: '📖 Storytelling', desc: 'Narrative tension & curiosity gap' },
  { id: 'professional', label: '💼 Professional', desc: 'Clean authority headline & summary' },
];

export function YouTubeCaptionPanel({
  clipId,
  initialPackage = null,
  onCaptionApplied,
}: YouTubeCaptionPanelProps) {
  const [pkg, setPkg] = useState<YouTubeCaptionPackage | null>(initialPackage);
  const [tone, setTone] = useState<YouTubeCaptionTone>('viral');
  const [includeHashtags, setIncludeHashtags] = useState(true);
  const [includeTimestamps, setIncludeTimestamps] = useState(true);
  const [customCaption, setCustomCaption] = useState('');
  const [editableTitle, setEditableTitle] = useState('');
  const [editableDescription, setEditableDescription] = useState('');
  const [activeSubView, setActiveSubView] = useState<'metadata' | 'content' | 'preview'>(
    'metadata',
  );
  const [isLoading, setIsLoading] = useState(!initialPackage);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const syncEditableFields = useCallback((data: YouTubeCaptionPackage) => {
    setPkg(data);
    setEditableTitle(data.youtube_title);
    setEditableDescription(data.youtube_description);
    setCustomCaption(data.caption_text);
  }, []);

  const loadInitialPackage = useCallback(async () => {
    if (initialPackage && initialPackage.clip_id === clipId) {
      syncEditableFields(initialPackage);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await getYouTubeCaptionPackage(clipId, 'viral');
      syncEditableFields(data);
    } catch {
      setError('Could not load YouTube caption package. Click Generate to retry.');
    } finally {
      setIsLoading(false);
    }
  }, [clipId, initialPackage, syncEditableFields]);

  useEffect(() => {
    void loadInitialPackage();
  }, [loadInitialPackage]);

  const handleGenerate = async (
    selectedTone: YouTubeCaptionTone = tone,
    applyCaption: boolean = false,
  ) => {
    setIsGenerating(true);
    setError(null);
    try {
      const data = await generateYouTubeCaptionPackage(clipId, {
        tone: selectedTone,
        include_hashtags: includeHashtags,
        include_timestamps: includeTimestamps,
        custom_caption_text: applyCaption ? customCaption : undefined,
        apply_caption_to_clip: applyCaption,
      });
      syncEditableFields(data);
      if (applyCaption && onCaptionApplied) {
        onCaptionApplied(data.caption_text);
      }
    } catch {
      setError('Failed to generate YouTube caption package. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => {
        setCopiedKey((curr) => (curr === key ? null : curr));
      }, 2000);
    } catch {
      // Fallback for environments without clipboard API
    }
  };

  const handleDownloadSrt = () => {
    if (!pkg?.srt_content) return;
    const blob = new Blob([pkg.srt_content], { type: 'text/plain;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `short-${clipId}-captions.srt`;
    document.body.appendChild(link);
    link.click();
    setTimeout(() => {
      link.remove();
      window.URL.revokeObjectURL(url);
    }, 2000);
  };

  if (isLoading) {
    return (
      <GlassCard className="flex items-center justify-center gap-2 py-10 text-xs text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        <span>Generating YouTube Shorts caption &amp; content package…</span>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-glass-border pb-3">
        <div>
          <div className="flex items-center gap-2">
            <PlaySquare className="h-4 w-4 text-rose-500" />
            <h3 className="text-base font-bold text-foreground">
              YouTube Shorts Caption &amp; Content Studio
            </h3>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Generate YouTube Shorts title, description, hashtags, SEO tags, and inspect spoken content &amp; timed subtitles.
          </p>
        </div>

        {pkg?.specs_check && (
          <span
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-semibold',
              pkg.specs_check.is_youtube_short_ready
                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                : 'bg-amber-500/15 text-amber-400 border border-amber-500/30',
            )}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            {pkg.specs_check.is_youtube_short_ready
              ? `YouTube Shorts Ready (${pkg.specs_check.duration_seconds}s • 9:16)`
              : `Duration ${pkg.specs_check.duration_seconds}s (Max 60s)`}
          </span>
        )}
      </div>

      {/* Tone Selector & Regenerate Controls */}
      <div className="space-y-3 rounded-xl border border-glass-border bg-background/40 p-3.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            Caption &amp; Metadata Style
          </span>
          <div className="flex items-center gap-3 text-xs">
            <label className="inline-flex items-center gap-1.5 cursor-pointer text-muted-foreground hover:text-foreground">
              <input
                type="checkbox"
                checked={includeHashtags}
                onChange={(e) => setIncludeHashtags(e.target.checked)}
                className="h-3.5 w-3.5 rounded accent-primary"
              />
              <span>Hashtags</span>
            </label>
            <label className="inline-flex items-center gap-1.5 cursor-pointer text-muted-foreground hover:text-foreground">
              <input
                type="checkbox"
                checked={includeTimestamps}
                onChange={(e) => setIncludeTimestamps(e.target.checked)}
                className="h-3.5 w-3.5 rounded accent-primary"
              />
              <span>Timestamps</span>
            </label>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {TONE_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => {
                setTone(opt.id);
                void handleGenerate(opt.id, false);
              }}
              className={cn(
                'flex flex-col items-start rounded-lg border p-2.5 text-left transition-all cursor-pointer',
                tone === opt.id
                  ? 'border-primary bg-primary/15 text-foreground shadow-sm'
                  : 'border-glass-border bg-background/60 text-muted-foreground hover:text-foreground',
              )}
            >
              <span className="text-xs font-bold">{opt.label}</span>
              <span className="text-[10px] text-muted-foreground mt-0.5 leading-tight">
                {opt.desc}
              </span>
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
          <GradientButton
            type="button"
            onClick={() => void handleGenerate(tone, false)}
            disabled={isGenerating}
            className="gap-1.5 py-2 px-4 text-xs font-semibold"
          >
            {isGenerating ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            {isGenerating ? 'Generating YouTube Caption…' : 'Generate YouTube Caption'}
          </GradientButton>

          {pkg && (
            <button
              type="button"
              onClick={() =>
                void handleCopy(
                  'all',
                  `${editableTitle}\n\n${editableDescription}\n\nTags: ${pkg.tags.join(', ')}`,
                )
              }
              className="inline-flex items-center gap-1.5 rounded-lg border border-primary/40 bg-primary/10 px-3 py-2 text-xs font-semibold text-primary hover:bg-primary/20 transition-colors cursor-pointer"
            >
              {copiedKey === 'all' ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                  <span>Copied Full Package!</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  <span>Copy Full YouTube Package</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {error && (
        <p className="rounded-lg bg-destructive/15 p-2.5 text-xs text-destructive">
          {error}
        </p>
      )}

      {/* Sub-navigation: YouTube Metadata vs See Content & Subtitles vs Feed Preview */}
      {pkg && (
        <>
          <div className="flex gap-1.5 rounded-xl bg-muted/60 p-1 border border-glass-border">
            <button
              type="button"
              onClick={() => setActiveSubView('metadata')}
              className={cn(
                'flex-1 flex items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-semibold transition-all cursor-pointer',
                activeSubView === 'metadata'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <Sparkles className="h-3.5 w-3.5" />
              YouTube Caption &amp; SEO
            </button>
            <button
              type="button"
              onClick={() => setActiveSubView('content')}
              className={cn(
                'flex-1 flex items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-semibold transition-all cursor-pointer',
                activeSubView === 'content'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <FileText className="h-3.5 w-3.5" />
              See Content &amp; Subtitles ({pkg.timed_captions.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveSubView('preview')}
              className={cn(
                'flex-1 flex items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-semibold transition-all cursor-pointer',
                activeSubView === 'preview'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <Eye className="h-3.5 w-3.5" />
              YouTube Feed Preview
            </button>
          </div>

          {activeSubView === 'metadata' && (
            <div className="space-y-4">
              {/* YouTube Title */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor={`yt-title-${clipId}`}
                    className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    YouTube Shorts Title ({editableTitle.length}/100)
                  </label>
                  <button
                    type="button"
                    onClick={() => void handleCopy('title', editableTitle)}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline cursor-pointer"
                  >
                    {copiedKey === 'title' ? (
                      <>
                        <Check className="h-3 w-3 text-emerald-400" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3" />
                        Copy Title
                      </>
                    )}
                  </button>
                </div>
                <input
                  id={`yt-title-${clipId}`}
                  type="text"
                  maxLength={100}
                  value={editableTitle}
                  onChange={(e) => setEditableTitle(e.target.value)}
                  className="w-full rounded-xl border border-glass-border bg-background/60 px-3.5 py-2.5 text-sm font-medium text-foreground outline-none focus:border-primary"
                />
              </div>

              {/* YouTube Description */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor={`yt-desc-${clipId}`}
                    className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    YouTube Description &amp; Caption Copy
                  </label>
                  <button
                    type="button"
                    onClick={() => void handleCopy('description', editableDescription)}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline cursor-pointer"
                  >
                    {copiedKey === 'description' ? (
                      <>
                        <Check className="h-3 w-3 text-emerald-400" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3" />
                        Copy Description
                      </>
                    )}
                  </button>
                </div>
                <textarea
                  id={`yt-desc-${clipId}`}
                  rows={6}
                  value={editableDescription}
                  onChange={(e) => setEditableDescription(e.target.value)}
                  className="w-full rounded-xl border border-glass-border bg-background/60 p-3.5 text-xs leading-relaxed text-foreground outline-none focus:border-primary"
                />
              </div>

              {/* Hashtags & SEO Tags */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="rounded-xl border border-glass-border bg-background/40 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                      <Hash className="h-3.5 w-3.5 text-primary" />
                      Viral Hashtags
                    </span>
                    <button
                      type="button"
                      onClick={() => void handleCopy('hashtags', pkg.hashtags.join(' '))}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline cursor-pointer"
                    >
                      {copiedKey === 'hashtags' ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {pkg.hashtags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full bg-primary/15 px-2.5 py-0.5 text-[11px] font-semibold text-primary"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="rounded-xl border border-glass-border bg-background/40 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                      <Tag className="h-3.5 w-3.5 text-primary" />
                      YouTube Studio SEO Tags
                    </span>
                    <button
                      type="button"
                      onClick={() => void handleCopy('tags', pkg.tags.join(', '))}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline cursor-pointer"
                    >
                      {copiedKey === 'tags' ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {pkg.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-md border border-glass-border bg-muted/50 px-2 py-0.5 text-[11px] text-muted-foreground"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeSubView === 'content' && (
            <div className="space-y-4">
              {/* Full Spoken Content & Burned-in Caption Script */}
              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label
                    htmlFor={`spoken-content-${clipId}`}
                    className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    Spoken Content / Burned-In Subtitle Script
                  </label>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleDownloadSrt}
                      className="inline-flex items-center gap-1 rounded-lg border border-glass-border bg-background/60 px-2.5 py-1 text-[11px] font-semibold text-foreground hover:bg-accent cursor-pointer"
                    >
                      <Download className="h-3 w-3 text-primary" />
                      Download .SRT
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleCopy('script', customCaption)}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline cursor-pointer"
                    >
                      {copiedKey === 'script' ? 'Copied!' : 'Copy Script'}
                    </button>
                  </div>
                </div>
                <textarea
                  id={`spoken-content-${clipId}`}
                  rows={3}
                  value={customCaption}
                  onChange={(e) => setCustomCaption(e.target.value)}
                  className="w-full rounded-xl border border-glass-border bg-background/60 p-3 text-xs leading-relaxed text-foreground outline-none focus:border-primary"
                />
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => void handleGenerate(tone, true)}
                    disabled={isGenerating}
                    className="rounded-lg bg-primary/15 px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary/25 transition-colors cursor-pointer"
                  >
                    Apply Edited Script to Video Captions &amp; Regenerate Metadata
                  </button>
                </div>
              </div>

              {/* Timestamped Subtitle Breakdown */}
              <div className="space-y-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground block">
                  Timed Subtitle Cues ({pkg.timed_captions.length} segments)
                </span>
                <div className="max-h-60 overflow-y-auto space-y-1.5 pr-1">
                  {pkg.timed_captions.map((cue, idx) => (
                    <div
                      key={`${idx}-${cue.start_time}`}
                      className="flex items-center justify-between gap-3 rounded-lg border border-glass-border bg-background/50 px-3 py-2 text-xs"
                    >
                      <span className="shrink-0 rounded bg-primary/15 px-2 py-0.5 font-mono text-[10px] font-semibold text-primary">
                        {cue.timestamp_label}
                      </span>
                      <span className="flex-1 text-foreground">{cue.text}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeSubView === 'preview' && (
            <div className="space-y-4">
              <div className="rounded-2xl border border-glass-border bg-black/90 p-5 text-white shadow-xl space-y-4">
                <div className="flex items-center justify-between border-b border-white/10 pb-3">
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-rose-600 text-xs font-bold">
                      YT
                    </div>
                    <div>
                      <p className="text-xs font-bold">@YourYouTubeChannel</p>
                      <p className="text-[10px] text-white/60">YouTube Shorts Feed Preview</p>
                    </div>
                  </div>
                  <span className="rounded-full bg-white text-black px-3 py-1 text-[11px] font-bold">
                    Subscribe
                  </span>
                </div>

                {/* Simulated Active Burned-In Subtitle Preview */}
                <div className="rounded-xl bg-white/5 border border-white/10 p-4 text-center space-y-2">
                  <span className="text-[10px] uppercase tracking-wider text-amber-400 font-semibold block">
                    On-Screen Burned Subtitle Preview ({pkg.specs_check.caption_style})
                  </span>
                  <p className="text-base font-extrabold tracking-wide text-amber-300 drop-shadow">
                    &ldquo;{pkg.timed_captions[0]?.text ?? pkg.caption_text.slice(0, 50)}&rdquo;
                  </p>
                </div>

                {/* YouTube Shorts Bottom Overlay Metadata */}
                <div className="space-y-2 pt-1">
                  <p className="text-sm font-bold leading-snug">{editableTitle}</p>
                  <p className="text-xs text-white/80 whitespace-pre-line line-clamp-4">
                    {editableDescription}
                  </p>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {pkg.hashtags.map((h) => (
                      <span key={h} className="text-[11px] font-semibold text-sky-400">
                        {h}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Technical Readiness Specs Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                <div className="rounded-lg border border-glass-border bg-background/50 p-2.5">
                  <span className="text-[10px] text-muted-foreground block">Resolution</span>
                  <span className="font-semibold text-foreground">{pkg.specs_check.resolution}</span>
                </div>
                <div className="rounded-lg border border-glass-border bg-background/50 p-2.5">
                  <span className="text-[10px] text-muted-foreground block">Aspect Ratio</span>
                  <span className="font-semibold text-foreground">{pkg.specs_check.aspect_ratio}</span>
                </div>
                <div className="rounded-lg border border-glass-border bg-background/50 p-2.5">
                  <span className="text-[10px] text-muted-foreground block">Duration</span>
                  <span className="font-semibold text-foreground">
                    {pkg.specs_check.duration_seconds}s / {pkg.specs_check.max_duration_seconds}s
                  </span>
                </div>
                <div className="rounded-lg border border-glass-border bg-background/50 p-2.5">
                  <span className="text-[10px] text-muted-foreground block">Codec Spec</span>
                  <span className="font-semibold text-emerald-400">H.264 + AAC</span>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </GlassCard>
  );
}
