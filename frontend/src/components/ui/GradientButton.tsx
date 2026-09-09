import { motion, type HTMLMotionProps } from 'framer-motion';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface GradientButtonProps extends HTMLMotionProps<'button'> {
  children: ReactNode;
  className?: string;
  variant?: 'primary' | 'outline' | 'ghost';
}

/**
 * CTA button — Restream-inspired.
 * "primary" = solid blue fill (main CTA).
 * "outline"  = semi-transparent white border (secondary action, matches Restream's "Get started" style).
 * "ghost"    = no border, dimmed text (tertiary/nav links).
 */
export function GradientButton({
  children,
  className,
  variant = 'primary',
  type = 'button',
  ...props
}: GradientButtonProps) {
  return (
    <motion.button
      type={type}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      transition={{ duration: 0.15, ease: 'easeOut' }}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-full font-medium transition-all duration-200 disabled:pointer-events-none disabled:opacity-40 text-sm',
        variant === 'primary' &&
          'bg-primary text-primary-foreground px-6 py-2.5 shadow-[0_0_24px_oklch(0.60_0.20_264_/_30%)] hover:bg-[oklch(0.65_0.20_264)] hover:shadow-[0_0_32px_oklch(0.60_0.20_264_/_45%)]',
        variant === 'outline' &&
          'border border-[oklch(1_0_0_/_15%)] bg-[oklch(1_0_0_/_8%)] text-foreground px-5 py-2 hover:bg-[oklch(1_0_0_/_14%)] hover:border-[oklch(1_0_0_/_25%)]',
        variant === 'ghost' &&
          'text-muted-foreground px-4 py-2 hover:text-foreground hover:bg-[oklch(1_0_0_/_6%)]',
        className,
      )}
      {...props}
    >
      {children}
    </motion.button>
  );
}
