import { useEffect, useState } from 'react'

import { useHelpCenter } from '../hooks/useHelpCenter.js'
import { useTutorialsI18n } from '../i18n/useTutorialsI18n.js'

/**
 * A single tutorial, rendered.
 *
 * One component for every surface that shows a tutorial — the reader panel in the
 * Help Center, the contextual drawer on a feature page. A second copy would
 * drift, and the drift would show up as the same guide reading differently
 * depending on how you found it.
 *
 * ## Why it takes an id and looks the tutorial up
 *
 * It keeps the prose out of the component's own module graph, so a page that
 * only needs to know *whether* a guide exists does not download it. The lookup is
 * a dynamic import of the registry, cached by the module system after the first
 * open.
 *
 * ## What is not here
 *
 * Any claim of authority the feature does not have. `notGuarantee` is always
 * rendered, in both languages, never collapsed: a reader who reaches the end of
 * a guide must read what it cannot promise them, not be spared it.
 *
 * ## Heading levels
 *
 * The tutorial title is an `h2` and each section an `h3`. The pages that host
 * this render an `h1` themselves, so the outline lands at three levels with no
 * gap.
 */
export function TutorialDetail({ tutorial, tutorialId, onDismiss, onClose }) {
  const { t, prose } = useTutorialsI18n()
  const { isDismissed, dismiss, reopen, problem } = useHelpCenter()

  /**
   * The tutorial to render, resolved from whichever form the caller had.
   *
   * The eager case (`tutorial` passed in) is settled in the initial state, so no
   * effect runs for it. The id case starts as `loading` and resolves through the
   * import. Splitting them this way matters: an effect that called setState on
   * every render was flagged as a cascading-render risk, and the eager path is
   * the common one — it is how the Help Center renders an already-loaded guide.
   */
  const [loaded, setLoaded] = useState(() =>
    tutorial
      ? { tutorial, state: 'ready' }
      : { tutorial: null, state: tutorialId ? 'loading' : 'missing' },
  )

  // Only the id path needs a lookup. A caller that passes an object — or neither
  // prop — is settled by the initial state above, so this effect is skipped for
  // them entirely rather than calling setState on a render it did not cause.
  useEffect(() => {
    if (!tutorialId) return undefined

    let cancelled = false
    import('../lib/registry.js')
      .then((module) => {
        if (cancelled) return
        // The prop is only consulted when the id lookup missed nothing, so an
        // explicitly-passed object always wins and the id is a fallback.
        const found =
          module.tutorialForRoute(tutorialId) ||
          module.TUTORIALS.find((entry) => entry.id === tutorialId) ||
          null
        setLoaded({ tutorial: found, state: found ? 'ready' : 'missing' })
      })
      .catch(() => {
        if (!cancelled) setLoaded({ tutorial: null, state: 'failed' })
      })

    return () => {
      cancelled = true
    }
  }, [tutorialId])

  if (loaded.state === 'loading') {
    return (
      <p className="ts-empty" role="status">
        {t('tutorial.loading')}
      </p>
    )
  }

  const active = loaded.tutorial
  if (!active) {
    return (
      <div className="ts-noresults" role="status">
        <h2>{t('search.noResults')}</h2>
        <p>{t('tutorial.empty')}</p>
      </div>
    )
  }

  const dismissed = isDismissed(active.id)
  const { primary, secondary } = prose(active.navLabel)

  return (
    <article className="ts-detail" aria-labelledby={`ts-detail-${active.id}`}>
      <div className="ts-detail__head">
        {onClose ? (
          <button type="button" className="ts-btn ts-btn--quiet" onClick={onClose}>
            {t('button.close')}
          </button>
        ) : null}
      </div>

      <h2 className="ts-detail__title" id={`ts-detail-${active.id}`}>
        {primary}
        {secondary ? <span className="ts-detail__title-en">{secondary}</span> : null}
      </h2>

      <p className="ts-detail__meta">
        <span className="ts-tag">{t(`category.${active.category}`)}</span>
        {active.audience === 'admin' ? (
          <span className="ts-tag ts-tag--admin">{t('route.admin')}</span>
        ) : null}
        {active.audience === 'auth' ? (
          <span className="ts-tag">{t('route.auth')}</span>
        ) : null}
      </p>

      <Section title={t('section.whatItDoes')}>
        <p>{prose(active.purpose).primary}</p>
      </Section>

      <Section title={t('section.whenToUse')}>
        <p>{prose(active.whenToUse).primary}</p>
      </Section>

      <Section title={t('section.steps')}>
        <ol className="ts-steps">
          {active.steps.map((step) => (
            <li key={step.title.en}>
              <h4 className="ts-steps__title">{prose(step.title).primary}</h4>
              <p>{prose(step.body).primary}</p>
            </li>
          ))}
        </ol>
      </Section>

      {active.fields?.length ? (
        <Section title={t('section.fields')}>
          <dl className="ts-fields">
            {active.fields.map((field) => (
              <div className="ts-fields__row" key={field.name.en}>
                <dt>{prose(field.name).primary}</dt>
                <dd>
                  <p>{prose(field.meaning).primary}</p>
                  {field.example ? (
                    <p className="ts-fields__example">{prose(field.example).primary}</p>
                  ) : null}
                </dd>
              </div>
            ))}
          </dl>
        </Section>
      ) : null}

      <Section title={t('section.interpret')}>
        <p>{prose(active.interpretResult).primary}</p>
      </Section>

      <Section title={t('section.mistakes')}>
        <ul className="ts-mistakes">
          {active.mistakes.map((mistake) => (
            <li key={mistake.mistake.en}>
              <p className="ts-mistakes__mistake">{prose(mistake.mistake).primary}</p>
              <p className="ts-mistakes__fix">{prose(mistake.fix).primary}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section title={t('section.storage')}>
        <p>{prose(active.storage).primary}</p>
      </Section>

      {/* Always rendered. A reader who reaches the end of a guide must read what
          it cannot promise, not be spared it. */}
      <Section title={t('section.notGuarantee')}>
        <p className="ts-not-guarantee">{prose(active.notGuarantee).primary}</p>
      </Section>

      <div className="ts-detail__actions">
        {onDismiss ? (
          <button
            type="button"
            className="ts-btn"
            onClick={() => (dismissed ? reopen(active.id) : dismiss(active.id))}
          >
            {dismissed ? t('button.showAgain') : t('button.dismiss')}
          </button>
        ) : null}
      </div>

      {/* One storage line, from the shared provider: a refused read and a
          refused write are the same failure to the reader. */}
      {problem ? (
        <p className="ts-note ts-note--warning" role="status">
          {t('panel.storageFailed')} {t('panel.storageFailedBody')}
        </p>
      ) : (
        <p className="ts-note">{t('panel.localOnly')}</p>
      )}
    </article>
  )
}

/** A titled section of a tutorial. */
function Section({ title, children }) {
  return (
    <section className="ts-section">
      <h3 className="ts-section__title">{title}</h3>
      {children}
    </section>
  )
}
