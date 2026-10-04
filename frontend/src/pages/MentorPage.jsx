/**
 * GROUNDed AI Mentor.
 *
 * Access is resolved from the server, not from the browser. The route is
 * registered plainly rather than wrapped in `ProtectedRoute`, for the reason the
 * dashboard and the workspace state in `App.jsx`: a client-side guard can only
 * trust a value the browser supplied. So the page asks, and a 401 is what puts it
 * into its signed-out state.
 *
 * `useAuth` is still read, but only to *offer* a sign-in link sooner. It never
 * decides what is shown, and the server's answer still overrules it - which is
 * why a revoked session on an already-open tab ends in the signed-out state here
 * too.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import MentorAnswer from '../components/mentor/MentorAnswer'
import MentorComposer from '../components/mentor/MentorComposer'
import { useAuth } from '../hooks/useAuth'
import { useReducedMotion } from '../hooks/useReducedMotion'
import {
  MentorRateLimitedError,
  MentorUnauthenticatedError,
  askMentor,
  fetchMentorOverview,
} from '../services/mentorService'
import { sourceLabel } from '../services/mentorPresentation'

import './MentorPage.css'

const PAGE_STATUS = Object.freeze({
  LOADING: 'loading',
  READY: 'ready',
  ERROR: 'error',
  UNAUTHENTICATED: 'unauthenticated',
})

const DEFAULT_MAX_LENGTH = 2000

function Skeleton() {
  return (
    <div className="mentor-page__skeleton" data-testid="mentor-loading">
      <span />
      <span />
      <span />
    </div>
  )
}

export default function MentorPage() {
  const { status: authStatus } = useAuth()
  const reducedMotion = useReducedMotion()

  const [status, setStatus] = useState(PAGE_STATUS.LOADING)
  const [overview, setOverview] = useState(null)
  const [answer, setAnswer] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const answerRef = useRef(null)

  // Load only. The mount path sets state inside promise callbacks so a component
  // that unmounts mid-flight never writes to a dead tree.
  useEffect(() => {
    let cancelled = false
    fetchMentorOverview().then(
      (data) => {
        if (cancelled) return
        setOverview(data)
        setStatus(PAGE_STATUS.READY)
      },
      () => {
        if (cancelled) return
        // The overview is only a list of suggestions, so failing to load it must
        // not block the page: the composer and its own limits still work.
        setStatus(PAGE_STATUS.READY)
      },
    )
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const previous = document.title
    document.title = 'Mentor · ScholarZone'
    const robots = document.createElement('meta')
    robots.name = 'robots'
    robots.content = 'noindex, nofollow'
    robots.setAttribute('data-sz-seo', 'true')
    document.head.appendChild(robots)
    return () => {
      document.title = previous
      document.head.removeChild(robots)
    }
  }, [])

  // A new answer moves focus to itself so a keyboard or screen-reader user is
  // not left at the composer, still pointing at the question they just asked.
  useEffect(() => {
    if (answer && answerRef.current) answerRef.current.focus()
  }, [answer])

  const submit = useCallback(async () => {
    const message = question.trim()
    if (!message || asking) return
    setAsking(true)
    setNotice(null)
    setError(null)
    try {
      const result = await askMentor(message)
      setAnswer(result)
    } catch (caught) {
      // A failure clears the previous answer. Leaving it on screen would answer a
      // question the student did not ask, about a state they have moved on from.
      setAnswer(null)
      if (caught instanceof MentorUnauthenticatedError) {
        setStatus(PAGE_STATUS.UNAUTHENTICATED)
      } else if (caught instanceof MentorRateLimitedError) {
        setNotice({
          type: 'error',
          message: `${caught.message}${
            caught.retryAfterSeconds ? ` Try again in about ${caught.retryAfterSeconds} seconds.` : ''
          }`,
        })
      } else {
        setError(caught)
      }
    } finally {
      setAsking(false)
    }
  }, [asking, question])

  const askSuggested = useCallback(
    (suggestion) => {
      setQuestion(suggestion)
      // Ask straight away: a suggestion the reader has to re-submit by hand is a
      // suggestion that mostly will not be used.
      const message = suggestion.trim()
      if (!message) return
      setAsking(true)
      setNotice(null)
      setError(null)
      askMentor(message).then(
        (result) => {
          setAnswer(result)
          setAsking(false)
        },
        (caught) => {
          setAnswer(null)
          setAsking(false)
          if (caught instanceof MentorUnauthenticatedError) {
            setStatus(PAGE_STATUS.UNAUTHENTICATED)
            return
          }
          setError(caught)
        },
      )
    },
    [],
  )

  if (status === PAGE_STATUS.LOADING) {
    return (
      <div className="mentor-page" aria-busy="true">
        <p className="sz-sr-only" role="status">
          Loading your mentor
        </p>
        <div className="mentor-page__inner">
          <Skeleton />
        </div>
      </div>
    )
  }

  if (status === PAGE_STATUS.UNAUTHENTICATED || authStatus === 'unauthenticated') {
    return (
      <div className="mentor-page">
        <div className="mentor-page__inner">
          <div className="empty-state" data-testid="mentor-signed-out">
            <h1>Mentor</h1>
            <p>
              Sign in and ScholarZone can answer from your own matches, deadlines
              and applications.
            </p>
            <Link to="/login" className="sz-btn sz-btn--primary">
              Sign in
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const suggestions = overview?.redirects ?? []

  return (
    <div className={`mentor-page${reducedMotion ? ' is-reduced-motion' : ''}`}>
      <div className="mentor-page__inner">
        <p className="sz-sr-only" role="status" aria-live="polite">
          {asking ? 'ScholarZone is preparing a grounded answer' : notice ? notice.message : ''}
        </p>

        <header className="mentor-page__masthead">
          <p className="page-eyebrow">Your grounded advisor</p>
          <h1 className="mentor-page__title">Mentor</h1>
          <p className="mentor-page__lede">
            Every answer is assembled from ScholarZone&rsquo;s own records: your
            profile, your matches, your deadlines and your applications. Anything
            it has not measured is named as unknown rather than guessed.
          </p>
        </header>

        {notice ? (
          <p className={`mentor-page__notice mentor-page__notice--${notice.type}`} role="alert">
            {notice.message}
          </p>
        ) : null}

        {error ? (
          <div className="mentor-page__error" role="alert" data-testid="mentor-error">
            <h2 className="mentor-page__error-title">That question could not be answered</h2>
            <p>{error.message}</p>
            <button
              type="button"
              className="sz-btn sz-btn--primary"
              onClick={() => {
                setError(null)
                submit()
              }}
            >
              Try again
            </button>
          </div>
        ) : null}

        {answer ? (
          <div ref={answerRef} tabIndex={-1} className="mentor-page__answer">
            <MentorAnswer answer={answer} />
          </div>
        ) : null}

        {asking ? (
          <p className="mentor-page__thinking" data-testid="mentor-thinking">
            Reading your records&hellip;
          </p>
        ) : null}

        {suggestions.length > 0 && !answer ? (
          <section
            className="mentor-page__suggestions"
            aria-labelledby="mentor-suggestions-heading"
          >
            <h2 className="mentor-page__suggestions-heading" id="mentor-suggestions-heading">
              Ask about
            </h2>
            <ul className="mentor-page__suggestion-list">
              {suggestions.map((suggestion) => (
                <li key={suggestion}>
                  <button
                    type="button"
                    className="sz-btn sz-btn--secondary mentor-page__suggestion"
                    disabled={asking}
                    onClick={() => askSuggested(suggestion)}
                  >
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {answer && !answer.known.length && !answer.general_guidance_only ? (
          <p className="mentor-page__empty" data-testid="mentor-no-grounded-data">
            ScholarZone has nothing measured for this question yet, so the answer
            above says so rather than filling the gap.
          </p>
        ) : null}

        <MentorComposer
          value={question}
          onChange={setQuestion}
          onSubmit={submit}
          busy={asking}
          maxLength={overview?.max_message_length ?? DEFAULT_MAX_LENGTH}
        />

        <footer className="mentor-page__footer">
          <p className="mentor-page__source">
            {answer
              ? `Source: ${sourceLabel(answer)}.`
              : 'Answers are grounded in ScholarZone data and clearly labelled general guidance.'}
          </p>
          <p className="mentor-page__privacy">
            Your questions are answered and discarded. Nothing here is stored as a
            conversation, and your private application notes are never read.
          </p>
        </footer>
      </div>
    </div>
  )
}