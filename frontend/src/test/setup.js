/**
 * Test environment setup.
 *
 * Two shims and nothing else. Both exist because jsdom does not implement
 * something the application genuinely uses, and stubbing them is more honest
 * than changing the application to suit the test runner.
 */

import '@testing-library/jest-dom/vitest'

/**
 * `useReducedMotion` reads `prefers-reduced-motion` through matchMedia.
 *
 * jsdom does not implement matchMedia at all, so without this the hook throws
 * and every component using it fails for a reason unrelated to what is being
 * tested. Defaults to "no preference", which is the motion-enabled path - the
 * reduced-motion path is asserted explicitly by the tests that care about it.
 */
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
    dispatchEvent() {
      return false
    },
  })
}

/** Lets a test opt into the reduced-motion branch. */
export function setReducedMotion(matches) {
  window.matchMedia = (query) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
    dispatchEvent() {
      return false
    },
  })
}