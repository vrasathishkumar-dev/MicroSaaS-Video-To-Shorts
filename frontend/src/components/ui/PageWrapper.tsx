import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface PageWrapperProps {
  children: ReactNode;
  className?: string;
}

/**
 * Fade/slide-in wrapper every route should render its content through,
 * so page transitions feel consistent across the app.
 */
export function PageWrapper({ children, className }: PageWrapperProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={cn('min-h-screen', className)}
    >
      {children}
    </motion.div>
  );
}
