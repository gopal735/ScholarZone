import { useState } from 'react'

/* One expandable level inside a card. Levels are
   progressively disclosed: the front (Level 1) carries
   decision data only, and each deeper level is collapsed
   until the reader asks for it. */
export default function CardExpandSection({ level, title, summary, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  const panelId = `card-level-${level}`
  const buttonId = `card-level-${level}-button`

  return (
    <section className={`card-level${open ? ' card-level--open' : ''}`}>
      <button
        id={buttonId}
        type="button"
        className="card-level__trigger"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="card-level__marker" aria-hidden="true">L{level}</span>
        <span className="card-level__title">{title}</span>
        {summary && !open ? <span className="card-level__summary">{summary}</span> : null}
        <svg
          className="card-level__chevron"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      <div
        id={panelId}
        role="region"
        aria-labelledby={buttonId}
        className="card-level__panel"
        hidden={!open}
      >
        <div className="card-level__body">{children}</div>
      </div>
    </section>
  )
}
