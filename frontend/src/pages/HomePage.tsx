import { motion } from 'framer-motion';
import {
  ArrowRight,
  Film,
  Image,
  Mic,
  Scissors,
  Sparkles,
  Zap,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { MeshBackground } from '@/components/layout/MeshBackground';

const FEATURES = [
  {
    icon: <Mic className="h-7 w-7" />,
    title: 'Auto-Transcription',
    description:
      'Upload your video and get an accurate, word-level transcript powered by AI. Captions are generated and burned in automatically.',
  },
  {
    icon: <Sparkles className="h-7 w-7" />,
    title: 'AI Highlight Detection',
    description:
      'Our engine scores every segment of your video to find the most engaging moments — no manual scrubbing required.',
  },
  {
    icon: <Image className="h-7 w-7" />,
    title: 'Automatic B-Roll',
    description:
      'Relevant stock footage from Pexels and Pixabay is fetched and inserted automatically based on your content\'s keywords.',
  },
];

const STEPS = [
  {
    icon: <Film className="h-5 w-5" />,
    title: 'Upload',
    description: 'Drop a file or paste a URL',
  },
  {
    icon: <Zap className="h-5 w-5" />,
    title: 'Process',
    description: 'AI transcribes & finds highlights',
  },
  {
    icon: <Scissors className="h-5 w-5" />,
    title: 'Export',
    description: 'Download 9:16 shorts with captions',
  },
];

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.15 } },
};

const item = {
  hidden: { opacity: 0, y: 30 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: 'easeOut' as const },
  },
};

/**
 * Full marketing landing page: hero, feature highlights, how-it-works
 * steps, and a closing CTA — all using the app's glassmorphism design
 * system with brand gradients and micro-animations.
 */
export function HomePage() {
  return (
    <div className="relative min-h-screen overflow-hidden font-sans">
      <MeshBackground />

      {/* ------ Topbar ------ */}
      <header className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
        <Link
          to="/"
          className="flex items-center gap-2 text-lg font-bold text-foreground"
        >
          <Film className="h-6 w-6 text-primary" />
          VideoToShorts
        </Link>
        <div className="flex items-center gap-3">
          <Link
            to="/login"
            className="rounded-full px-5 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            Log in
          </Link>
          <Link to="/register">
            <GradientButton className="text-sm">Sign up free</GradientButton>
          </Link>
        </div>
      </header>

      {/* ------ Hero ------ */}
      <section className="relative z-10 mx-auto flex max-w-4xl flex-col items-center px-6 pb-20 pt-16 text-center sm:pt-24">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-xs font-medium text-primary"
        >
          <Sparkles className="h-3.5 w-3.5" />
          AI-Powered Video Repurposing
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1, ease: 'easeOut' }}
          className="mb-6 text-4xl font-extrabold leading-tight tracking-tight text-foreground sm:text-5xl md:text-6xl"
        >
          Turn long videos into{' '}
          <span className="bg-gradient-to-r from-gradient-from to-gradient-to bg-clip-text text-transparent">
            viral Shorts
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2, ease: 'easeOut' }}
          className="mx-auto mb-10 max-w-2xl text-lg text-muted-foreground"
        >
          Upload a video, and our AI automatically finds the best moments,
          transcribes them with captions, inserts B-roll, and renders
          ready-to-post 9:16 YouTube Shorts — in minutes, not hours.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.35, ease: 'easeOut' }}
          className="flex flex-wrap items-center justify-center gap-4"
        >
          <Link to="/register">
            <GradientButton className="gap-2 px-8 py-3.5 text-base">
              Get started free
              <ArrowRight className="h-4 w-4" />
            </GradientButton>
          </Link>
          <Link
            to="/login"
            className="flex items-center gap-1 rounded-full border border-border px-6 py-3 text-sm font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
          >
            I already have an account
          </Link>
        </motion.div>
      </section>

      {/* ------ How it works ------ */}
      <section className="relative z-10 mx-auto max-w-4xl px-6 pb-20">
        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.3 }}
          className="grid grid-cols-1 gap-4 sm:grid-cols-3"
        >
          {STEPS.map((step, i) => (
            <motion.div key={step.title} variants={item}>
              <GlassCard className="flex flex-col items-center gap-3 p-6 text-center">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-gradient-from to-gradient-to text-primary-foreground shadow-md">
                  {step.icon}
                </div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Step {i + 1}
                </p>
                <h3 className="text-lg font-bold text-foreground">
                  {step.title}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {step.description}
                </p>
              </GlassCard>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* ------ Features ------ */}
      <section className="relative z-10 mx-auto max-w-5xl px-6 pb-24">
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="mb-12 text-center text-3xl font-bold text-foreground"
        >
          Everything you need to{' '}
          <span className="bg-gradient-to-r from-gradient-from to-gradient-to bg-clip-text text-transparent">
            create faster
          </span>
        </motion.h2>

        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.2 }}
          className="grid grid-cols-1 gap-6 md:grid-cols-3"
        >
          {FEATURES.map((feature) => (
            <motion.div key={feature.title} variants={item}>
              <GlassCard className="flex h-full flex-col gap-4 p-7">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  {feature.icon}
                </div>
                <h3 className="text-lg font-bold text-foreground">
                  {feature.title}
                </h3>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {feature.description}
                </p>
              </GlassCard>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* ------ CTA ------ */}
      <section className="relative z-10 mx-auto max-w-3xl px-6 pb-24">
        <GlassCard className="flex flex-col items-center gap-6 p-10 text-center">
          <h2 className="text-2xl font-bold text-foreground sm:text-3xl">
            Ready to make your first Short?
          </h2>
          <p className="max-w-lg text-muted-foreground">
            Join creators who are already saving hours every week. Upload a
            video, let AI do the heavy lifting, and publish shorts that grow
            your channel.
          </p>
          <Link to="/register">
            <GradientButton className="gap-2 px-8 py-3.5 text-base">
              Start for free
              <ArrowRight className="h-4 w-4" />
            </GradientButton>
          </Link>
        </GlassCard>
      </section>

      {/* ------ Footer ------ */}
      <footer className="relative z-10 border-t border-glass-border bg-glass-bg py-8 backdrop-blur-lg">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-6 text-sm text-muted-foreground sm:flex-row">
          <div className="flex items-center gap-2 font-semibold text-foreground">
            <Film className="h-4 w-4 text-primary" />
            VideoToShorts
          </div>
          <p>&copy; {new Date().getFullYear()} VideoToShorts. All rights reserved.</p>
          <div className="flex gap-4">
            <Link
              to="/login"
              className="transition-colors hover:text-foreground"
            >
              Log in
            </Link>
            <Link
              to="/register"
              className="transition-colors hover:text-foreground"
            >
              Sign up
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
