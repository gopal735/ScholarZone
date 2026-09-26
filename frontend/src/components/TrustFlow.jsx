import { useEffect, useRef, useState } from 'react'
import './TrustFlow.css'

/* The five stages of the verification model, stated once so the visual
   sequence and the copy cannot drift apart. No figures are invented
   here — this describes the process, not a statistic. */
const STAGES = [
  {
    id: 'discover',
    label: 'Discover',
    note: 'Opportunities are gathered from official university portals and government databases.',
  },
  {
    id: 'source',
    label: 'Source',
    note: 'Every listing is tied to the awarding body’s own page, not an aggregator summary.',
  },
  {
    id: 'verify',
    label: 'Verify',
    note: 'Deadlines, funding and eligibility are cross-referenced against the primary source.',
  },
  {
    id: 'update',
    label: 'Update',
    note: 'Listings are re-verified on a rolling basis so details stay current as they change.',
  },
  {
    id: 'trust',
    label: 'Trust',
    note: 'A verification status is published on every listing so the confidence level is explicit.',
  },
]

/* Activates once, when the sequence scrolls into view. The line then
   fills on its own and never re-runs — a looping connector would read
   as a demo rather than as a process. */
export default function TrustFlow() {
  const ref = useRef(null)
  const [isActive, setIsActive] = useState(false)

  useEffect(() => {
    const element = ref.current
    if (!element) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsActive(true)
          observer.unobserve(element)
        }
      },
      { threshold: 0.25, rootMargin: '0px 0px -60px 0px' }
    )

    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return (
    <ol ref={ref} className={`sz-flow${isActive ? ' is-active' : ''}`}>
      {STAGES.map((stage, index) => (
        <li className="sz-flow__stage" key={stage.id}>
          <span className="sz-flow__node" aria-hidden="true">
            {String(index + 1).padStart(2, '0')}
          </span>
          <span className="sz-flow__body">
            <span className="sz-flow__label">{stage.label}</span>
            <span className="sz-flow__note">{stage.note}</span>
          </span>
        </li>
      ))}
    </ol>
  )
}
