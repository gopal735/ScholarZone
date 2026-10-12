import { useEffect, useRef } from 'react'
import { useJourneyI18n } from '../i18n/useJourneyI18n.js'
import { BilingualText } from './ui/primitives.jsx'

/**
 * The standing guidance disclaimer.
 *
 * Always rendered, never collapsible, and never a first-run-only interstitial:
 * the whole value of the feature depends on the student knowing that the
 * authority for every requirement, deadline and decision sits with the
 * university, provider, government authority or embassy — not with this tool.
 *
 * It is a `region` with a label rather than a decorative note, so it can be
 * reached by a screen-reader user navigating by landmark.
 */
export function JourneyDisclaimer() {
  const { t, both, mode } = useJourneyI18n()
  const title = both('disclaimer.title')
  const body = mode === 'en' ? { primary: t('disclaimer.body'), secondary: null } : { primary: t('disclaimer.body'), secondary: null }
  const privacyTitle = both('disclaimer.privacy.title')
  const privacyBody = { primary: t('disclaimer.privacy.body'), secondary: null }

  return (
    <aside className="jdisclaimer" aria-labelledby="jdisclaimer-title">
      <div className="jdisclaimer__block">
        <h2 className="jdisclaimer__title" id="jdisclaimer-title">
          <span className="jbilingual__primary">{title.primary}</span>
          {title.secondary ? (
            <span className="jbilingual__secondary" lang="en">
              {title.secondary}
            </span>
          ) : null}
        </h2>
        <p className="jdisclaimer__body">
          {mode === 'both' ? (
            <>
              <span lang="bn">{t('disclaimer.body')}</span>
              <span className="jdisclaimer__en" lang="en">
                {both('disclaimer.body').secondary}
              </span>
            </>
          ) : (
            body.primary
          )}
        </p>
      </div>

      <div className="jdisclaimer__block">
        <h3 className="jdisclaimer__subtitle">
          <span className="jbilingual__primary">{privacyTitle.primary}</span>
          {privacyTitle.secondary ? (
            <span className="jbilingual__secondary" lang="en">
              {privacyTitle.secondary}
            </span>
          ) : null}
        </h3>
        <p className="jdisclaimer__body">
          {mode === 'both' ? (
            <>
              <span lang="bn">{t('disclaimer.privacy.body')}</span>
              <span className="jdisclaimer__en" lang="en">
                {both('disclaimer.privacy.body').secondary}
              </span>
            </>
          ) : (
            privacyBody.primary
          )}
        </p>
      </div>
    </aside>
  )
}

/**
 * Non-blocking storage notice.
 *
 * A `status` region so a change to storage availability is announced, and never
 * a blocking modal: the workspace stays usable in memory, and the student can
 * still export what they have entered. The copy states the actual condition
 * rather than a generic "something went wrong", because "your progress will not
 * be kept" and "this save was refused" need different responses.
 */
export function StorageNotice({ problem }) {
  const { t } = useJourneyI18n()
  const liveRef = useRef(null)

  useEffect(() => {
    liveRef.current?.setAttribute('aria-live', 'polite')
  }, [])

  if (!problem) return null

  const titleKey =
    problem === 'unavailable'
      ? 'storage.unavailable.title'
      : problem === 'quota-exceeded'
        ? 'storage.quota.title'
        : problem === 'corrupt-json' || problem === 'invalid-schema'
          ? 'storage.corrupt.title'
          : 'storage.unsupported.title'
  const bodyKey =
    problem === 'unavailable'
      ? 'storage.unavailable.body'
      : problem === 'quota-exceeded'
        ? 'storage.quota.body'
        : problem === 'corrupt-json' || problem === 'invalid-schema'
          ? 'storage.corrupt.body'
          : 'storage.unsupported.body'

  return (
    <div className="jnotice jnotice--warning" role="status" ref={liveRef} data-problem={problem}>
      <p className="jnotice__title">{t(titleKey)}</p>
      <p className="jnotice__body">{t(bodyKey)}</p>
    </div>
  )
}

export { BilingualText }
