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

/**
 * `IntersectionObserver` — a lifecycle-only stub, for the same reason.
 *
 * `ScholarshipDetailsPage` reveals its sections on scroll through
 * `useReveal` (`src/pages/ScholarshipDetailsPage.jsx:42`), and `Layout`,
 * `HomePage`, `TrustFlow`, `useScrollReveal` and `useReveal` all construct
 * one directly. jsdom implements neither the observer nor `IntersectionObserverEntry`,
 * so any test that renders one of those throws
 * `ReferenceError: IntersectionObserver is not defined` at the first
 * `new IntersectionObserver(...)` — reported against ScholarshipDetailsPage,
 * but the reference is shared.
 *
 * The stub records what it was told and never invokes the callback.
 * That is deliberate and is the limit of what it asserts: it makes the
 * observer *exist*, so a component's effects can run and a reveal can be
 * left un-triggered. It does not simulate scrolling, so a test must not
 * read a `sz-reveal` element's `is-visible` class as evidence that anything
 * scrolled — that would be asserting on the stub, not the browser. The one
 * existing test that needs a callback to fire (`ScholarshipsPage.test.jsx`)
 * supplies its own immediate stub and is unaffected.
 *
 * Guarded on `globalThis` so a future jsdom that ships the real parser wins,
 * and mirrored onto `window` because the components reach for it there.
 */
if (typeof globalThis.IntersectionObserver === 'undefined') {
  class IntersectionObserverMock {
    constructor(callback, options) {
      this.callback = callback
      this.options = options
      this.targets = new Set()
    }

    observe(target) {
      this.targets.add(target)
    }

    unobserve(target) {
      this.targets.delete(target)
    }

    disconnect() {
      this.targets.clear()
    }

    takeRecords() {
      return []
    }
  }

  globalThis.IntersectionObserver = IntersectionObserverMock

  if (typeof window !== 'undefined') {
    window.IntersectionObserver = IntersectionObserverMock
  }
}
