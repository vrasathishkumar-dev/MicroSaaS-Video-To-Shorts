import '@testing-library/jest-dom';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// Ensure each test starts from a clean DOM/mocks.
afterEach(() => {
  cleanup();
  localStorage.clear();
});

// jsdom doesn't implement matchMedia; several UI primitives (and libraries
// like framer-motion in some code paths) probe for it.
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

// jsdom doesn't implement IntersectionObserver, which framer-motion and
// some viewport-aware components probe for.
if (typeof window !== 'undefined' && !window.IntersectionObserver) {
  class MockIntersectionObserver {
    readonly root: Element | Document | null = null;
    readonly rootMargin: string = '';
    readonly scrollMargin: string = '';
    readonly thresholds: ReadonlyArray<number> = [];
    disconnect() {}
    observe() {}
    takeRecords(): IntersectionObserverEntry[] {
      return [];
    }
    unobserve() {}
  }

  window.IntersectionObserver =
    MockIntersectionObserver as unknown as typeof IntersectionObserver;
}

// jsdom doesn't implement ResizeObserver either.
if (typeof window !== 'undefined' && !window.ResizeObserver) {
  class MockResizeObserver implements ResizeObserver {
    disconnect() {}
    observe() {}
    unobserve() {}
  }

  window.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;
}
