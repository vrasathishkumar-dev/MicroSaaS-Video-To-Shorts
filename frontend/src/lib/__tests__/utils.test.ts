import { describe, expect, it } from 'vitest';
import { cn } from '@/lib/utils';

describe('cn', () => {
  it('merges plain class names with a space', () => {
    expect(cn('a', 'b')).toBe('a b');
  });

  it('resolves conflicting Tailwind utility classes, keeping the last one', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4');
  });

  it('drops falsy values', () => {
    const shouldInclude = false;
    expect(cn('a', shouldInclude && 'b', undefined, null, 'c')).toBe('a c');
  });

  it('supports conditional object syntax', () => {
    expect(cn('base', { active: true, hidden: false })).toBe('base active');
  });
});
