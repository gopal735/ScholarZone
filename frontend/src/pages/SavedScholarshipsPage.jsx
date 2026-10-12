import { Link } from 'react-router-dom'
import ScholarshipList from '../components/ScholarshipList'
import { useScholarshipDirectory } from '../hooks/useScholarshipDirectory'
import { useSavedScholarships } from '../hooks/useSavedScholarships'
import { SyncNotice } from '../components/SyncNotice'
import './SavedScholarshipsPage.css'

export default function SavedScholarshipsPage() {
  const { savedIds, syncState } = useSavedScholarships()
  // The whole catalogue, not the first 100 of it. This page resolves the ids a
  // student chose with `find`, so it has to be able to see all 618 records;
  // against a 100-record window a shortlist of anything outside it rendered as
  // empty, which reads as "you have saved nothing" rather than "this device is
  // looking in the wrong place".
  const { scholarships, isLoading } = useScholarshipDirectory()
  const savedScholarships = savedIds
    .map((savedId) => scholarships.find((scholarship) => String(scholarship.id) === savedId))
    .filter(Boolean)

  // Reported rather than dropped. The cause is almost always a plan restored
  // from an export whose snapshot was newer than this device's.
  const unresolvedCount = savedIds.length - savedScholarships.length

  return (
    <section className="saved-scholarships-page">
      <div className="saved-scholarships-page__heading">
        <div>
          <p className="saved-scholarships-page__eyebrow">Your shortlist</p>
          <h1>Saved scholarships</h1>
          <p>
            {/* The previous copy said "on this device", which stopped being true
                when sign-in reconciliation was added: a signed-in student's
                shortlist is the server's list. */}
            Shortlisted opportunities in one place.
          </p>
        </div>
        <span className="saved-scholarships-page__count">{savedScholarships.length} saved</span>
      </div>

      {syncState !== 'idle' && <SyncNotice state={syncState} />}

      {isLoading ? (
        <div className="saved-scholarships-page__empty" aria-busy="true">
          <h2>Loading saved scholarships&hellip;</h2>
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
        <>
          {unresolvedCount > 0 && (
            <p className="saved-scholarships-page__unresolved" role="status">
              {unresolvedCount === 1
                ? 'One saved scholarship is not in this device\u2019s catalogue.'
                : `${unresolvedCount} saved scholarships are not in this device\u2019s catalogue.`}
              {' '}
              They were saved on a device whose catalogue had newer records.
            </p>
          )}
          <ScholarshipList items={savedScholarships} />
        </>
      )}

      {/* The planning surface is where the local checklist, notes and deadline
          planner live, so it is linked from here rather than being rebuilt. */}
      {savedScholarships.length > 0 && (
        <p className="saved-scholarships-page__plan-link">
          <Link to="/plan">
            Build an application checklist and add notes <span aria-hidden="true">&rarr;</span>
          </Link>
        </p>
      )}
    </section>
  )
}
