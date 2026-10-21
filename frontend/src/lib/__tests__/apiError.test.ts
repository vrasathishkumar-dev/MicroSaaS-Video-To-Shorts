import { describe, expect, it } from 'vitest';
import { getApiErrorMessage } from '../apiError';

const wrap = (detail: unknown) => ({ response: { data: { detail } } });

describe('getApiErrorMessage', () => {
  it('returns string detail', () => expect(getApiErrorMessage(wrap('Nope'), 'fb')).toBe('Nope'));
  it('joins validation array msgs', () =>
    expect(getApiErrorMessage(wrap([{ type: 'x', loc: [], msg: 'A' }, { msg: 'B' }]), 'fb')).toBe('A; B'));
  it('falls back', () => {
    expect(getApiErrorMessage(new Error('x'), 'fb')).toBe('fb');
    expect(getApiErrorMessage(wrap([]), 'fb')).toBe('fb');
  });
});
