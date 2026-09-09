import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Clapperboard,
  Sparkles,
  Zap,
  Scissors,
  Layers,
  Wand2,
  Play,
  CheckCircle2,
  Upload,
  Link2,
  ChevronRight,
  Cpu,
  Volume2,
  TrendingUp,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { MeshBackground } from '@/components/layout/MeshBackground';
import { cn } from '@/lib/utils';

/** Shared fade-up animation props helper. */
const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 24 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5, delay, ease: [0.25, 0.1, 0.25, 1] as const },
});



/* ── Data ── */
const STEPS = [
  {
    num: '01',
    title: 'Upload or paste a link',
    description:
      'Drop any MP4 or paste a YouTube / Vimeo URL. Files up to 2 GB are supported.',
    icon: <Upload className="h-5 w-5" />,
  },
  {
    num: '02',
    title: 'AI finds the best moments',
    description:
      'Our model scores every second for virality, emotion, and speech energy to pick the top clips.',
    icon: <Cpu className="h-5 w-5" />,
  },
  {
    num: '03',
    title: 'Edit, caption & export',
    description:
      'Trim clips in the text-based editor, add animated captions, and download 9:16 MP4s instantly.',
    icon: <Scissors className="h-5 w-5" />,
  },
];

const FEATURES = [
  {
    icon: <TrendingUp className="h-5 w-5" style={{ color: 'oklch(0.60 0.20 264)' }} />,
    title: 'AI Virality Scoring',
    description:
      'Analyzes emotional hooks, retention patterns, and speaking pacing to surface 90%+ viral moments.',
  },
  {
    icon: <Volume2 className="h-5 w-5" style={{ color: 'oklch(0.60 0.20 264)' }} />,
    title: 'Animated Captions',
    description:
      '99% accurate Whisper STT with Hormozi-style, Neon Cyberpunk, and Karaoke caption presets.',
  },
  {
    icon: <Layers className="h-5 w-5" style={{ color: 'oklch(0.60 0.20 264)' }} />,
    title: 'Smart B-Roll',
    description:
      'Extracts keywords and overlays HD stock footage from Pexels & Pixabay to maximize retention.',
  },
  {
    icon: <Scissors className="h-5 w-5" style={{ color: 'oklch(0.60 0.20 264)' }} />,
    title: 'Text-Based Trimming',
    description:
      'Click sentences in the interactive transcript to cut video — as easy as editing a document.',
  },
  {
    icon: <Wand2 className="h-5 w-5" style={{ color: 'oklch(0.60 0.20 264)' }} />,
    title: '9:16 Smart Reframe',
    description:
      'Converts landscape video to 1080×1920 vertical — perfect for Shorts, Reels, and TikTok.',
  },
  {
    icon: <Sparkles className="h-5 w-5" style={{ color: 'oklch(0.60 0.20 264)' }} />,
    title: 'Prompt-to-Shorts Generator',
    description:
      'Enter an idea or list (e.g. "Top 5 Monkey Facts") — AI writes the script, sources B-roll, and outputs ready shorts.',
  },
  {
    icon: <Zap className="h-5 w-5" style={{ color: 'oklch(0.60 0.20 264)' }} />,
    title: 'Batch Export & Render',
    description:
      'Generate dozens of unique shorts from a single long video or idea prompt. Burned animated subtitles included.',
  },
];

const STATS = [
  { value: '10×', label: 'Faster than manual editing' },
  { value: '99%', label: 'Caption accuracy' },
  { value: '2 GB', label: 'Max upload size' },
  { value: '9:16', label: 'Vertical format ready' },
];

/* ── Component ── */
export function HomePage() {
  const [heroMode, setHeroMode] = useState<'url' | 'text'>('text');
  const [quickUrl, setQuickUrl] = useState('');
  const [quickPrompt, setQuickPrompt] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (heroMode === 'text') {
      const q = quickPrompt.trim();
      navigate('/generate' + (q ? `?prompt=${encodeURIComponent(q)}` : ''));
    } else {
      navigate('/videos/new');
    }
  };

  return (
    <div className="relative min-h-screen overflow-x-hidden font-sans">
      <MeshBackground />

      {/* ══════════════════════════════════════════════
          Navigation
      ══════════════════════════════════════════════ */}
      <header
        className="sticky top-0 z-30 transition-all duration-500"
        style={{
          backgroundColor: 'oklch(0.08 0.025 264 / 90%)',
          backdropFilter: 'blur(20px)',
          borderBottom: '1px solid oklch(1 0 0 / 8%)',
        }}
      >
        <div className="mx-auto flex h-[68px] max-w-[1344px] items-center justify-between px-6 lg:px-8">
          {/* Logo */}
          <Link
            to="/"
            className="flex items-center gap-2.5 text-[15px] font-semibold text-foreground transition-opacity hover:opacity-80"
            aria-label="VideoToShorts home"
          >
            <div
              className="flex h-8 w-8 items-center justify-center rounded-lg"
              style={{ backgroundColor: 'oklch(0.60 0.20 264)' }}
            >
              <Clapperboard className="h-4 w-4 text-white" />
            </div>
            <span>
              Video<span style={{ color: 'oklch(0.60 0.20 264)' }}>ToShorts</span>
            </span>
          </Link>

          {/* Auth links */}
          <div className="flex items-center gap-2">
            <Link
              to="/login"
              className="rounded-full px-5 py-2 text-sm font-medium text-muted-foreground transition-all hover:text-foreground"
            >
              Log in
            </Link>
            <Link to="/register">
              <button
                className="inline-flex items-center gap-1.5 rounded-full border px-5 py-2 text-sm font-medium text-foreground transition-all duration-200 hover:bg-[oklch(1_0_0_/_14%)]"
                style={{
                  borderColor: 'oklch(1 0 0 / 15%)',
                  backgroundColor: 'oklch(1 0 0 / 8%)',
                }}
              >
                Get started
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
            </Link>
          </div>
        </div>
      </header>

      {/* ══════════════════════════════════════════════
          Hero
      ══════════════════════════════════════════════ */}
      <section className="relative z-10 mx-auto flex max-w-[1344px] flex-col items-center px-6 pb-20 pt-20 text-center lg:px-8 lg:pt-28">
        {/* Badge */}
        <motion.div
          {...fadeUp(0)}
          className="mb-7 inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-xs font-medium"
          style={{
            borderColor: 'oklch(0.60 0.20 264 / 35%)',
            backgroundColor: 'oklch(0.60 0.20 264 / 10%)',
            color: 'oklch(0.75 0.15 264)',
          }}
        >
          <Sparkles className="h-3.5 w-3.5" />
          AI-powered · 10× faster than manual editing
        </motion.div>

        {/* Headline */}
        <motion.h1
          {...fadeUp(0.1)}
          className="mb-6 max-w-4xl text-[42px] font-bold leading-[1.1] tracking-tight text-foreground sm:text-6xl lg:text-7xl"
        >
          Convert long videos into{' '}
          <span
            style={{
              background:
                'linear-gradient(135deg, oklch(0.60 0.20 264), oklch(0.75 0.15 264))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            viral Shorts
          </span>{' '}
          instantly
        </motion.h1>

        {/* Subheadline */}
        <motion.p
          {...fadeUp(0.2)}
          className="mx-auto mb-10 max-w-[600px] text-base leading-relaxed text-muted-foreground sm:text-lg"
        >
          Paste a YouTube link or upload a file. Our AI finds the best moments, adds
          animated captions, and exports 9:16 clips for Shorts, Reels, and TikTok — in
          seconds.
        </motion.p>

        {/* Mode Tabs */}
        <motion.div
          {...fadeUp(0.25)}
          className="mb-3 flex items-center justify-center gap-2"
        >
          <button
            type="button"
            onClick={() => setHeroMode('url')}
            className={cn(
              'flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-semibold transition-all',
              heroMode === 'url'
                ? 'bg-foreground/15 text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Link2 className="h-3.5 w-3.5" />
            Convert Video Link
          </button>
          <button
            type="button"
            onClick={() => setHeroMode('text')}
            className={cn(
              'flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-semibold transition-all',
              heroMode === 'text'
                ? 'bg-primary/20 text-primary border border-primary/40 shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Wand2 className="h-3.5 w-3.5 text-primary" />
            Generate from Idea / Prompt
            <span className="rounded-full bg-primary/25 px-1.5 py-0.2 text-[10px] font-bold uppercase text-primary">
              New
            </span>
          </button>
        </motion.div>

        {/* Input bar */}
        <motion.div
          {...fadeUp(0.3)}
          className="w-full max-w-2xl"
        >
          <form
            onSubmit={handleSubmit}
            className="flex flex-col gap-2 rounded-2xl border p-2 sm:flex-row"
            style={{
              borderColor: heroMode === 'text' ? 'oklch(0.60 0.20 264 / 35%)' : 'oklch(1 0 0 / 12%)',
              backgroundColor: 'oklch(1 0 0 / 5%)',
              backdropFilter: 'blur(16px)',
            }}
          >
            <div className="flex flex-1 items-center gap-2.5 px-3">
              {heroMode === 'url' ? (
                <Link2 className="h-4 w-4 shrink-0 text-muted-foreground" />
              ) : (
                <Sparkles className="h-4 w-4 shrink-0 text-primary" />
              )}
              <input
                id="hero-url-input"
                type="text"
                value={heroMode === 'url' ? quickUrl : quickPrompt}
                onChange={(e) =>
                  heroMode === 'url' ? setQuickUrl(e.target.value) : setQuickPrompt(e.target.value)
                }
                placeholder={
                  heroMode === 'url'
                    ? 'Paste YouTube, TikTok, or Vimeo link…'
                    : 'Enter topic or idea (e.g. Top 5 Monkey Facts, Mind-Blowing Space Secrets)…'
                }
                className="w-full bg-transparent py-2.5 text-sm text-foreground outline-none placeholder:text-muted-foreground"
              />
            </div>
            <button
              type="submit"
              id="hero-generate-btn"
              className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl px-6 py-3 text-sm font-semibold text-white transition-all duration-200 hover:opacity-90 sm:rounded-[14px]"
              style={{ backgroundColor: 'oklch(0.60 0.20 264)' }}
            >
              {heroMode === 'url' ? (
                <>
                  <Sparkles className="h-4 w-4" />
                  Convert to Shorts
                </>
              ) : (
                <>
                  <Wand2 className="h-4 w-4" />
                  Generate Shorts
                </>
              )}
            </button>
          </form>

          {/* Platform support / prompt suggestion row */}
          <div className="mt-3.5 flex flex-wrap items-center justify-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
            {heroMode === 'url' ? (
              <>
                <span>Supports:</span>
                {['YouTube', 'TikTok', 'Vimeo', 'MP4 upload up to 2 GB'].map((p) => (
                  <span
                    key={p}
                    className="flex items-center gap-1 font-medium text-foreground/70"
                  >
                    <CheckCircle2 className="h-3 w-3 text-primary" />
                    {p}
                  </span>
                ))}
              </>
            ) : (
              <>
                <span>Quick ideas:</span>
                {['Top 5 Monkey Facts', 'Top 3 Space Anomalies', 'Top 4 Psychology Life Hacks'].map((idea) => (
                  <button
                    key={idea}
                    type="button"
                    onClick={() => setQuickPrompt(idea)}
                    className="flex items-center gap-1 font-medium text-primary hover:underline cursor-pointer"
                  >
                    • {idea}
                  </button>
                ))}
              </>
            )}
          </div>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════
          Stats row
      ══════════════════════════════════════════════ */}
      <section className="relative z-10 mx-auto max-w-[1344px] px-6 pb-20 lg:px-8">
        <div
          className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border md:grid-cols-4"
          style={{
            borderColor: 'oklch(1 0 0 / 10%)',
            backgroundColor: 'oklch(1 0 0 / 5%)',
          }}
        >
          {STATS.map((stat) => (
            <div
              key={stat.label}
              className="flex flex-col items-center justify-center gap-1 px-6 py-8"
              style={{ backgroundColor: 'oklch(0.10 0.02 264)' }}
            >
              <span
                className="text-3xl font-bold"
                style={{ color: 'oklch(0.60 0.20 264)' }}
              >
                {stat.value}
              </span>
              <span className="text-center text-xs text-muted-foreground">
                {stat.label}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════════════════
          How it works
      ══════════════════════════════════════════════ */}
      <section className="relative z-10 mx-auto max-w-[1344px] px-6 pb-24 lg:px-8">
        <div className="mb-12 text-center">
          <h2 className="mb-3 text-3xl font-bold text-foreground sm:text-4xl">
            How it works
          </h2>
          <p className="mx-auto max-w-md text-sm text-muted-foreground">
            From raw video to ready-to-publish short — in under a minute.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {STEPS.map((step, i) => (
            <motion.div
              key={step.num}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1 }}
              className="relative rounded-2xl border p-6"
              style={{
                borderColor: 'oklch(1 0 0 / 10%)',
                backgroundColor: 'oklch(0.10 0.02 264)',
              }}
            >
              {/* Step number accent */}
              <div className="mb-5 flex items-center gap-3">
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-xl text-white"
                  style={{ backgroundColor: 'oklch(0.60 0.20 264 / 20%)', color: 'oklch(0.60 0.20 264)' }}
                >
                  {step.icon}
                </div>
                <span
                  className="text-3xl font-bold tabular-nums leading-none"
                  style={{ color: 'oklch(0.60 0.20 264 / 20%)' }}
                >
                  {step.num}
                </span>
              </div>
              <h3 className="mb-2 text-base font-semibold text-foreground">
                {step.title}
              </h3>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {step.description}
              </p>

              {/* Connector arrow between steps */}
              {i < STEPS.length - 1 && (
                <div className="absolute -right-3 top-1/2 z-10 -translate-y-1/2 hidden md:block">
                  <ArrowRight
                    className="h-5 w-5"
                    style={{ color: 'oklch(0.60 0.20 264 / 40%)' }}
                  />
                </div>
              )}
            </motion.div>
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════════════════
          Interactive preview mockup
      ══════════════════════════════════════════════ */}
      <section className="relative z-10 mx-auto max-w-[1344px] px-6 pb-24 lg:px-8">
        <div
          className="overflow-hidden rounded-2xl border"
          style={{
            borderColor: 'oklch(1 0 0 / 10%)',
            backgroundColor: 'oklch(0.10 0.02 264)',
          }}
        >
          {/* Panel header */}
          <div
            className="flex items-center justify-between border-b px-6 py-4"
            style={{ borderColor: 'oklch(1 0 0 / 8%)' }}
          >
            <div className="flex items-center gap-3">
              <div className="flex gap-1.5">
                {['bg-red-500/70', 'bg-yellow-500/70', 'bg-green-500/70'].map((c) => (
                  <div key={c} className={`h-2.5 w-2.5 rounded-full ${c}`} />
                ))}
              </div>
              <span className="text-xs font-medium text-muted-foreground">
                VideoToShorts — Live Preview
              </span>
            </div>
            <div
              className="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
              style={{
                backgroundColor: 'oklch(0.60 0.20 264 / 12%)',
                color: 'oklch(0.75 0.15 264)',
              }}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-current" />
              AI Virality Score: 96/100
            </div>
          </div>

          {/* Three-column layout */}
          <div className="grid grid-cols-1 items-center gap-6 p-6 md:grid-cols-3">
            {/* Input */}
            <div
              className="space-y-3 rounded-xl border p-4"
              style={{ borderColor: 'oklch(1 0 0 / 8%)', backgroundColor: 'oklch(0.08 0.025 264)' }}
            >
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span className="font-medium">Input — Long video</span>
                <span className="font-mono">45:00</span>
              </div>
              <div
                className="relative flex aspect-video items-center justify-center overflow-hidden rounded-lg border"
                style={{ borderColor: 'oklch(1 0 0 / 10%)', backgroundColor: 'oklch(0.06 0.02 264)' }}
              >
                <Play className="h-8 w-8 text-muted-foreground" />
                <span
                  className="absolute bottom-2 right-2 rounded px-1.5 py-0.5 font-mono text-[10px] text-white"
                  style={{ backgroundColor: 'oklch(0 0 0 / 70%)' }}
                >
                  Full Podcast
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Raw footage — transcribed and scored for high-energy hooks.
              </p>
            </div>

            {/* AI Engine */}
            <div className="flex flex-col items-center gap-4 py-4 text-center">
              <div
                className="flex h-14 w-14 items-center justify-center rounded-2xl"
                style={{
                  backgroundColor: 'oklch(0.60 0.20 264 / 15%)',
                  boxShadow: '0 0 32px oklch(0.60 0.20 264 / 20%)',
                }}
              >
                <Wand2 className="h-7 w-7" style={{ color: 'oklch(0.60 0.20 264)' }} />
              </div>
              <h3 className="text-sm font-semibold text-foreground">AI Engine</h3>
              <ul className="space-y-2 text-left">
                {[
                  'Hook detection (score 96)',
                  'Hormozi animated captions',
                  'Pexels B-roll overlay',
                ].map((item) => (
                  <li key={item} className="flex items-center gap-2 text-xs text-muted-foreground">
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-primary" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            {/* Output — 9:16 phone mockup */}
            <div className="flex flex-col items-center gap-3">
              <div
                className="relative flex w-36 flex-col justify-end overflow-hidden rounded-2xl border-2 pb-3 text-center"
                style={{
                  aspectRatio: '9/16',
                  borderColor: 'oklch(0.60 0.20 264 / 50%)',
                  backgroundColor: 'oklch(0.06 0.02 264)',
                  boxShadow: '0 8px 40px oklch(0.60 0.20 264 / 20%)',
                }}
              >
                <div className="absolute inset-0 flex items-center justify-center">
                  <Play className="h-8 w-8 text-white/50" />
                </div>
                <div
                  className="relative z-10 mx-2 mb-1 rounded border px-2 py-1"
                  style={{ borderColor: 'oklch(0.70 0.16 264 / 50%)', backgroundColor: 'oklch(0 0 0 / 60%)' }}
                >
                  <span className="text-[9px] font-black uppercase tracking-wider text-yellow-300">
                    This one technique
                  </span>
                </div>
                <span className="text-[9px] text-muted-foreground">
                  0:35 · 9:16 Short
                </span>
              </div>
              <span className="text-xs text-muted-foreground">Ready to publish</span>
            </div>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════
          Features grid
      ══════════════════════════════════════════════ */}
      <section className="relative z-10 mx-auto max-w-[1344px] px-6 pb-24 lg:px-8">
        <div className="mb-12 text-center">
          <h2 className="mb-3 text-3xl font-bold text-foreground sm:text-4xl">
            Everything you need to go viral
          </h2>
          <p className="mx-auto max-w-md text-sm text-muted-foreground">
            A full creative pipeline — from raw footage to publishing-ready shorts.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feat, i) => (
            <motion.div
              key={feat.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.07 }}
              className="group rounded-2xl border p-6 transition-all duration-300 hover:border-[oklch(0.60_0.20_264_/_35%)]"
              style={{
                borderColor: 'oklch(1 0 0 / 10%)',
                backgroundColor: 'oklch(0.10 0.02 264)',
              }}
            >
              <div
                className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl transition-all group-hover:shadow-[0_0_20px_oklch(0.60_0.20_264_/_25%)]"
                style={{ backgroundColor: 'oklch(0.60 0.20 264 / 12%)' }}
              >
                {feat.icon}
              </div>
              <h3 className="mb-1.5 text-sm font-semibold text-foreground">
                {feat.title}
              </h3>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {feat.description}
              </p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════════════════
          CTA Banner
      ══════════════════════════════════════════════ */}
      <section className="relative z-10 mx-auto max-w-[1344px] px-6 pb-28 lg:px-8">
        <div
          className="relative overflow-hidden rounded-2xl border p-12 text-center"
          style={{
            borderColor: 'oklch(0.60 0.20 264 / 25%)',
            backgroundColor: 'oklch(0.10 0.02 264)',
          }}
        >
          {/* Background glow */}
          <div
            className="pointer-events-none absolute inset-0 -z-[1]"
            style={{
              background:
                'radial-gradient(ellipse 60% 50% at 50% 100%, oklch(0.60 0.20 264 / 15%) 0%, transparent 70%)',
            }}
          />
          <h2 className="mb-3 text-3xl font-bold text-foreground sm:text-4xl">
            Start converting your videos today
          </h2>
          <p className="mx-auto mb-8 max-w-md text-sm text-muted-foreground">
            No credit card required. Upload a video and create your first viral short
            in minutes.
          </p>
          <Link to="/register" id="cta-signup-btn">
            <button
              className="inline-flex items-center gap-2 rounded-full px-8 py-3.5 text-sm font-semibold text-white transition-all duration-200 hover:opacity-90"
              style={{
                backgroundColor: 'oklch(0.60 0.20 264)',
                boxShadow: '0 0 32px oklch(0.60 0.20 264 / 35%)',
              }}
            >
              Get started for free
              <ArrowRight className="h-4 w-4" />
            </button>
          </Link>
        </div>
      </section>

      {/* ══════════════════════════════════════════════
          Footer
      ══════════════════════════════════════════════ */}
      <footer
        className="relative z-10 border-t"
        style={{ borderColor: 'oklch(1 0 0 / 8%)' }}
      >
        <div className="mx-auto flex max-w-[1344px] flex-col items-center justify-between gap-4 px-6 py-8 text-xs text-muted-foreground sm:flex-row lg:px-8">
          <div className="flex items-center gap-2 font-medium text-foreground">
            <Clapperboard className="h-4 w-4 text-primary" />
            VideoToShorts
          </div>
          <p>© {new Date().getFullYear()} VideoToShorts. All rights reserved.</p>
          <div className="flex gap-4">
            <Link to="/login" className="hover:text-foreground transition-colors">
              Log in
            </Link>
            <Link to="/register" className="hover:text-foreground transition-colors">
              Sign up
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
