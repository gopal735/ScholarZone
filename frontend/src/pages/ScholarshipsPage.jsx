import { useSearchParams } from 'react-router-dom'
import ScholarshipList from '../components/ScholarshipList'
import './ScholarshipsPage.css'

export default function ScholarshipsPage() {
  const [searchParams] = useSearchParams()
  const countryParam = searchParams.get('country') || undefined

  const headerTitle = countryParam || 'All Scholarships'
  const headerDescription = countryParam
    ? `Explore verified scholarship opportunities in ${countryParam}.`
    : 'Compare key funding details, degree levels, countries and deadlines in one focused directory.'

  return (
    <div className="scholarships-page">
      <div className="scholarships-page__content">
        <div className="page-heading">
          <div>
            <p className="page-eyebrow">Scholarship discovery</p>
            <h1>{headerTitle}</h1>
            <p className="page-description">{headerDescription}</p>
          </div>

          <div className="page-heading__trust">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="m9 12 2 2 4-4m5-4v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-3 8 3Z" />
            </svg>
            <p>
              <strong>Trust the details, then verify.</strong>
              <span>Always check the official provider before you apply.</span>
            </p>
          </div>
        </div>
        <ScholarshipList initialCountry={countryParam} />
      </div>
    </div>
  )
}
