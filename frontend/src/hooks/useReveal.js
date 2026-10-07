import { useEffect } from 'react'

/**
 * Scroll reveal, built so that content is NEVER invisible by default.
 *
 * The ordering here is the whole point, and it is the inverse of the
 * usual implementation:
 *
 *   1. CSS renders `[data-reveal]` as VISIBLE.
 *   2. This module confirms it has a working IntersectionObserver.
 *   3. Only then does it add `js-motion` to <html>, which is the single
 *      selector that hides anything.
 *
 * So if the module never runs, if the browser lacks
 * IntersectionObserver, if an error throws mid-effect, or if a build step
 * drops it, the page is still fully readable. The previous
 * implementation hid content in CSS and revealed it from JS, which is
 * why fast scrolling produced blank voids.
 *
 * Three further guarantees, in order of how much they matter:
 *   · anything marked data-motion="now" never waits for anything
 *   · each target unobserves after its first fire, so there is no
 *     ongoing cost once the page has settled
 *   · a failsafe timer reveals anything still hidden, which covers the
 *     case where an element is inside a container that never intersects
 *     (an off-screen drawer, a collapsed panel, a zero-height parent)
 *
 * @param {boolean} [enabled] Skip the effect entirely where motion is
 *   not wanted — a print stylesheet, or a view that has its own
 *   choreography.
 */
export function useReveal(enabled = true) {
  useEffect(() => {
    if (!enabled) return undefined

    const supportsObserver = typeof window !== 'undefined' && 'IntersectionObserver' in window
    if (!supportsObserver) return undefined

    // The reduced-motion query is read up front but does NOT skip
    // anything: reduced motion still needs `js-motion` so the reveal
    // resolves to a fade rather than to a jump. motion.css collapses
    // the tokens for this case.
    const selector = '[data-reveal]:not([data-motion="now"])'
    const root = document.documentElement

    let failsafe = 0

    const reveal = (node) => {
      if (!node || node.dataset.revealDone === 'true') return
      node.dataset.revealDone = 'true'
      node.style.removeProperty('opacity')
      node.style.removeProperty('animation-name')
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          reveal(entry.target)
          observer.unobserve(entry.target)
        }
      },
      {
        threshold: 0.15,
        // Fire slightly before the element is fully in view so the
        // motion is already underway when the reader's eye arrives.
        rootMargin: '0px 0px -8% 0px',
      },
    )

    const observeAll = () => {
      document.querySelectorAll(selector).forEach((node) => {
        if (node.dataset.revealBound === 'true') return
        node.dataset.revealBound = 'true'

        // The stagger index is clamped to 6 inside motion.css via
        // min(), so a 24-row list does not take a second to reach its
        // first screen. It is written here rather than in CSS because
        // CSS has no reliable sibling-index() across engines.
        if (!node.style.getPropertyValue('--i')) {
          const group = node.dataset.revealGroup
          const index = group ? indexWithinGroup(node, group) : 0
          node.style.setProperty('--i', String(index))
        }

        observer.observe(node)
      })
    }

    // Marked before observing, so elements already on screen are not
    // missed between the class landing and the first observer callback.
    root.classList.add('js-motion')
    observeAll()

    // Late content — anything rendered after a fetch — has to be picked
    // up without a full re-scan on every render.
    const mutations = new MutationObserver(() => observeAll())
    mutations.observe(document.body, { childList: true, subtree: true })

    failsafe = window.setTimeout(() => {
      document.querySelectorAll(selector).forEach(reveal)
    }, 1200)

    return () => {
      window.clearTimeout(failsafe)
      mutations.disconnect()
      observer.disconnect()
      root.classList.remove('js-motion')
      // `is-visible` would leave a stale class on nodes React reuses
      // across a route change, which is how a page ends up permanently
      // blank. Clear the binding state so the next mount re-observes.
      document.querySelectorAll('[data-reveal]').forEach((node) => {
        delete node.dataset.revealBound
        delete node.dataset.revealDone
      })
    }
  }, [enabled])
}

/** Position of `node` among the reveal targets that share its group. */
function indexWithinGroup(node, group) {
  const peers = node.ownerDocument.querySelectorAll(`[data-reveal-group="${group}"]`)
  return Math.min(Array.prototype.indexOf.call(peers, node), 12)
}

export default useReveal
