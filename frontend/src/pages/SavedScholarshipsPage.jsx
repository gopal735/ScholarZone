import { Link } from 'react-router-dom'
import ScholarshipList from '../components/ScholarshipList'
import { useScholarshipDirectory } from '../hooks/useScholarshipDirectory'
import { useSavedScholarships } from '../hooks/useSavedScholarships'
import './SavedScholarshipsPage.css'

export default function SavedScholarshipsPage() {
  const { savedIds } = useSavedScholarships()
  const { scholarships, isLoading } = useScholarshipDirectory()
  const savedScholarships = savedIds
    .map((savedId) => scholarships.find((scholarship) => String(scholarship.id) === savedId))
    .filter(Boolean)

  return (
    <section className="saved-scholarships-page">
      <div className="saved-scholarships-page__heading">
        <div>
          <p className="saved-scholarships-page__eyebrow">Your shortlist</p>
          <h1>Saved scholarships</h1>
          <p>Keep opportunities you want to revisit in one place on this device.</p>
        </div>
        <span className="saved-scholarships-page__count">{savedScholarships.length} saved</span>
      </div>

      {isLoading ? (
        <div className="saved-scholarships-page__empty" aria-busy="true">
          <h2>Loading saved scholarships…</h2>
        </div>
      ) : savedScholarships.length === 0 ? (
        <div className="saved-scholarships-page__empty">
          <span className="saved-scholarships-page__empty-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M6 4.5A1.5 1.5 0 0 1 7.5 3h9A1.5 1.5 0 0 1 18 4.5v16l-6-3.5L6 20.5v-16Z" />
            </svg>
          </span>
          <h2>Build a shortlist you can return to.</h2>
          <p>Use Save on any scholarship to keep it available here.</p>
          <Link to="/scholarships" className="saved-scholarships-page__action">
            Browse scholarships <span aria-hidden="true">&rarr;</span>
          </Link>
        </div>
      ) : (
        <ScholarshipList items={savedScholarships} />
      )}
    </section>
  )
}
