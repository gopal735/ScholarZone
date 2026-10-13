import { Suspense, lazy, useCallback, useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { useHelpCenter } from '../hooks/useHelpCenter.js'
import { useTutorialsI18n } from '../i18n/useTutorialsI18n.js'
import { tutorialIdForRoute } from '../lib/routeMap.js'

/**
 * The heavy half of the panel: the tutorial prose, in both languages.
 *
 * Lazy so a feature page pays for it only when a reader opens the guide. Seven
 * pages mount `HowToUse`, so importing this eagerly put every tutorial's text in
 * the initial bundle — about 138 kB — for the readers who never open one.
 */
const TutorialDetail = lazy(() =>
  import('./TutorialDetail.jsx').then((module) => ({ default: module.TutorialDetail })),
)

/**
 * The contextual "How to use this" entry on a feature page.
 *
 * ## Why it takes a route and not a tutorial id
 *
 * A page knows where it is, not what its tutorial is called. Passing the route
 * means the mapping is the registry's job, and a page that is renamed cannot
 * leave a guide pointing at a route that no longer exists. The lookup is a tiny
 * route map, not the tutorial prose, so this component is cheap to mount even on
 * a page that never shows a guide.
 *
 * ## Why it says nothing when there is no tutorial
 *
 * A button that opens an empty panel is worse than no button.
 * `/consistency-review` is the live case: it is behind the feature's own flag
 * and deliberately has no tutorial, so this renders nothing there rather than a
 * control whose panel would say "not written yet".
 *
 * ## Why the panel is not a modal
 *
 * It renders in flow below the trigger, so it cannot cover a primary action and
 * cannot trap a keyboard user. Opening it does not move focus — a page that
 * jumps when a control is clicked is disorienting for a screen-reader user, and
 * the panel is the next thing in reading order anyway. Closing returns focus to
 * the trigger; without that, Escape leaves the keyboard at the top of the
 * document.
 *
 * ## What it does not do
 *
 * It does not appear on load. Nothing auto-shows, nothing steals focus to sell
 * itself, and a dismissal is remembered per tutorial, so a reader who has hidden
 * one guide is not sold the same thing on every visit.
 */
export function HowToUse({ route }) {
  const { t } = useTutorialsI18n()
  // Dismissal is handed to the tutorial's own control rather than being read
  // here, so this component's job is only where the panel goes and what it shows.
  const { dismiss } = useHelpCenter()
  const [open, setOpen] = useState(false)

  const triggerRef = useRef(null)
  const panelId = useId()
  const tutorialId = tutorialIdForRoute(route)

  /**
   * No effect here to clear a dismissal.
   *
   * The first version reopened the guide on every open, which wrote to storage
   * on a render it did not cause and offered the guide regardless of what the
   * reader had asked for. A reader who dismissed it can reopen it from the
   * tutorial's own control, which is one click further away but is a choice they
   * made rather than one the page overrides.
   */
  const close = useCallback(() => {
    setOpen(false)
    // Return focus to the trigger. Without this, closing with Escape leaves the
    // keyboard at the top of the document, which is a trap of a different kind.
    triggerRef.current?.focus()
  }, [])

  // Escape closes, from anywhere on the document, so a keyboard user does not
  // have to tab back to the trigger to dismiss it.
  useEffect(() => {
    if (!open) return undefined
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        close()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, close])

  if (!tutorialId) {
    return null
  }

  return (
    <div className="ts-howto">
      <div className="ts-howto__bar">
        <button
          type="button"
          ref={triggerRef}
          className="ts-btn ts-btn--howto"
          aria-expanded={open}
          aria-controls={open ? panelId : undefined}
          onClick={() => setOpen((value) => !value)}
        >
          {t('button.howToUse')}
        </button>
      </div>

      {open ? (
        <div
          className="ts-howto__panel"
          id={panelId}
          role="region"
          aria-label={`${t('button.howToUseLong')}`}
        >
          <Suspense
            fallback={
              <p className="ts-empty" role="status">
                {t('tutorial.loading')}
              </p>
            }
          >
            <TutorialDetail
              tutorialId={tutorialId}
              onClose={close}
              onDismiss={() => dismiss(tutorialId)}
            />
          </Suspense>
          <p className="ts-howto__footer">
            <Link to="/help" className="ts-link">
              {t('button.openHelpCenter')}
            </Link>
          </p>
        </div>
      ) : null}
    </div>
  )
}
