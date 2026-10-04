import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

/**
 * Test configuration, kept separate from `vite.config.js`.
 *
 * The build config is deliberately left untouched: `base` there is chosen per
 * deployment target, and a test-only field in that file risks being read as
 * build configuration. This file only describes how tests run.
 *
 * jsdom rather than a real browser because these tests assert rendering and
 * state transitions, not layout. Responsive behaviour is verified by reading the
 * stylesheet's own rules, which is the only place a breakpoint can actually be
 * proven - a jsdom query has no viewport, so a media-query assertion there would
 * be theatre.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
    include: ['src/**/*.test.{js,jsx}'],
    // The CSS files import design tokens that jsdom does not need to parse for
    // assertions, and processing them through PostCSS only slows the run down.
    css: false,
    restoreMocks: true,
  },
})