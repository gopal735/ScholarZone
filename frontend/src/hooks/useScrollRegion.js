import { useEffect, useRef } from 'react'

/**
 * Marks a horizontally scrollable region, and makes it focusable only when
 * it actually scrolls.
 *
 * Two jobs, one observer. A container that is focusable but does not scroll
 * is an interactive element that does nothing, which is its own accessibility
 * problem; a container that scrolls but is not focusable cannot be reached with
 * the keyboard at all, which fails SC 2.1.1. Measuring first answers which of
 * the two this region is.
 *
 * The measurement also drives the edge fade in .sz-table-scroll, which is
 * scoped to [data-overflowing='true'] so a non-scrolling table does not get a
 * permanent gradient across its last column.
 */
export function useScrollRegion() {
  const ref = useRef(null)

  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined

    const measure = () => {
      const overflowing = el.scrollWidth > el.clientWidth + 1
      el.dataset.overflowing = String(overflowing)
      el.tabIndex = overflowing ? 0 : -1
    }

    const observer = new ResizeObserver(measure)
    observer.observe(el)
    measure()

    return () => observer.disconnect()
  }, [])

  return ref
}

export default useScrollRegion
