import { motion, type HTMLMotionProps } from 'framer-motion';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface GlassCardProps extends HTMLMotionProps<'div'> {
  children: ReactNode;
  className?: string;
}

/**
 * Frosted-glass container with a subtle rise-on-hover elevation effect.
 * Use for dashboard tiles, form panels, and content cards throughout the app.
 */
export function GlassCard({ children, className, ...props }: GlassCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02, y: -5 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={cn(
        'rounded-2xl border border-glass-border bg-glass-bg p-6 shadow-xl backdrop-blur-lg',
        className,
      )}
      {...props}
    >
      {children}
    </motion.div>
  );
}
