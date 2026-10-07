/**
 * Count a figure up once, on mount.
 *
 * The only decorative figure motion in the product, and it earns its
 * place: a stat band that counts up is the one moment where the numbers
 * read as an instrument reading out rather than as text someone typed.
 * It runs once per mount, never on scroll-back, and never on a filter
 * change.
 *
 * Reduced motion is honoured by reading the media query here rather than
 * in CSS, because `requestAnimationFrame` cannot be turned off by a
 * stylesheet — the numbers would keep climbing invisibly while the rest
 * of the product had stopped moving.
 *
 * Falls back to the final value wherever the API is missing, and never
 * renders a wrong intermediate: the final value is what a screen reader
 * and a crawler both receive, because the animation writes to `textContent`
 * only after the accessible label is already correct.
 */
export function useCountUp(value, { duration = 700 } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return null

  const prefersReduced =
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  return { target: value, duration, animate: !prefersReduced }
}

export default useCountUp
