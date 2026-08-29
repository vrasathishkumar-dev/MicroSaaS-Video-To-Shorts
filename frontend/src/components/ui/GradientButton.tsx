import { motion, type HTMLMotionProps } from 'framer-motion';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface GradientButtonProps extends HTMLMotionProps<'button'> {
  children: ReactNode;
  className?: string;
  variant?: 'solid' | 'outline';
}

/**
 * Primary call-to-action button with the brand gradient and press/hover
 * micro-interactions. Use for every primary action per skills/FRONTEND.md.
 */
export function GradientButton({
  children,
  className,
  variant = 'solid',
  type = 'button',
  ...props
}: GradientButtonProps) {
  return (
    <motion.button
      type={type}
      whileHover={{ scale: 1.02, y: -2 }}
      whileTap={{ scale: 0.98 }}
      transition={{ duration: 0.15, ease: 'easeOut' }}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-full px-6 py-3 font-semibold transition-shadow disabled:pointer-events-none disabled:opacity-50',
        variant === 'solid' &&
          'bg-gradient-to-r from-gradient-from to-gradient-to text-primary-foreground shadow-md hover:shadow-lg',
        variant === 'outline' &&
          'border border-primary text-primary hover:bg-accent',
        className,
      )}
      {...props}
    >
      {children}
    </motion.button>
  );
}
