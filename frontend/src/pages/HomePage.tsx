import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Film,
  Sparkles,
  Zap,
  Flame,
  CheckCircle2,
  Video,
  Play,
  PlaySquare,
  Tv,
  Scissors,
  Layers,
  Wand2,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { MeshBackground } from '@/components/layout/MeshBackground';

const PLATFORMS = [
  { name: 'YouTube', icon: PlaySquare },
  { name: 'TikTok', icon: Video },
  { name: 'Twitch', icon: Tv },
  { name: 'Vimeo', icon: Film },
];

const HIGHLIGHT_FEATURES = [
  {
    icon: <Flame className="h-6 w-6 text-emerald-400" />,
    title: 'AI Virality Scoring',
    description:
      'Our engine analyzes emotional hooks, retention patterns, and speaking pacing to select moments with 90%+ viral probability.',
  },
  {
    icon: <Sparkles className="h-6 w-6 text-yellow-400" />,
    title: 'Animated Captions & Presets',
    description:
      'Auto-generate stylish Alex Hormozi captions, Neon Cyberpunk, or Karaoke highlights with 99% Whisper STT accuracy.',
  },
  {
    icon: <Layers className="h-6 w-6 text-cyan-400" />,
    title: 'Smart B-Roll Integration',
    description:
      'Automatically extracts keywords and overlays high-definition stock footage from Pexels and Pixabay to boost visual retention.',
  },
  {
    icon: <Scissors className="h-6 w-6 text-purple-400" />,
    title: 'Text-Based Video Trimming',
    description:
      'Edit your shorts by simply clicking sentences in the interactive transcript — just like editing a Google Doc.',
  },
  {
    icon: <Wand2 className="h-6 w-6 text-pink-400" />,
    title: '9:16 Smart Vertical Reframe',
    description:
      'Converts horizontal landscape video to vertical 1080x1920 short-form video ready for YouTube Shorts, Reels & TikTok.',
  },
  {
    icon: <Zap className="h-6 w-6 text-amber-400" />,
    title: '1-Click Batch Export',
    description:
      'Generate multiple unique shorts from a single long podcast or webinar with burned-in subtitles and instant MP4 download.',
  },
];

export function HomePage() {
  const [quickUrl, setQuickUrl] = useState('');
  const navigate = useNavigate();

  const handleQuickSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (quickUrl.trim()) {
      navigate('/videos/new');
    } else {
      navigate('/videos/new');
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden font-sans">
      <MeshBackground />

      {/* ------ Navigation Bar ------ */}
      <header className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
        <Link
          to="/"
          className="flex items-center gap-2.5 text-lg font-bold text-foreground tracking-tight"
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-secondary text-primary-foreground shadow-md shadow-primary/20">
            <Film className="h-5 w-5" />
          </div>
          <span>
            Video<span className="text-primary">ToShorts</span>
          </span>
        </Link>

        <div className="flex items-center gap-3">
          <Link
            to="/login"
            className="rounded-full px-5 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            Log in
          </Link>
          <Link to="/register">
            <GradientButton className="text-sm shadow-md shadow-primary/20">
              Sign up free
            </GradientButton>
          </Link>
        </div>
      </header>

      {/* ------ Hero Section ------ */}
      <section className="relative z-10 mx-auto flex max-w-5xl flex-col items-center px-6 pb-16 pt-12 text-center sm:pt-20">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-xs font-semibold text-emerald-400 backdrop-blur-md"
        >
          <Flame className="h-3.5 w-3.5" />
          AI Long Video to Short Video Converter &bull; 10x Faster
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 25 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: 'easeOut' }}
          className="mb-6 text-4xl font-extrabold leading-[1.15] tracking-tight text-foreground sm:text-6xl md:text-7xl"
        >
          Convert Long Videos to{' '}
          <span className="bg-gradient-to-r from-emerald-400 via-primary to-cyan-400 bg-clip-text text-transparent">
            Viral Shorts in 30s
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2, ease: 'easeOut' }}
          className="mx-auto mb-10 max-w-2xl text-base text-muted-foreground sm:text-lg"
        >
          Paste any YouTube, TikTok, or podcast link. Our AI automatically extracts
          the highest-retention hooks, creates 9:16 vertical clips, animates Hormozi-style
          captions, and overlays stock B-roll.
        </motion.p>

        {/* Quick Ingestion Bar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3, ease: 'easeOut' }}
          className="w-full max-w-2xl"
        >
          <form
            onSubmit={handleQuickSubmit}
            className="flex flex-col sm:flex-row items-center gap-2 rounded-2xl border border-glass-border bg-glass-bg p-2 backdrop-blur-xl shadow-2xl"
          >
            <input
              type="text"
              value={quickUrl}
              onChange={(e) => setQuickUrl(e.target.value)}
              placeholder="Paste YouTube, TikTok, or Vimeo link here..."
              className="w-full bg-transparent px-4 py-3 text-sm text-foreground outline-none placeholder:text-muted-foreground"
            />
            <GradientButton
              type="submit"
              className="w-full sm:w-auto shrink-0 gap-2 px-6 py-3.5 text-sm font-bold shadow-lg shadow-primary/25"
            >
              <Sparkles className="h-4 w-4" />
              Generate Shorts Free
            </GradientButton>
          </form>

          {/* Supported platform icons */}
          <div className="mt-3 flex items-center justify-center gap-3 text-xs text-muted-foreground">
            <span>Supports:</span>
            {PLATFORMS.map((plat) => (
              <span
                key={plat.name}
                className="inline-flex items-center gap-1 font-medium text-foreground/80"
              >
                <plat.icon className="h-3.5 w-3.5 text-primary" />
                {plat.name}
              </span>
            ))}
            <span className="opacity-60">&bull; Or Upload File up to 2GB</span>
          </div>
        </motion.div>
      </section>

      {/* ------ Interactive Showcase Preview ------ */}
      <section className="relative z-10 mx-auto max-w-5xl px-6 pb-20">
        <GlassCard className="p-6 md:p-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6 pb-6 border-b border-glass-border">
            <div>
              <span className="inline-block rounded-full bg-primary/20 px-3 py-1 text-xs font-semibold text-primary mb-2">
                Live Interactive Preview
              </span>
              <h2 className="text-xl md:text-2xl font-bold text-foreground">
                How VideoToShorts Transforms Your Video
              </h2>
            </div>

            <div className="flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400">
              <Flame className="h-3.5 w-3.5" />
              AI Virality Rating: 96/100
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-6 items-center">
            {/* Left: Input */}
            <div className="rounded-2xl border border-glass-border bg-background/50 p-4 space-y-3">
              <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
                <span>1. Long Video Input</span>
                <span className="font-mono">45:00 min</span>
              </div>
              <div className="relative aspect-video rounded-xl bg-muted/60 flex items-center justify-center overflow-hidden border border-glass-border">
                <PlaySquare className="h-10 w-10 text-red-500" />
                <span className="absolute bottom-2 right-2 text-[10px] bg-black/80 px-1.5 py-0.5 rounded text-white font-mono">
                  Full Podcast
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Raw footage transcribed and scored for high-energy hooks.
              </p>
            </div>

            {/* Middle: AI Process */}
            <div className="flex flex-col items-center justify-center gap-3 p-4 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/20 text-primary shadow-lg shadow-primary/30 animate-pulse">
                <Wand2 className="h-7 w-7" />
              </div>
              <h3 className="text-sm font-bold text-foreground">Wayin AI Engine</h3>
              <ul className="text-xs text-muted-foreground space-y-1 text-left">
                <li className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-primary shrink-0" />
                  Hook Detection (Score 96)
                </li>
                <li className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-primary shrink-0" />
                  Hormozi Animated Captions
                </li>
                <li className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-primary shrink-0" />
                  Pexels Stock B-Roll Overlay
                </li>
              </ul>
            </div>

            {/* Right: 9:16 Short Output */}
            <div className="flex flex-col items-center">
              <div className="relative w-44 aspect-[9/16] rounded-2xl overflow-hidden border-2 border-primary/40 bg-black shadow-xl flex flex-col justify-end p-3 text-center">
                <div className="absolute inset-0 flex items-center justify-center">
                  <Play className="h-8 w-8 text-white opacity-80" />
                </div>
                <div className="relative z-10 bg-black/80 px-2 py-1 rounded border border-lime-400">
                  <span className="text-[10px] font-black text-yellow-300 uppercase tracking-wide">
                    THIS ONE TECHNIQUE
                  </span>
                </div>
                <span className="text-[9px] text-muted-foreground font-mono mt-1">
                  0:35 &bull; 9:16 Ready Short
                </span>
              </div>
            </div>
          </div>
        </GlassCard>
      </section>

      {/* ------ Features Grid ------ */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 pb-24">
        <div className="text-center mb-12 space-y-3">
          <h2 className="text-3xl font-extrabold text-foreground sm:text-4xl">
            Built for Creators Who Value Quality & Speed
          </h2>
          <p className="text-muted-foreground max-w-xl mx-auto text-sm">
            Everything you need to turn raw videos into viral social media assets in seconds.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {HIGHLIGHT_FEATURES.map((feat) => (
            <GlassCard key={feat.title} className="p-6 space-y-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-background/80 border border-glass-border">
                {feat.icon}
              </div>
              <h3 className="text-base font-bold text-foreground">{feat.title}</h3>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {feat.description}
              </p>
            </GlassCard>
          ))}
        </div>
      </section>

      {/* ------ CTA Banner ------ */}
      <section className="relative z-10 mx-auto max-w-4xl px-6 pb-24">
        <GlassCard className="p-10 text-center space-y-6">
          <h2 className="text-3xl font-bold text-foreground">
            Start Converting Your Videos Today
          </h2>
          <p className="text-muted-foreground max-w-lg mx-auto text-sm">
            No credit card required. Upload a video and start creating viral shorts immediately.
          </p>
          <Link to="/register">
            <GradientButton className="gap-2 px-8 py-3.5 text-base shadow-xl shadow-primary/30">
              Get Started for Free
              <ArrowRight className="h-4 w-4" />
            </GradientButton>
          </Link>
        </GlassCard>
      </section>
    </div>
  );
}
