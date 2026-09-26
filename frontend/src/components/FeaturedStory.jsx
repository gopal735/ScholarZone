import { useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import ScholarshipCard from './ScholarshipCard'
import './FeaturedStory.css'

/* Centre-stage collection, after the interaction reference: one active
   item in the middle with its neighbours cropped at the edges, and a tab
   bar crossing the lower boundary of the stage.

   The crop is the point. Neighbours bleeding off-canvas tell the reader
   the set continues, which a three-up grid never does. */

function EdgeItem({ scholarship, side }) {
  if (!scholarship) return null

  return (
    <Link
      to={`/scholarships/${scholarship.id}`}
      className={`sz-story__edge sz-story__edge--${side}`}
      tabIndex={-1}
      aria-hidden="true"
    >
      <span className="sz-story__edge-funding">{scholarship.funding}</span>
      <span className="sz-story__edge-title">{scholarship.title}</span>
    </Link>
  )
}

export default function FeaturedStory({ items, label }) {
  const [requestedIndex, setRequestedIndex] = useState(0)
  const listRef = useRef(null)

  const count = items.length

  /* Clamped during render rather than corrected in an effect. When the
     directory shrinks the selection lands on the last real item
     immediately, with no intermediate render and no cascade. */
  const active = count === 0 ? 0 : Math.min(Math.max(requestedIndex, 0), count - 1)

  const current = items[active] ?? null
  const before = useMemo(() => {
    if (count === 0) return null
    return items[(active - 1 + count) % count]
  }, [items, active, count])
  const after = useMemo(() => {
    if (count === 0) return null
    return items[(active + 1) % count]
  }, [items, active, count])

  const step = (delta) => {
    if (count === 0) return
    setRequestedIndex((index) => (index + delta + count) % count)
  }

  const onKeyDown = (event) => {
    if (event.key === 'ArrowRight') { event.preventDefault(); step(1) }
    if (event.key === 'ArrowLeft') { event.preventDefault(); step(-1) }
  }

  if (count === 0) {
    return (
      <div className="sz-story sz-story--empty">
        <p className="sz-story__empty">Featured opportunities appear here as the directory grows.</p>
      </div>
    )
  }

  return (
    <div className="sz-story">
      <div
        className="sz-story__stage"
        ref={listRef}
        role="group"
        aria-roledescription="carousel"
        aria-label={label}
        tabIndex={0}
        onKeyDown={onKeyDown}
      >
        <EdgeItem scholarship={before} side="left" />

        <div className="sz-story__active" key={current?.id ?? 'empty'}>
          <ScholarshipCard scholarship={current} />
          <p className="sz-story__count">
            <strong>{String(active + 1).padStart(2, '0')}</strong>
            <span aria-hidden="true"> / </span>
            <span>{String(count).padStart(2, '0')}</span>
            <em className="visually-hidden">
              , item {active + 1} of {count}
            </em>
          </p>
        </div>

        <EdgeItem scholarship={after} side="right" />
      </div>

      {/* The tab bar crosses the stage's lower edge. Active state is an
          underline and nothing else — a filled pill here would
          reintroduce the weight the composition is trying to lose. */}
      <div className="sz-story__tabs" role="tablist" aria-label="Choose a featured opportunity">
        {items.map((item, index) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`sz-story-tab-${item.id}`}
            aria-selected={index === active}
            aria-controls="sz-story-panel"
            tabIndex={index === active ? 0 : -1}
            className={`sz-story__tab${index === active ? ' is-active' : ''}`}
            onClick={() => setRequestedIndex(index)}
          >
            <span className="sz-story__tab-name">{item.title}</span>
            <span className="sz-story__tab-country">{item.country}</span>
          </button>
        ))}
      </div>

      <p className="sz-story__hint" aria-hidden="true">
        Use the arrow keys, or pick a name below.
      </p>
      <div id="sz-story-panel" className="visually-hidden" aria-live="polite">
        {current ? `${current.title} — ${current.funding}, ${current.country}` : ''}
      </div>
    </div>
  )
}
