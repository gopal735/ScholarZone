import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { scholarships } from '../data/scholarships'
import { fetchScholarships } from '../services/scholarshipService'
import ScholarshipCard from './ScholarshipCard'
import './ScholarshipShowcase.css'

function getFallbackItems({ funding, sort }) {
  const filteredItems = funding && funding !== 'All'
    ? scholarships.filter((scholarship) => scholarship.funding === funding)
    : scholarships

  const sortedItems = [...filteredItems]
  if (sort === 'deadline-soon') {
    sortedItems.sort((first, second) => Date.parse(first.deadline) - Date.parse(second.deadline))
  }

  return sortedItems.slice(0, 3)
}

function ShowcaseLoading() {
  return (
    <div className="scholarship-showcase__grid scholarship-showcase__grid--loading" aria-label="Loading scholarship collection" aria-busy="true">
      {[1, 2, 3].map((item) => (
        <div key={item} className="scholarship-card-skeleton" aria-hidden="true">
          <span className="scholarship-card-skeleton__line scholarship-card-skeleton__line--badge" />
          <span className="scholarship-card-skeleton__line scholarship-card-skeleton__line--title" />
          <span className="scholarship-card-skeleton__line" />
          <span className="scholarship-card-skeleton__line" />
          <span className="scholarship-card-skeleton__line scholarship-card-skeleton__line--deadline" />
          <span className="scholarship-card-skeleton__line scholarship-card-skeleton__line--button" />
        </div>
      ))}
    </div>
  )
}

export default function ScholarshipShowcase({ title, description, query }) {
  const [items, setItems] = useState([])
  const [loadState, setLoadState] = useState('loading')
  const requestIdRef = useRef(0)

  useEffect(() => {
    const controller = new AbortController()
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId

    fetchScholarships({ ...query, limit: 3 }, { signal: controller.signal })
      .then((directory) => {
        if (controller.signal.aborted || requestId !== requestIdRef.current) {
          return
        }

        setItems(directory.items)
        setLoadState('success')
      })
      .catch(() => {
        if (controller.signal.aborted || requestId !== requestIdRef.current) {
          return
        }

        setItems(getFallbackItems(query))
        setLoadState('fallback')
      })

    return () => controller.abort()
  }, [query])

  return (
    <section className="scholarship-showcase" aria-labelledby={`showcase-${title.replaceAll(' ', '-').toLowerCase()}`}>
      <div className="scholarship-showcase__heading">
        <div>
          <h2 id={`showcase-${title.replaceAll(' ', '-').toLowerCase()}`}>{title}</h2>
          <p>{description}</p>
        </div>
        <Link to="/scholarships">Explore all <span aria-hidden="true">&rarr;</span></Link>
      </div>

      {loadState === 'loading' ? <ShowcaseLoading /> : (
        <>
          {loadState === 'fallback' && <p className="scholarship-showcase__fallback" role="status">Showing local directory data.</p>}
          {items.length > 0 ? (
            <div className="scholarship-showcase__grid">
              {items.map((scholarship) => (
                <ScholarshipCard key={scholarship.id} scholarship={scholarship} />
              ))}
            </div>
          ) : (
            <p className="scholarship-showcase__empty">No scholarships match this collection yet.</p>
          )}
        </>
      )}
    </section>
  )
}
