import { motion, type HTMLMotionProps } from 'framer-motion';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface GlassCardProps extends HTMLMotionProps<'div'> {
  children: ReactNode;
  className?: string;
}

/**
 * Dark card surface — Restream-inspired.
 * Slightly elevated dark panel with a subtle white border and soft shadow.
 * Use for all content panels, form sections, and data tiles throughout the app.
 */
export function GlassCard({ children, className, ...props }: GlassCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className={cn(
        'rounded-[20px] border border-glass-border bg-card p-6 shadow-[0_4px_32px_rgba(0,0,0,0.4)]',
        className,
      )}
      {...props}
    >
      {children}
    </motion.div>
  );
}
