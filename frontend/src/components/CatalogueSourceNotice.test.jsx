import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import CatalogueSourceNotice from './CatalogueSourceNotice.jsx'

const SNAPSHOT_META = {
  generated_at: '2026-10-10T12:41:37.970162Z',
  source_database: 'scholarzone.db',
  source_record_count: 695,
  public_record_count: 634,
  excluded: { closed: 12, archived: 52, quarantined: 51 },
  excluded_union: 61,
  schema_version: '1.0',
  visibility_predicate: 'status != closed AND is_archived = false AND verification_status != quarantined',
  sort_orders: { 'recently-added': [1, 2, 3] },
}

describe('CatalogueSourceNotice', () => {
  afterEach(() => {
    cleanup()
  })

  it('names the deadline rule when the snapshot excluded any', () => {
    // The header's deadline_passed bucket is derived, not stored: records whose
    // deadline had already gone when the snapshot was built. Saying so keeps the
    // membership rule honest, and an absence of the phrase when the count is
    // zero is not a claim that no deadline has ever passed.
    render(
      <CatalogueSourceNotice
        source="snapshot"
        meta={{ ...SNAPSHOT_META, deadline_passed: 12 }}
      />,
    )
    expect(screen.getByText(/deadline had not passed/i)).toBeInTheDocument()
  })

  it('does not claim a deadline rule applied when none did', () => {
    render(
      <CatalogueSourceNotice
        source="snapshot"
        meta={{ ...SNAPSHOT_META, deadline_passed: 0 }}
      />,
    )
    expect(screen.queryByText(/deadline had not passed/i)).not.toBeInTheDocument()
  })

  it('does not hide a record merely for being unverified or imageless', () => {
    render(<CatalogueSourceNotice source="snapshot" meta={SNAPSHOT_META} />)
    expect(screen.getByText(/does not hide a scholarship for being unverified/i)).toBeInTheDocument()
  })

  it('renders nothing when the data came from the live API', () => {
    const { container } = render(
      <CatalogueSourceNotice source="api" meta={SNAPSHOT_META} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when there is no metadata to disclose', () => {
    // Without provenance there is nothing honest to say, and inventing a date
    // or a count would be the failure this notice exists to avoid.
    const { container } = render(<CatalogueSourceNotice source="snapshot" meta={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('states that the catalogue is a static snapshot', () => {
    render(<CatalogueSourceNotice source="snapshot" meta={SNAPSHOT_META} />)
    expect(screen.getByText(/static snapshot/i)).toBeInTheDocument()
  })

  it('states that production parity has not been verified', () => {
    render(<CatalogueSourceNotice source="snapshot" meta={SNAPSHOT_META} />)
    expect(
      screen.getByText(/not been reconciled against the production database/i),
    ).toBeInTheDocument()
  })

  it('directs the reader to each scholarship official source before applying', () => {
    render(<CatalogueSourceNotice source="snapshot" meta={SNAPSHOT_META} />)
    expect(
      screen.getByText(/official source link to confirm the deadline and requirements/i),
    ).toBeInTheDocument()
  })

  it('says opportunities and deadlines may have changed', () => {
    render(<CatalogueSourceNotice source="snapshot" meta={SNAPSHOT_META} />)
    expect(screen.getByText(/deadlines and funding can have changed/i)).toBeInTheDocument()
  })

  it('shows the snapshot generation date', () => {
    render(<CatalogueSourceNotice source="snapshot" meta={SNAPSHOT_META} />)
    // 2026-10-10, rendered in the reader's locale rather than as raw ISO.
    expect(screen.getByText(/October 10, 2026|10 October 2026|2026/)).toBeInTheDocument()
  })

  it('does not claim every record is currently open or verified', () => {
    render(<CatalogueSourceNotice source="snapshot" meta={SNAPSHOT_META} />)
    const body = document.body.textContent
    expect(body).not.toMatch(/all records are (currently )?(open|verified)/i)
    expect(body).not.toMatch(/production.current/i)
  })

  it('is reachable by an accessible name', () => {
    render(<CatalogueSourceNotice source="snapshot" meta={SNAPSHOT_META} />)
    expect(
      screen.getByRole('heading', { name: /about this catalogue/i }),
    ).toBeInTheDocument()
  })

  it('is marked up as a complementary landmark so it can be skipped', () => {
    render(<CatalogueSourceNotice source="snapshot" meta={SNAPSHOT_META} />)
    expect(screen.getByRole('complementary')).toBeInTheDocument()
  })

  it('carries a test id for behavioural assertions', () => {
    render(<CatalogueSourceNotice source="snapshot" meta={SNAPSHOT_META} />)
    expect(screen.getByTestId('catalogue-source-notice')).toBeInTheDocument()
  })

  it('omits the date rather than rendering an unreadable one', () => {
    render(
      <CatalogueSourceNotice
        source="snapshot"
        meta={{ ...SNAPSHOT_META, generated_at: 'not a real date' }}
      />,
    )
    expect(screen.queryByText(/generated on/i)).not.toBeInTheDocument()
    expect(screen.getByText(/static snapshot/i)).toBeInTheDocument()
  })

  it('omits the counts when the header does not carry them', () => {
    render(
      <CatalogueSourceNotice
        source="snapshot"
        meta={{ generated_at: SNAPSHOT_META.generated_at }}
      />,
    )
    expect(screen.queryByText(/of .* records are included/i)).not.toBeInTheDocument()
  })

  it('never renders the sort orderings', () => {
    // The orderings are implementation detail - nine arrays of ids. They have
    // no place in a sentence a student reads.
    render(<CatalogueSourceNotice source="snapshot" meta={SNAPSHOT_META} />)
    expect(document.body.textContent).not.toContain('recently-added')
    expect(document.body.textContent).not.toContain('1,2,3')
  })

  it('does not present the snapshot as a failure of the database', () => {
    render(<CatalogueSourceNotice source="snapshot" meta={SNAPSHOT_META} />)
    const body = document.body.textContent
    expect(body).not.toMatch(/unavailable|error|failed|broken|down/i)
  })

  it('accepts an extra class name for placement without changing the message', () => {
    render(
      <CatalogueSourceNotice source="snapshot" meta={SNAPSHOT_META} className="sz-detail__notice-slot" />,
    )
    const notice = screen.getByTestId('catalogue-source-notice')
    expect(notice.className).toContain('catalogue-source-notice')
    expect(notice.className).toContain('sz-detail__notice-slot')
  })
})
