import { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Wand2,
  Sparkles,
  Layers,
  CheckCircle2,
  Loader2,
  Play,
  Download,
  AlertCircle,
  ExternalLink,
  Film,
  ChevronRight,
  RefreshCw,
  Lightbulb,
} from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { generateFromText } from '@/services/generateService';
import { listClips, getClipPreviewUrl } from '@/services/clipService';
import { getVideo } from '@/services/videoService';
import { cn } from '@/lib/utils';
import type {
  CaptionStylePreset,
  Clip,
  VideoProject,
} from '@/types';

const PRESET_EXAMPLES = [
  {
    label: '🐒 Monkey Facts',
    title: 'Top 5 Monkey Facts',
    description:
      'Interesting, punchy facts about wild monkeys for a YouTube Shorts audience: tool usage, social hierarchies, remarkable intelligence, speed, and mimicry.',
    count: 5,
  },
  {
    label: '🌌 Space Mysteries',
    title: 'Top 3 Mind-Blowing Space Facts',
    description:
      'Unbelievable cosmic anomalies: rogue planets wandering dark space, neutron star densities, and giant water clouds floating between galaxies.',
    count: 3,
  },
  {
    label: '🧠 Brain Hacks',
    title: 'Top 4 Psychology Life Hacks',
    description:
      'Fascinating human psychology tricks to boost focus, read body language, remember names effortlessly, and beat procrastination in seconds.',
    count: 4,
  },
];

const CAPTION_STYLES: { id: CaptionStylePreset; name: string; desc: string }[] = [
  { id: 'hormozi', name: 'Hormozi Punchy', desc: 'High-energy bold captions with active word highlight' },
  { id: 'neon', name: 'Neon Cyberpunk', desc: 'Vibrant glowing style with electric accents' },
  { id: 'bold_box', name: 'Bold Box', desc: 'High-contrast boxed styling with solid backing' },
  { id: 'minimal', name: 'Clean Minimal', desc: 'Subtle clean subtitles along the lower third' },
];

export function GeneratePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialPrompt = searchParams.get('prompt') || '';

  const [title, setTitle] = useState(initialPrompt);
  const [description, setDescription] = useState(
    initialPrompt
      ? `Top key points and engaging, punchy facts about ${initialPrompt} tailored for a YouTube Shorts audience.`
      : '',
  );
  const [shortsCount, setShortsCount] = useState<number>(3);
  const [captionStyle, setCaptionStyle] = useState<CaptionStylePreset>('hormozi');
  const [autoBroll, setAutoBroll] = useState(true);

  // Submission & Generation State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Active generation tracking
  const [activeProject, setActiveProject] = useState<VideoProject | null>(null);
  const [activeClips, setActiveClips] = useState<Clip[]>([]);
  const [previewClip, setPreviewClip] = useState<Clip | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  // Poll project and clips when generating
  useEffect(() => {
    if (!activeProject) return;

    if (activeProject.status === 'ready' || activeProject.status === 'failed') {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      return;
    }

    const checkStatus = async () => {
      try {
        const [updatedProject, clipsRes] = await Promise.all([
          getVideo(activeProject.id),
          listClips(activeProject.id),
        ]);

        setActiveProject(updatedProject);
        if (clipsRes.items && clipsRes.items.length > 0) {
          setActiveClips(clipsRes.items);
        }

        if (updatedProject.status === 'ready' || updatedProject.status === 'failed') {
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
        }
      } catch {
        // Continue polling despite temporary network glitches
      }
    };

    pollingRef.current = setInterval(checkStatus, 3000);

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [activeProject?.id, activeProject?.status]);

  const handleApplyPreset = (preset: typeof PRESET_EXAMPLES[0]) => {
    setTitle(preset.title);
    setDescription(preset.description);
    setShortsCount(preset.count);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim() || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const res = await generateFromText({
        title: title.trim(),
        description: description.trim(),
        shorts_count: shortsCount,
        caption_style: captionStyle,
        auto_broll: autoBroll,
      });

      setActiveProject(res.project);
      setActiveClips(res.clips);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? // @ts-expect-error axios response data check
            (err.response?.data?.detail ?? 'Failed to generate shorts.')
          : 'Failed to start video generation. Please check your network connection.';
      setError(String(msg));
    } finally {
      setIsSubmitting(false);
    }
  };

  const allClipsReady =
    activeClips.length > 0 &&
    activeClips.every((c) => c.status === 'ready' || c.status === 'failed');

  return (
    <PageWrapper className="mx-auto max-w-6xl px-4 py-8 md:py-12">
      {/* ── Header ── */}
      <div className="mb-8 flex flex-col items-start justify-between gap-4 border-b border-glass-border/30 pb-6 md:flex-row md:items-center">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3.5 py-1 text-xs font-semibold text-primary mb-3">
            <Sparkles className="h-3.5 w-3.5" />
            AI Text-to-Shorts Generator
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground md:text-4xl">
            Generate Shorts from Idea
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Provide a topic and description. Our AI creates the script, searches relevant
            stock B-roll footage, and stitches complete 9:16 vertical videos with animated captions.
          </p>
        </div>

        {activeProject && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setActiveProject(null);
                setActiveClips([]);
              }}
              className="inline-flex items-center gap-1.5 rounded-xl border border-glass-border bg-glass-bg/60 px-4 py-2 text-xs font-medium text-muted-foreground transition-all hover:text-foreground"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              New Prompt
            </button>
            <button
              type="button"
              onClick={() => navigate('/clips')}
              className="inline-flex items-center gap-1.5 rounded-xl bg-primary/20 px-4 py-2 text-xs font-semibold text-primary transition-all hover:bg-primary/30"
            >
              View Clip Library
              <ExternalLink className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        {/* ── Left Column: Form / Controls ── */}
        <div className={cn('transition-all duration-300', activeProject ? 'lg:col-span-5' : 'lg:col-span-7')}>
          <GlassCard className="p-6 md:p-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Presets chips */}
              <div>
                <div className="mb-2.5 flex items-center justify-between text-xs font-medium text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <Lightbulb className="h-3.5 w-3.5 text-amber-400" />
                    Quick Prompt Ideas
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {PRESET_EXAMPLES.map((preset) => (
                    <button
                      key={preset.label}
                      type="button"
                      onClick={() => handleApplyPreset(preset)}
                      className="rounded-lg border border-glass-border/60 bg-glass-bg/40 px-3 py-1.5 text-xs font-medium text-foreground/80 transition-all hover:border-primary/40 hover:bg-primary/10 hover:text-primary"
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Title input */}
              <div>
                <label htmlFor="gen-title" className="block text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1.5">
                  Video Series Title <span className="text-primary">*</span>
                </label>
                <input
                  id="gen-title"
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Top 5 Monkey Facts, Mind-Blowing Space Secrets"
                  required
                  className="w-full rounded-xl border border-glass-border bg-glass-bg/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-all focus:border-primary/50 focus:ring-2 focus:ring-primary/20"
                />
              </div>

              {/* Description textarea */}
              <div>
                <label htmlFor="gen-desc" className="block text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1.5">
                  Idea / Outline / Description <span className="text-primary">*</span>
                </label>
                <textarea
                  id="gen-desc"
                  rows={4}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe the content for each short: key facts, hooks, tone, or stories to tell..."
                  required
                  className="w-full rounded-xl border border-glass-border bg-glass-bg/60 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-all focus:border-primary/50 focus:ring-2 focus:ring-primary/20 resize-none"
                />
                <span className="mt-1 block text-[11px] text-muted-foreground">
                  The AI splits this description into punchy 15–30s segments with hooks and B-roll visuals.
                </span>
              </div>

              {/* Shorts count selection */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    Number of Shorts to Generate
                  </label>
                  <span className="rounded-md bg-primary/15 px-2 py-0.5 text-xs font-bold text-primary">
                    {shortsCount} {shortsCount === 1 ? 'Short' : 'Shorts'}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {[1, 2, 3, 5, 8, 10].map((num) => (
                    <button
                      key={num}
                      type="button"
                      onClick={() => setShortsCount(num)}
                      className={cn(
                        'flex-1 rounded-xl border py-2 text-xs font-semibold transition-all',
                        shortsCount === num
                          ? 'border-primary bg-primary text-white shadow-md'
                          : 'border-glass-border bg-glass-bg/40 text-foreground/80 hover:bg-accent hover:text-foreground',
                      )}
                    >
                      {num}
                    </button>
                  ))}
                </div>
              </div>

              {/* Caption Style selector */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">
                  Animated Subtitle Preset
                </label>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {CAPTION_STYLES.map((style) => (
                    <div
                      key={style.id}
                      onClick={() => setCaptionStyle(style.id)}
                      className={cn(
                        'cursor-pointer rounded-xl border p-3 transition-all',
                        captionStyle === style.id
                          ? 'border-primary/60 bg-primary/10 shadow-sm'
                          : 'border-glass-border bg-glass-bg/40 hover:border-glass-border/80',
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-foreground">{style.name}</span>
                        {captionStyle === style.id && (
                          <CheckCircle2 className="h-3.5 w-3.5 text-primary" />
                        )}
                      </div>
                      <p className="mt-1 text-[11px] text-muted-foreground leading-tight">{style.desc}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Auto B-roll switch */}
              <div className="flex items-center justify-between rounded-xl border border-glass-border/60 bg-glass-bg/40 p-3.5">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15 text-primary">
                    <Layers className="h-4 w-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-foreground">Auto-source HD B-Roll</h4>
                    <p className="text-[11px] text-muted-foreground">
                      Pulls free high-quality stock clips from Pexels & Pixabay
                    </p>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={autoBroll}
                  onChange={(e) => setAutoBroll(e.target.checked)}
                  className="h-4 w-4 rounded border-glass-border accent-primary cursor-pointer"
                />
              </div>

              {error && (
                <div className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* Submit button */}
              <GradientButton
                type="submit"
                disabled={isSubmitting || !title.trim() || !description.trim()}
                className="w-full justify-center py-3.5 text-sm font-semibold shadow-xl"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating Script & Starting Pipeline...
                  </>
                ) : (
                  <>
                    <Wand2 className="h-4 w-4" />
                    Generate {shortsCount} Viral Shorts
                  </>
                )}
              </GradientButton>
            </form>
          </GlassCard>
        </div>

        {/* ── Right Column: Live Pipeline Progress & Clip Cards ── */}
        <div className={cn('transition-all duration-300', activeProject ? 'lg:col-span-7' : 'lg:col-span-5')}>
          {!activeProject ? (
            /* Standby Card */
            <GlassCard className="flex flex-col items-center justify-center p-8 text-center min-h-[420px]">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary mb-4">
                <Film className="h-8 w-8" />
              </div>
              <h3 className="text-lg font-bold text-foreground">AI Video Canvas Ready</h3>
              <p className="mt-1.5 max-w-sm text-xs text-muted-foreground leading-relaxed">
                Fill in the series title and description or select one of the quick prompt ideas above, then click{' '}
                <strong className="text-foreground">Generate</strong>.
              </p>
              <div className="mt-6 flex flex-col gap-2.5 text-left text-xs text-muted-foreground/90 w-full max-w-xs">
                <div className="flex items-center gap-2 rounded-lg bg-glass-bg/60 p-2.5 border border-glass-border/40">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                  <span>AI generates {shortsCount} structured script hooks</span>
                </div>
                <div className="flex items-center gap-2 rounded-lg bg-glass-bg/60 p-2.5 border border-glass-border/40">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                  <span>Finds matching visual B-roll videos</span>
                </div>
                <div className="flex items-center gap-2 rounded-lg bg-glass-bg/60 p-2.5 border border-glass-border/40">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                  <span>Stitches 9:16 vertical MP4s with captions</span>
                </div>
              </div>
            </GlassCard>
          ) : (
            /* Active Progress & Clips Listing */
            <div className="space-y-6">
              {/* Project Status Banner */}
              <GlassCard className="p-6">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                  <div>
                    <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
                      Project #{activeProject.id}
                    </span>
                    <h2 className="text-xl font-bold text-foreground">{activeProject.title}</h2>
                  </div>
                  <div className="flex items-center gap-2">
                    {activeProject.status === 'ready' ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-400">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        All Shorts Ready!
                      </span>
                    ) : activeProject.status === 'failed' ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-destructive/15 px-3 py-1 text-xs font-semibold text-destructive">
                        <AlertCircle className="h-3.5 w-3.5" />
                        Generation Failed
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/15 px-3 py-1 text-xs font-semibold text-primary">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Generating Clips ({activeClips.filter((c) => c.status === 'ready').length}/{activeClips.length})
                      </span>
                    )}
                  </div>
                </div>

                {/* Progress bar */}
                <div className="relative mb-2 h-2.5 w-full overflow-hidden rounded-full bg-muted/80">
                  <motion.div
                    className="h-full rounded-full bg-gradient-to-r from-gradient-from via-primary to-gradient-to"
                    initial={{ width: '10%' }}
                    animate={{
                      width:
                        activeProject.status === 'ready'
                          ? '100%'
                          : `${Math.max(
                              20,
                              Math.round(
                                (activeClips.filter((c) => c.status === 'ready').length /
                                  Math.max(activeClips.length, 1)) *
                                  100,
                              ),
                            )}%`,
                    }}
                    transition={{ duration: 0.5 }}
                  />
                </div>
                <div className="flex justify-between text-[11px] text-muted-foreground">
                  <span>Script & B-roll Assembly</span>
                  <span>
                    {activeClips.filter((c) => c.status === 'ready').length} of {activeClips.length} ready
                  </span>
                </div>
              </GlassCard>

              {/* Generated Clips Grid */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
                    Generated Shorts ({activeClips.length})
                  </h3>
                  {allClipsReady && (
                    <button
                      type="button"
                      onClick={() => navigate('/clips')}
                      className="text-xs font-semibold text-primary hover:underline"
                    >
                      Open Full Clips Library &rarr;
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <AnimatePresence>
                    {activeClips.map((clip, idx) => (
                      <motion.div
                        key={clip.id}
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.1 }}
                      >
                        <GlassCard className="flex flex-col justify-between p-4 h-full border-glass-border/60 hover:border-primary/40 transition-all">
                          <div>
                            {/* Card Top: Order and Status */}
                            <div className="flex items-center justify-between mb-2.5">
                              <span className="rounded bg-primary/10 px-2 py-0.5 text-[11px] font-bold text-primary">
                                Part {clip.order_index + 1}
                              </span>
                              <span
                                className={cn(
                                  'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold',
                                  clip.status === 'ready'
                                    ? 'bg-emerald-500/15 text-emerald-400'
                                    : clip.status === 'failed'
                                      ? 'bg-destructive/15 text-destructive'
                                      : 'bg-primary/15 text-primary',
                                )}
                              >
                                {clip.status === 'ready' ? (
                                  <>
                                    <CheckCircle2 className="h-3 w-3" />
                                    Ready
                                  </>
                                ) : clip.status === 'failed' ? (
                                  <>
                                    <AlertCircle className="h-3 w-3" />
                                    Failed
                                  </>
                                ) : (
                                  <>
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                    Rendering
                                  </>
                                )}
                              </span>
                            </div>

                            {/* Title & narration snippet */}
                            <h4 className="text-sm font-bold text-foreground line-clamp-1">{clip.title}</h4>
                            <p className="mt-1 text-xs text-muted-foreground line-clamp-3 leading-relaxed">
                              {clip.caption_text || 'Assembling B-roll footage and caption overlays...'}
                            </p>
                          </div>

                          {/* Actions Bottom */}
                          <div className="mt-4 pt-3 border-t border-glass-border/40 flex items-center justify-between gap-2">
                            <span className="text-[11px] text-muted-foreground font-mono">
                              ~{Math.round(clip.end_time - clip.start_time)}s
                            </span>

                            <div className="flex items-center gap-1.5">
                              {clip.status === 'ready' && (
                                <>
                                  <button
                                    type="button"
                                    onClick={() => setPreviewClip(clip)}
                                    className="inline-flex items-center gap-1 rounded-lg bg-primary/15 px-2.5 py-1 text-xs font-semibold text-primary transition-all hover:bg-primary/25"
                                  >
                                    <Play className="h-3 w-3 fill-current" />
                                    Preview
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => navigate(`/clips/${clip.id}`)}
                                    className="inline-flex items-center gap-1 rounded-lg border border-glass-border px-2.5 py-1 text-xs font-medium text-foreground/80 transition-all hover:text-foreground"
                                  >
                                    Edit
                                    <ChevronRight className="h-3 w-3" />
                                  </button>
                                </>
                              )}
                            </div>
                          </div>
                        </GlassCard>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Preview Video Modal ── */}
      {previewClip && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
          onClick={() => setPreviewClip(null)}
        >
          <div
            className="relative w-full max-w-sm rounded-2xl border border-glass-border bg-glass-bg/95 p-4 shadow-2xl backdrop-blur-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-foreground truncate">{previewClip.title}</h3>
              <button
                type="button"
                onClick={() => setPreviewClip(null)}
                className="text-xs text-muted-foreground hover:text-foreground p-1"
              >
                ✕ Close
              </button>
            </div>

            <div className="aspect-[9/16] w-full overflow-hidden rounded-xl bg-black flex items-center justify-center">
              <video
                src={getClipPreviewUrl(previewClip.id)}
                controls
                autoPlay
                className="h-full w-full object-contain"
              />
            </div>

            <div className="mt-3 flex items-center justify-between">
              <a
                href={getClipPreviewUrl(previewClip.id)}
                download={`${previewClip.title.replace(/\s+/g, '_')}.mp4`}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline"
              >
                <Download className="h-3.5 w-3.5" />
                Download 9:16 MP4
              </a>
              <button
                type="button"
                onClick={() => navigate(`/clips/${previewClip.id}`)}
                className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
              >
                Open in Editor
                <ExternalLink className="h-3 w-3" />
              </button>
            </div>
          </div>
        </div>
      )}
    </PageWrapper>
  );
}
