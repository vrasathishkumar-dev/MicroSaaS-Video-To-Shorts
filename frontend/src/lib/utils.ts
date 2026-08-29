import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind class names conditionally, resolving conflicting
 * utility classes the same way shadcn/ui components expect.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
