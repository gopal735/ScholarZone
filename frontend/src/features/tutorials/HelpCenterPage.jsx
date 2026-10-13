import { Suspense, lazy, useCallback, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { HowToUse } from './components/HowToUse.jsx'
const TutorialDetail = lazy(() =>
  import('./components/TutorialDetail.jsx').then((module) => ({ default: module.TutorialDetail })),
)
import { useHelpCenter } from './hooks/useHelpCenter.js'
import { useTutorialsI18n } from './i18n/useTutorialsI18n.js'
import {
  CATEGORY_ORDER,
  KNOWN_GOALS,
  adminTutorials,
} from './lib/registry.js'

/**
 * The Help Center at `/help`.
 *
 * A directory first and a reader second: search and categories at the top, the
 * results beside them, and the open tutorial after. Selecting a tutorial puts
 * its id in the URL, so a link to a guide is a link a reader can send someone.
 *
 * ## How admin visibility works, and why it is not derived from a session
 *
 * The auth context in this app carries `{ status, user, login, register,
 * logout }` — it has no role, and admin access is enforced by an `X-Admin-Secret`
 * header the admin pages supply themselves, resolved server-side. Deriving
 * "is this reader staff" from a session field that does not exist would be a
 * second, weaker authority than the server, and it would be wrong.
 *
 * So the admin group is opt-in via a plainly labelled control, and the admin
 * tutorial states what actually gates the tools. The control decides what the
 * *directory* shows; it decides nothing about whether the tools work. That is
 * the same distinction the routes make, kept in one place.
 *
 * ## What this page does not claim
 *
 * Every tutorial ends in what the feature cannot promise, and the page carries
 * the local-storage note. Nothing here predicts an outcome.
 */
export default function HelpCenterPage() {
  const { t, both, prose, mode, problem: languageProblem } = useTutorialsI18n()
  const [params, setParams] = useSearchParams()

  const includeAdmin = params.get('audience') === 'admin'
  const setIncludeAdmin = useCallback(
    (value) => {
      const next = new URLSearchParams(params)
      if (value) {
        next.set('audience', 'admin')
      } else {
        next.delete('audience')
      }
      setParams(next, { replace: true })
    },
    [params, setParams],
  )

  const {
    query,
    setQuery,
    clearSearch,
    category,
    setCategory,
    categoryCounts,
    goalIndex,
    results,
    selected,
    open,
    close,
    isDismissed,
    dismiss,
    reopen,
    problem: dismissalProblem,
    storageAvailable,
    excludedRoutes,
  } = useHelpCenter({ includeAdmin })

  const [adminNoticeShown, setAdminNoticeShown] = useState(false)

  const adminGroup = useMemo(() => (includeAdmin ? adminTutorials() : []), [includeAdmin])

  // One storage problem, from either write path. A refused language write and a
  // refused dismissal are the same failure to the reader — the browser would not
  // keep their preference — so they surface in one sentence rather than in two
  // that each know half the story.
  const storageProblem = dismissalProblem || languageProblem

  return (
    <div className="ts-page">
      <header className="ts-page__head">
        <p className="ts-page__eyebrow">ScholarZone</p>
        <h1 className="ts-page__title" lang={mode === 'en' ? 'en' : 'bn'}>
          {both('app.title').primary}
          {both('app.title').secondary ? (
            <span className="ts-page__title-en">{both('app.title').secondary}</span>
          ) : null}
        </h1>
        <p className="ts-page__tagline">{t('app.tagline')}</p>

        <LanguageSwitcher />

        <p className="ts-page__intro">{t('help.introBody')}</p>

        {/*
          One storage line, not two. The earlier shape rendered both
          "stored in this browser only" and, separately, a warning — so a
          reader with storage blocked was told both that the guide was local and
          that it could not be stored, in sentences one after another.
        */}
        {storageAvailable && !storageProblem ? (
          <p className="ts-page__note">
            {t('panel.localOnly')} {t('panel.noNetwork')}
          </p>
        ) : (
          <p className="ts-page__note ts-page__note--warning" role="status">
            {t('panel.storageFailed')} {t('panel.storageFailedBody')}
          </p>
        )}
      </header>

      <div className="ts-layout">
        <div className="ts-browser">
          <div className="ts-search">
            <label className="ts-search__label" htmlFor="ts-search-input">
              {t('search.label')}
            </label>
            <div className="ts-search__row">
              <input
                id="ts-search-input"
                type="search"
                className="ts-input"
                value={query}
                placeholder={t('search.placeholder')}
                onChange={(event) => setQuery(event.target.value)}
              />
              {query ? (
                <button type="button" className="ts-btn ts-btn--quiet" onClick={clearSearch}>
                  {t('button.clearSearch')}
                </button>
              ) : null}
            </div>
            <p className="ts-search__count" aria-live="polite">
              {`${results.length} ${t('search.resultsCount')}`}
            </p>
          </div>

          <nav className="ts-categories" aria-label={t('category.label')}>
            <h2 className="ts-categories__title">{t('category.label')}</h2>
            <ul className="ts-categories__list">
              {['all', ...CATEGORY_ORDER].map((id) => {
                const count = categoryCounts[id] || 0
                const active = category === id
                return (
                  <li key={id}>
                    <button
                      type="button"
                      className={active ? 'ts-chip is-active' : 'ts-chip'}
                      aria-pressed={active}
                      onClick={() => setCategory(id)}
                    >
                      {t(`category.${id}`)}
                      <span className="ts-chip__count">{count}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </nav>

          {/* The goal index: a reader who knows what they want rather than what
              it is called starts here; a reader who knows the name uses search. */}
          <nav className="ts-goals" aria-label={t('goal.label')}>
            <h2 className="ts-goals__title">{t('goal.label')}</h2>
            <ul className="ts-goals__list">
              {KNOWN_GOALS.filter((goal) => goalIndex[goal]).map((goal) => (
                <li className="ts-goal" key={goal}>
                  <span>{t(`goal.${goal}`)}</span>
                  <span className="ts-goal__count">{goalIndex[goal]}</span>
                </li>
              ))}
            </ul>
          </nav>

          {/*
            The admin group. Opt-in, plainly labelled, and it grants nothing:
            the tools themselves still require the admin secret and still resolve
            access server-side. Showing the guide is not showing the tool.
          */}
          <section className="ts-admin">
            <h2 className="ts-admin__title">{t('route.admin')}</h2>
            <button
              type="button"
              className="ts-btn ts-btn--quiet"
              aria-pressed={includeAdmin}
              onClick={() => {
                setIncludeAdmin(!includeAdmin)
                setAdminNoticeShown(!includeAdmin)
              }}
            >
              {includeAdmin ? t('button.hideAll') : t('button.showAll')}
            </button>
            {adminNoticeShown && includeAdmin ? (
              <p className="ts-note ts-note--warning" role="status">
                {t('route.admin')}: {t('help.coverageTitle')}.{' '}
                {prose(adminGroup[0]?.notGuarantee).primary}
              </p>
            ) : null}
            {includeAdmin ? (
              <ul className="ts-admin__list">
                {adminGroup.map((tutorial) => (
                  <li key={tutorial.id}>
                    <button type="button" className="ts-link" onClick={() => open(tutorial.id)}>
                      {prose(tutorial.navLabel).primary}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>

          {/* The honest list of what this directory deliberately does not cover,
              so a reader is not left to find it by visiting a dead route. */}
          {excludedRoutes.length ? (
            <aside className="ts-excluded">
              <h2 className="ts-excluded__title">{t('help.coverageTitle')}</h2>
              <p className="ts-excluded__body">{t('tutorial.empty')}</p>
              <ul className="ts-excluded__list">
                {excludedRoutes.map((route) => (
                  <li key={route}>
                    <code>{route}</code>
                  </li>
                ))}
              </ul>
            </aside>
          ) : null}
        </div>

        <main className="ts-results">
          {results.length === 0 ? (
            <div className="ts-noresults" role="status">
              <h2>{t('search.noResults')}</h2>
              <p>{t('search.noResultsHint')}</p>
            </div>
          ) : (
            <ul className="ts-cards">
              {results.map((tutorial) => {
                const dismissed = isDismissed(tutorial.id)
                const isActive = selected?.id === tutorial.id
                return (
                  <li key={tutorial.id}>
                    <article className={isActive ? 'ts-card is-active' : 'ts-card'}>
                      <h3 className="ts-card__title">
                        <button
                          type="button"
                          className="ts-card__button"
                          aria-expanded={isActive}
                          onClick={() => (isActive ? close() : open(tutorial.id))}
                        >
                          {prose(tutorial.navLabel).primary}
                        </button>
                      </h3>
                      <p className="ts-card__summary">{prose(tutorial.purpose).primary}</p>
                      <p className="ts-card__routes">
                        {(tutorial.routes || [tutorial.route]).map((route) => (
                          <code key={route}>{route}</code>
                        ))}
                      </p>
                      <div className="ts-card__actions">
                        <button
                          type="button"
                          className="ts-link"
                          onClick={() => open(tutorial.id)}
                        >
                          {t('button.readTutorial')}
                        </button>
                        <button
                          type="button"
                          className="ts-btn ts-btn--quiet ts-btn--small"
                          onClick={() => (dismissed ? reopen(tutorial.id) : dismiss(tutorial.id))}
                        >
                          {dismissed ? t('button.showAgain') : t('button.dismiss')}
                        </button>
                      </div>
                    </article>
                  </li>
                )
              })}
            </ul>
          )}

          {/* A deep link to a known id opens it in place. An unknown id falls
              through to the not-found panel rather than rendering nothing. */}
          {params.get('tutorial') && !selected ? (
            <div className="ts-noresults" role="status">
              <h2>{t('search.noResults')}</h2>
              <p>{t('tutorial.empty')}</p>
            </div>
          ) : null}

            {selected ? (
              <section className="ts-reader" aria-label={prose(selected.navLabel).primary}>
                <Suspense
                  fallback={
                    <p className="ts-empty" role="status">
                      {t('tutorial.loading')}
                    </p>
                  }
                >
                  <TutorialDetail
                    tutorial={selected}
                    onDismiss={() => dismiss(selected.id)}
                    onClose={close}
                  />
                </Suspense>
              </section>
            ) : null}
        </main>
      </div>
    </div>
  )
}

/** The three display modes, as a radio group. */
function LanguageSwitcher() {
  const { t, mode, setLanguage } = useTutorialsI18n()
  return (
    <fieldset className="ts-lang">
      <legend className="ts-lang__label">{t('language.label')}</legend>
      {['en', 'bn', 'both'].map((value) => (
        <label className="ts-lang__option" key={value}>
          <input
            type="radio"
            name="ts-language"
            value={value}
            checked={mode === value}
            onChange={() => setLanguage(value)}
          />
          <span>{t(`language.${value}`)}</span>
        </label>
      ))}
    </fieldset>
  )
}

/**
 * A single tutorial at `/:tutorialId`, for a guide linked to directly.
 *
 * Exported for the route table so a shared link does not have to carry query
 * state. An unknown id renders the not-found panel, never a blank page.
 */
export function TutorialPage({ tutorialId }) {
  const { t, prose } = useTutorialsI18n()
  // An id is enough; TutorialDetail does the prose lookup so the guide text is
  // not in this file's module graph.
  const found = tutorialId || null

  return (
    <div className="ts-page">
      <header className="ts-page__head">
        <p className="ts-page__eyebrow">ScholarZone</p>
        <h1 className="ts-page__title">{prose(found?.navLabel ?? 'app.title').primary}</h1>
        <Link className="ts-link" to="/help">
          {t('button.backToHelp')}
        </Link>
      </header>
        {found ? (
          <Suspense
            fallback={
              <p className="ts-empty" role="status">
                {t('tutorial.loading')}
              </p>
            }
          >
            <TutorialDetail tutorial={found} />
          </Suspense>
        ) : (
        <div className="ts-noresults" role="status">
          <h2>{t('search.noResults')}</h2>
          <p>{t('tutorial.empty')}</p>
        </div>
      )}
    </div>
  )
}

export { HowToUse }
