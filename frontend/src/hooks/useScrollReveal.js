import { useEffect } from 'react'

/**
 * Adds `is-in` to cards and sections as they enter the viewport, staggering
 * the cards so a page arrives as a sequence rather than a wall.
 *
 * Two things this must never do:
 *
 * 1. Leave content invisible. The hidden state is gated behind a `js-reveal`
 *    class that is only set once an observer is attached, so a browser without
 *    IntersectionObserver — or a hook that runs before the list has rendered —
 *    shows everything immediately rather than opacity 0 forever.
 *
 * 2. Miss late content. The catalogue renders its cards after the fetch
 *    resolves, so a single scan on mount finds nothing. A MutationObserver
 *    picks up cards as they appear instead of re-scanning on a timer.
 */
let observer = null

function getObserver() {
  if (observer || typeof IntersectionObserver === 'undefined') {
    return observer
  }
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) {
          continue
        }
        entry.target.classList.add('is-in')
        observer.unobserve(entry.target)
      }
    },
    // Fires a little after the element settles, so a card does not animate
    // while a lazy image is still moving it.
    { rootMargin: '0px 0px -8% 0px', threshold: 0.01 },
  )
  return observer
}

const SELECTOR = '.sz-reveal, .scholarship-card'

export function useScrollReveal() {
  useEffect(() => {
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const io = getObserver()

    const apply = (nodes) => {
      let index = 0
      nodes.forEach((node) => {
        if (node.classList.contains('is-in')) {
          return
        }
        if (node.classList.contains('scholarship-card')) {
          node.style.transitionDelay = reduced ? '0ms' : `${Math.min(index, 12) * 40}ms`
        }
        index += 1
        if (reduced || !io) {
          node.classList.add('is-in')
          return
        }
        io.observe(node)
      })
    }

    if (reduced || !io) {
      document.querySelectorAll(SELECTOR).forEach((node) => node.classList.add('is-in'))
      return undefined
    }

    // Only now is it safe to hide anything.
    document.documentElement.classList.add('js-reveal')
    apply(document.querySelectorAll(SELECTOR))

    const mo = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType !== 1) {
            continue
          }
          const self = node.matches?.(SELECTOR) ? [node] : []
          const inner = node.querySelectorAll ? node.querySelectorAll(SELECTOR) : []
          if (self.length || inner.length) {
            apply([...self, ...inner])
          }
        }
      }
    })
    mo.observe(document.body, { childList: true, subtree: true })

    // Failsafe. If a node is never intersected — an offscreen card inside a
    // collapsed container, say — it still has to become visible.
    const failsafe = window.setTimeout(() => {
      document.querySelectorAll(`${SELECTOR}:not(.is-in)`).forEach((node) => {
        node.classList.add('is-in')
      })
    }, 2500)

    return () => {
      window.clearTimeout(failsafe)
      mo.disconnect()
      document.documentElement.classList.remove('js-reveal')
      document.querySelectorAll(SELECTOR).forEach((node) => {
        node.classList.remove('is-in')
        node.style.transitionDelay = ''
        if (io) {
          io.unobserve(node)
        }
      })
    }
  }, [])
}