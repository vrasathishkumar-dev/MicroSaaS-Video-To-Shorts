import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.08 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

export interface AnimatedListProps {
  children: ReactNode[];
  className?: string;
  itemClassName?: string;
}

/**
 * Wraps a list of items with a staggered fade/slide-in animation.
 * Give each item a stable `key` at the call site as usual.
 */
export function AnimatedList({
  children,
  className,
  itemClassName,
}: AnimatedListProps) {
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={containerVariants}
      className={cn('flex flex-col gap-4', className)}
    >
      {children.map((child, index) => (
        <motion.div key={index} variants={itemVariants} className={itemClassName}>
          {child}
        </motion.div>
      ))}
    </motion.div>
  );
}
