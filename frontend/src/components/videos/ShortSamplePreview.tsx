import { useState, useEffect } from 'react';
import {
  Sparkles,
  Play,
  Pause,
  RotateCcw,
  Heart,
  MessageCircle,
  Bookmark,
  Share2,
  Music2,
  Flame,
  Film,
  Crop,
  Layers,
  Clock,
  Wand2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type {
  BrollPlacement,
  CaptionStylePreset,
  ClipLength,
  FramingMode,
} from '@/types';

export interface ShortSamplePreviewProps {
  clipLength: ClipLength;
  subtitleStyle: CaptionStylePreset;
  framingMode: FramingMode;
  autoBroll: boolean;
  brollPlacement: BrollPlacement;
  autoProduce?: boolean;
}

const SAMPLE_SCRIPTS = [
  {
    hook: 'THE KEY TO VIRAL CONTENT',
    words: ['THE', 'KEY', 'TO', 'VIRAL', 'CONTENT', 'IS', 'AN', 'IRRESISTIBLE', 'HOOK'],
    topic: 'Exponential Growth',
    category: 'Content Strategy',
  },
  {
    hook: 'THIS ONE SECRET CHANGED EVERYTHING',
    words: ['THIS', 'ONE', 'SECRET', '10X', 'MY', 'AUDIENCE', 'IN', 'THIRTY', 'DAYS'],
    topic: 'AI Technology',
    category: 'Productivity Hacks',
  },
  {
    hook: 'NEVER MAKE THIS PODCAST MISTAKE',
    words: ['NEVER', 'MAKE', 'THIS', 'MISTAKE', 'IF', 'YOU', 'WANT', 'TO', 'BLOW', 'UP'],
    topic: 'Creator Economy',
    category: 'Podcasting Tips',
  },
];

export function ShortSamplePreview({
  clipLength,
  subtitleStyle,
  framingMode,
  autoBroll,
  brollPlacement,
  autoProduce = true,
}: ShortSamplePreviewProps) {
  const [isPlaying, setIsPlaying] = useState(true);
  const [scriptIndex, setScriptIndex] = useState(0);
  const [currentWordIndex, setCurrentWordIndex] = useState(0);
  const [isLiked, setIsLiked] = useState(false);
  const [likeCount, setLikeCount] = useState(84200);

  const currentScript = SAMPLE_SCRIPTS[scriptIndex];

  // Cycle through words smoothly when playing
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setCurrentWordIndex((prev) => (prev + 1) % currentScript.words.length);
    }, 450);

    return () => clearInterval(interval);
  }, [isPlaying, currentScript.words.length]);

  const handleNextScript = () => {
    setScriptIndex((prev) => (prev + 1) % SAMPLE_SCRIPTS.length);
    setCurrentWordIndex(0);
  };

  const handleToggleLike = () => {
    setIsLiked((prev) => {
      const next = !prev;
      setLikeCount((count) => (next ? count + 1 : count - 1));
      return next;
    });
  };

  // Caption styling based on preset
  const renderCaptionText = () => {
    const words = currentScript.words;

    switch (subtitleStyle) {
      case 'hormozi':
        return (
          <div className="rounded-xl border-2 border-[#a3e635] bg-black/95 px-3 py-1.5 text-center shadow-[0_0_20px_rgba(163,230,53,0.5)] backdrop-blur-md">
            <div className="flex flex-wrap items-center justify-center gap-1.5 font-black uppercase tracking-wide text-xs">
              {words.map((word, idx) => {
                const isActive = idx === currentWordIndex;
                return (
                  <span
                    key={idx}
                    className={cn(
                      'transition-all duration-150',
                      isActive
                        ? 'scale-125 text-[#a3e635] underline decoration-[#a3e635] decoration-2 drop-shadow-[0_2px_10px_rgba(163,230,53,0.9)]'
                        : 'text-[#ffe600]'
                    )}
                  >
                    {word}
                  </span>
                );
              })}
            </div>
          </div>
        );

      case 'neon':
        return (
          <div className="rounded-xl border border-[#22d3ee] bg-[#06141e]/90 px-3 py-1.5 text-center shadow-[0_0_16px_rgba(34,211,238,0.7)] backdrop-blur-md">
            <div className="flex flex-wrap items-center justify-center gap-1.5 font-extrabold uppercase tracking-wide text-xs">
              {words.map((word, idx) => {
                const isActive = idx === currentWordIndex;
                return (
                  <span
                    key={idx}
                    className={cn(
                      'transition-all duration-150',
                      isActive
                        ? 'scale-125 text-[#e879f9] drop-shadow-[0_0_12px_rgba(232,121,249,0.95)]'
                        : 'text-[#22d3ee]'
                    )}
                  >
                    {word}
                  </span>
                );
              })}
            </div>
          </div>
        );

      case 'karaoke':
        return (
          <div className="rounded-xl border-b-2 border-[#34d399] bg-[#06080a]/85 px-3 py-1.5 text-center backdrop-blur-md">
            <div className="flex flex-wrap items-center justify-center gap-1.5 font-extrabold uppercase tracking-wide text-xs">
              {words.map((word, idx) => {
                const isPastOrCurrent = idx <= currentWordIndex;
                const isActive = idx === currentWordIndex;
                return (
                  <span
                    key={idx}
                    className={cn(
                      'transition-all duration-150',
                      isActive
                        ? 'scale-115 text-[#34d399] underline decoration-[#34d399] decoration-2'
                        : isPastOrCurrent
                          ? 'text-[#34d399]'
                          : 'text-[#e2fff0]/60'
                    )}
                  >
                    {word}
                  </span>
                );
              })}
            </div>
          </div>
        );

      case 'bold_box':
      default:
        return (
          <div className="rounded-xl border border-white/20 bg-black/90 px-3 py-1.5 text-center shadow-xl backdrop-blur-md">
            <div className="flex flex-wrap items-center justify-center gap-1.5 font-bold text-xs text-white">
              {words.map((word, idx) => {
                const isActive = idx === currentWordIndex;
                return (
                  <span
                    key={idx}
                    className={cn(
                      'transition-all duration-150',
                      isActive
                        ? 'rounded bg-yellow-400 px-1 py-0.5 text-black font-extrabold shadow-sm'
                        : 'text-white'
                    )}
                  >
                    {word}
                  </span>
                );
              })}
            </div>
          </div>
        );
    }
  };

  // Simulated Speaker Host Visual
  const renderSpeakerVisual = () => (
    <div className="relative h-full w-full overflow-hidden bg-gradient-to-b from-slate-950 via-indigo-950/70 to-slate-950 flex flex-col items-center justify-center">
      {/* Studio acoustic foam background pattern */}
      <div className="absolute inset-0 opacity-20 bg-[radial-gradient(#6366f1_1px,transparent_1px)] [background-size:16px_16px]" />

      {/* Studio Rim Light Spotlights */}
      <div className="absolute -top-12 -left-12 h-44 w-44 rounded-full bg-cyan-500/20 blur-3xl" />
      <div className="absolute -top-12 -right-12 h-44 w-44 rounded-full bg-purple-500/25 blur-3xl" />
      <div className="absolute -bottom-10 inset-x-0 h-32 bg-gradient-to-t from-slate-950 via-slate-950/80 to-transparent z-10" />

      {/* Speaker Avatar & Mic */}
      <div className="relative z-10 flex flex-col items-center">
        {/* Host Avatar with Headphones */}
        <div className="relative">
          <div className="h-24 w-24 rounded-full bg-gradient-to-tr from-purple-600 via-indigo-500 to-pink-500 p-1 shadow-2xl ring-4 ring-white/10">
            <div className="h-full w-full rounded-full bg-slate-900 flex items-center justify-center overflow-hidden relative">
              {/* Host Silhouette Head */}
              <div className="h-16 w-16 rounded-full bg-slate-800 flex flex-col items-center justify-center relative">
                {/* Hair/Head */}
                <div className="h-8 w-10 rounded-t-full bg-slate-700 mt-1" />
                {/* Face */}
                <div className="h-8 w-8 rounded-b-full bg-amber-200/80 -mt-1 flex items-center justify-center">
                  <div className="flex gap-2">
                    <span className="h-1 w-1 rounded-full bg-slate-900" />
                    <span className="h-1 w-1 rounded-full bg-slate-900" />
                  </div>
                </div>
              </div>
              {/* Studio Headphones Band */}
              <div className="absolute top-2 inset-x-2 h-4 border-t-4 border-cyan-400 rounded-t-full" />
              {/* Earcups */}
              <div className="absolute top-7 left-1 h-5 w-3 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
              <div className="absolute top-7 right-1 h-5 w-3 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
            </div>
          </div>

          {/* Active Voice Equalizer Pulsing beside speaker */}
          {isPlaying && (
            <div className="absolute -right-5 top-6 flex items-end gap-0.5 rounded-full bg-black/60 px-1.5 py-1 border border-primary/30 backdrop-blur-sm shadow-lg">
              <span className="h-3 w-0.5 rounded-full bg-primary animate-pulse" />
              <span className="h-5 w-0.5 rounded-full bg-primary animate-pulse delay-75" />
              <span className="h-2 w-0.5 rounded-full bg-primary animate-pulse delay-150" />
              <span className="h-4 w-0.5 rounded-full bg-primary animate-pulse delay-100" />
            </div>
          )}
        </div>

        {/* Podcast Studio Boom Mic in front */}
        <div className="relative -mt-3 flex flex-col items-center">
          <div className="h-8 w-5 rounded-full border border-slate-500 bg-gradient-to-b from-slate-400 to-slate-700 shadow-lg flex items-center justify-center">
            <div className="h-6 w-3 rounded-full bg-slate-900/80 border border-slate-600 flex flex-col items-center justify-center gap-0.5">
              <span className="h-0.5 w-2 bg-slate-400/60" />
              <span className="h-0.5 w-2 bg-slate-400/60" />
              <span className="h-0.5 w-2 bg-slate-400/60" />
            </div>
          </div>
          <div className="h-4 w-1 bg-slate-600" />
          <div className="h-2 w-8 rounded-full bg-slate-700 shadow" />
        </div>

        {/* Speaker Name Tag */}
        <div className="mt-1 flex items-center gap-1.5 rounded-full bg-black/50 px-2.5 py-0.5 text-[10px] text-muted-foreground border border-white/10 backdrop-blur-sm">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-semibold text-slate-200">Host (AI Speaker Focus)</span>
        </div>
      </div>
    </div>
  );

  // Simulated AI B-Roll Visual
  const renderBrollVisual = () => (
    <div className="relative h-full w-full overflow-hidden bg-gradient-to-tr from-blue-950 via-slate-900 to-emerald-950 flex flex-col justify-between p-2.5">
      {/* Dynamic graphic animation grid */}
      <div className="absolute inset-0 opacity-30 bg-[linear-gradient(to_right,#38bdf8_1px,transparent_1px),linear-gradient(to_bottom,#38bdf8_1px,transparent_1px)] bg-[size:1.5rem_1.5rem]" />
      
      {/* Rising Trend / Stock Chart / Growth Graphic */}
      <div className="absolute inset-x-0 bottom-0 h-28 opacity-40">
        <svg viewBox="0 0 100 40" className="h-full w-full overflow-visible preserve-3d">
          <defs>
            <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d="M0,35 Q20,30 35,20 T70,12 T100,5 L100,40 L0,40 Z"
            fill="url(#chartGrad)"
          />
          <path
            d="M0,35 Q20,30 35,20 T70,12 T100,5"
            fill="none"
            stroke="#34d399"
            strokeWidth="2"
          />
        </svg>
      </div>

      {/* Floating B-Roll Badge */}
      <div className="relative z-10 flex items-center justify-between">
        <div className="flex items-center gap-1 rounded-full bg-black/75 px-2 py-0.5 text-[9px] font-semibold text-white border border-primary/40 backdrop-blur-sm shadow-md">
          <Sparkles className="h-2.5 w-2.5 text-primary" />
          <span className="truncate max-w-[100px]">✨ {currentScript.topic}</span>
        </div>
        <span className="rounded bg-primary/20 px-1 py-0.5 text-[8px] font-mono text-primary font-bold">
          Pexels HD
        </span>
      </div>

      {/* Bottom B-Roll tag */}
      <div className="relative z-10 flex items-center justify-between text-[8px] text-white/70">
        <span className="flex items-center gap-1">
          <Film className="h-2.5 w-2.5 text-primary" />
          Keyword Synced B-Roll
        </span>
        <span className="font-mono text-emerald-400 font-semibold">+180% Retention</span>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col gap-3">
      {/* Header Bar */}
      <div className="flex items-center justify-between rounded-2xl border border-glass-border bg-glass-bg p-3 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h3 className="text-xs font-bold text-foreground">Live 9:16 Short Preview</h3>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-semibold text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Live Sync
              </span>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Real-time look based on your AI customization options
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleNextScript}
            title="Cycle sample viral quote"
            className="flex h-7 items-center gap-1 rounded-lg border border-glass-border bg-background/50 px-2 text-[10px] font-medium text-muted-foreground hover:border-primary/50 hover:text-foreground transition-all"
          >
            <RotateCcw className="h-3 w-3" />
            Hook
          </button>
          <button
            type="button"
            onClick={() => setIsPlaying(!isPlaying)}
            title={isPlaying ? 'Pause preview' : 'Play preview'}
            className="flex h-7 w-7 items-center justify-center rounded-lg border border-glass-border bg-background/50 text-muted-foreground hover:border-primary/50 hover:text-primary transition-all"
          >
            {isPlaying ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3 fill-current" />}
          </button>
        </div>
      </div>

      {/* Realistic 9:16 Phone Mockup Canvas */}
      <div className="relative mx-auto w-full max-w-[310px] aspect-[9/16] rounded-[2.5rem] border-[6px] border-slate-800 bg-black shadow-[0_25px_60px_-15px_rgba(0,0,0,0.8),0_0_35px_rgba(99,102,241,0.15)] overflow-hidden flex flex-col justify-between ring-1 ring-white/10 select-none">
        {/* Dynamic Island / Notch */}
        <div className="absolute top-2 inset-x-0 z-40 flex justify-center pointer-events-none">
          <div className="h-4 w-24 rounded-full bg-black/90 border border-slate-700/60 shadow-inner flex items-center justify-between px-2.5">
            <span className="h-1.5 w-1.5 rounded-full bg-slate-800" />
            <span className="h-1 w-1 rounded-full bg-emerald-500/80 animate-pulse" />
          </div>
        </div>

        {/* Top Status Bar & Badges */}
        <div className="relative z-30 flex items-center justify-between px-5 pt-3 pb-1 text-[10px] font-semibold text-white/80">
          <span>9:41</span>
          <div className="flex items-center gap-1.5">
            <span className="inline-flex items-center gap-1 rounded-full bg-primary/25 border border-primary/40 px-2 py-0.5 text-[9px] font-bold text-primary shadow-sm">
              <Flame className="h-2.5 w-2.5 text-primary fill-primary" />
              94 Viral Score
            </span>
          </div>
        </div>

        {/* Framing & Video Layer */}
        <div className="absolute inset-0 z-0 overflow-hidden bg-black flex flex-col">
          {framingMode === 'speaker_focus' && (
            <div className="relative h-full w-full">
              {/* If split screen B-roll is enabled, top 50% is speaker */}
              {autoBroll && brollPlacement === 'split' ? (
                <div className="h-1/2 w-full border-b border-primary/50 relative">
                  {renderSpeakerVisual()}
                  <span className="absolute top-8 left-3 z-20 rounded bg-black/70 px-1.5 py-0.5 text-[8px] font-semibold text-slate-300">
                    Host Focus
                  </span>
                </div>
              ) : (
                <div className="h-full w-full">
                  {renderSpeakerVisual()}
                </div>
              )}
            </div>
          )}

          {framingMode === 'dynamic_blur' && (
            <div className="relative h-full w-full flex items-center justify-center overflow-hidden">
              {/* Blurred background copy */}
              <div className="absolute inset-0 filter blur-xl scale-125 opacity-70">
                {renderSpeakerVisual()}
              </div>
              {/* 16:9 Crisp Center Box */}
              <div className="relative z-10 w-full aspect-video border-y border-white/20 shadow-2xl overflow-hidden bg-black">
                {renderSpeakerVisual()}
                <div className="absolute top-1.5 left-2 rounded bg-black/75 px-1.5 py-0.5 text-[8px] font-semibold text-cyan-300">
                  Dynamic 16:9 Blur
                </div>
              </div>
            </div>
          )}

          {framingMode === 'fit' && (
            <div className="relative h-full w-full flex items-center justify-center bg-black">
              {/* Letterboxed 16:9 Center */}
              <div className="relative z-10 w-full aspect-video border-y border-white/10 shadow-2xl overflow-hidden bg-black">
                {renderSpeakerVisual()}
                <div className="absolute top-1.5 left-2 rounded bg-black/75 px-1.5 py-0.5 text-[8px] font-semibold text-white/70">
                  16:9 Letterbox Fit
                </div>
              </div>
            </div>
          )}

          {/* Auto B-Roll Layer based on brollPlacement */}
          {autoBroll && (
            <>
              {brollPlacement === 'bottom' && (
                <div className="absolute inset-x-0 bottom-0 h-[25%] w-full border-t-2 border-primary shadow-2xl z-10 overflow-hidden animate-in fade-in duration-300">
                  {renderBrollVisual()}
                </div>
              )}

              {brollPlacement === 'split' && (
                <div className="absolute inset-x-0 bottom-0 h-1/2 w-full border-t-2 border-primary shadow-2xl z-10 overflow-hidden animate-in fade-in duration-300">
                  {renderBrollVisual()}
                </div>
              )}

              {brollPlacement === 'bottom_right' && (
                <div className="absolute bottom-16 right-3 w-28 aspect-video rounded-xl border-2 border-primary shadow-2xl z-20 overflow-hidden animate-in fade-in zoom-in-95 duration-300">
                  {renderBrollVisual()}
                </div>
              )}

              {brollPlacement === 'top' && (
                <div className="absolute inset-x-0 top-0 h-[25%] w-full border-b-2 border-primary shadow-2xl z-10 overflow-hidden animate-in fade-in duration-300">
                  {renderBrollVisual()}
                </div>
              )}
            </>
          )}
        </div>

        {/* Right Social Action Rail (TikTok/Shorts UI) */}
        <div className="absolute right-2.5 bottom-20 z-30 flex flex-col items-center gap-3 text-white">
          {/* Creator Avatar with follow plus */}
          <div className="relative">
            <div className="h-8 w-8 rounded-full border border-white/50 bg-gradient-to-tr from-purple-500 to-pink-500 p-0.5 shadow-md">
              <div className="h-full w-full rounded-full bg-slate-900 flex items-center justify-center text-[10px] font-bold text-white">
                VS
              </div>
            </div>
            <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-white shadow">
              +
            </span>
          </div>

          {/* Like Button */}
          <button
            type="button"
            onClick={handleToggleLike}
            className="flex flex-col items-center gap-0.5 group"
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-black/40 backdrop-blur-sm group-hover:scale-110 transition-transform">
              <Heart
                className={cn(
                  'h-4 w-4 transition-colors',
                  isLiked ? 'fill-red-500 text-red-500' : 'text-white'
                )}
              />
            </div>
            <span className="text-[9px] font-semibold">
              {(likeCount / 1000).toFixed(1)}K
            </span>
          </button>

          {/* Comments Button */}
          <div className="flex flex-col items-center gap-0.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-black/40 backdrop-blur-sm">
              <MessageCircle className="h-4 w-4 text-white" />
            </div>
            <span className="text-[9px] font-semibold">1.4K</span>
          </div>

          {/* Bookmark Button */}
          <div className="flex flex-col items-center gap-0.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-black/40 backdrop-blur-sm">
              <Bookmark className="h-4 w-4 text-white" />
            </div>
            <span className="text-[9px] font-semibold">12K</span>
          </div>

          {/* Share Button */}
          <div className="flex flex-col items-center gap-0.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-black/40 backdrop-blur-sm">
              <Share2 className="h-4 w-4 text-white" />
            </div>
            <span className="text-[9px] font-semibold">4.8K</span>
          </div>

          {/* Rotating Vinyl Disc */}
          <div className="mt-1 flex h-7 w-7 items-center justify-center rounded-full border-2 border-white/60 bg-gradient-to-tr from-slate-900 to-black shadow-lg animate-spin [animation-duration:4s]">
            <Music2 className="h-3 w-3 text-white" />
          </div>
        </div>

        {/* Captions Overlay Center */}
        <div
          className={cn(
            'relative z-30 px-3 transition-all duration-300',
            brollPlacement === 'bottom' && autoBroll
              ? 'mb-3'
              : 'mb-4'
          )}
        >
          {renderCaptionText()}
        </div>

        {/* Bottom Metadata & Info Bar */}
        <div className="relative z-30 space-y-1.5 bg-gradient-to-t from-black via-black/80 to-transparent p-3 pt-6 text-white">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-bold">@podcasthighlights</span>
            <span className="rounded bg-white/20 px-1 py-0.2 text-[8px] font-semibold">
              Original
            </span>
          </div>

          <p className="line-clamp-1 text-[10px] text-white/90">
            {currentScript.hook} #viral #shorts #podcast
          </p>

          <div className="flex items-center justify-between pt-0.5">
            <div className="flex items-center gap-1 text-[9px] text-white/70">
              <Music2 className="h-2.5 w-2.5" />
              <span className="truncate max-w-[130px]">Viral Podcast Audio • Original</span>
            </div>
            <span className="rounded-full bg-primary/20 border border-primary/40 px-2 py-0.5 text-[8px] font-bold text-primary">
              {clipLength === 'fast'
                ? '⚡ Fast (15-30s)'
                : clipLength === 'in_depth'
                  ? '🎬 In-Depth (45-60s)'
                  : '⏱️ Auto (30-50s)'}
            </span>
          </div>
        </div>
      </div>

      {/* Applied Specs Breakdown Chips */}
      <div className="rounded-2xl border border-glass-border bg-glass-bg p-3.5 backdrop-blur-md space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
            <Wand2 className="h-3 w-3 text-primary" />
            Applied Output Blueprint
          </span>
          {autoProduce && (
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-primary">
              <Sparkles className="h-2.5 w-2.5" />
              Auto Produce Ready
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2 text-[11px]">
          {/* Framing spec */}
          <div className="flex items-start gap-1.5 rounded-lg border border-glass-border bg-background/50 p-2">
            <Crop className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
            <div>
              <span className="block font-semibold text-foreground">
                {framingMode === 'speaker_focus'
                  ? 'Speaker Focus'
                  : framingMode === 'dynamic_blur'
                    ? 'Dynamic Blur'
                    : 'Fit (Letterbox)'}
              </span>
              <span className="block text-[9px] text-muted-foreground">
                {framingMode === 'speaker_focus'
                  ? 'Face tracking 9:16 crop'
                  : framingMode === 'dynamic_blur'
                    ? '16:9 on blurred canvas'
                    : 'Widescreen letterbox'}
              </span>
            </div>
          </div>

          {/* Caption spec */}
          <div className="flex items-start gap-1.5 rounded-lg border border-glass-border bg-background/50 p-2">
            <Sparkles className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
            <div>
              <span className="block font-semibold text-foreground">
                {subtitleStyle === 'hormozi'
                  ? 'Hormozi Pop'
                  : subtitleStyle === 'neon'
                    ? 'Neon Cyber'
                    : subtitleStyle === 'karaoke'
                      ? 'Karaoke Wave'
                      : 'Viral Box'}
              </span>
              <span className="block text-[9px] text-muted-foreground">
                {subtitleStyle === 'hormozi'
                  ? 'Yellow/Lime word pop'
                  : subtitleStyle === 'neon'
                    ? 'Cyan/Magenta glow'
                    : subtitleStyle === 'karaoke'
                      ? 'Word-by-word wave'
                      : 'High-contrast overlay'}
              </span>
            </div>
          </div>

          {/* B-Roll spec */}
          <div className="flex items-start gap-1.5 rounded-lg border border-glass-border bg-background/50 p-2">
            <Layers className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
            <div>
              <span className="block font-semibold text-foreground">
                {autoBroll
                  ? brollPlacement === 'bottom'
                    ? 'Bottom Split (25%)'
                    : brollPlacement === 'split'
                      ? 'Split Screen (50/50)'
                      : brollPlacement === 'bottom_right'
                        ? 'Corner PIP B-Roll'
                        : 'Top Split (25%)'
                  : 'B-Roll Disabled'}
              </span>
              <span className="block text-[9px] text-muted-foreground">
                {autoBroll
                  ? 'Keyword matched Pexels'
                  : 'Speaker footage only'}
              </span>
            </div>
          </div>

          {/* Length spec */}
          <div className="flex items-start gap-1.5 rounded-lg border border-glass-border bg-background/50 p-2">
            <Clock className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
            <div>
              <span className="block font-semibold text-foreground">
                {clipLength === 'fast'
                  ? 'Fast (15-30s)'
                  : clipLength === 'in_depth'
                    ? 'In-Depth (45-60s)'
                    : 'Auto (30-50s)'}
              </span>
              <span className="block text-[9px] text-muted-foreground">
                {clipLength === 'fast'
                  ? 'Max retention hooks'
                  : clipLength === 'in_depth'
                    ? 'Detailed storytelling'
                    : 'Optimized virality'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
