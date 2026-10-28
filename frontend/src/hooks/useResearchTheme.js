import { useEffect, useState } from 'react'

/* ═══════════════════════════════════════════════════════════════════
   useResearchTheme

   The active theme, read from the document rather than from context.

   The document element carries ``data-theme`` because that is the single
   place the whole design system reads it from — every token in
   styles/tokens.css hangs off that attribute. A component that wants to
   know the theme therefore has two options: it can depend on the provider
   that writes the attribute, or it can read the attribute itself.

   Reading it is the better default for a small number of components
   (the 3D hero, the chart palette), because it makes them usable
   anywhere in the tree instead of only inside the provider, and it means
   they can never be out of step with the styling they are trying to
   match — the attribute is the truth.

   It is also why this subscribes with a MutationObserver rather than
   reading once: the attribute can change from the theme toggle, from
   the persistence layer restoring a stored preference, or from a system
   preference change, and a component that only sampled it on mount would
   silently keep the old palette.

   Not a replacement for useTheme inside application components. Use
   that one when you need to *write* the theme; use this one only when
   you need to *follow* it.
   ═══════════════════════════════════════════════════════════════════ */

const THEME_ATTRIBUTE = 'data-theme'
const FALLBACK_THEME = 'light'

function readTheme() {
  if (typeof document === 'undefined') return FALLBACK_THEME
  return document.documentElement?.getAttribute(THEME_ATTRIBUTE) || FALLBACK_THEME
}

export function useResearchTheme() {
  const [theme, setTheme] = useState(readTheme)

  useEffect(() => {
    if (typeof document === 'undefined' || !('MutationObserver' in window)) return

    const observer = new MutationObserver(() => {
      const next = readTheme()
      setTheme((current) => (current === next ? current : next))
    })
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: [THEME_ATTRIBUTE],
    })

    return () => observer.disconnect()
  }, [])

  return { theme, isDark: theme === 'dark', isLight: theme === 'light' }
}

export default useResearchTheme
