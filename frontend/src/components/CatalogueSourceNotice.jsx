import './CatalogueSourceNotice.css'

/**
 * Discloses where the catalogue data came from.
 *
 * The public catalogue is served from a version-controlled JSON snapshot, not
 * from the live database. That is what makes it work on a free tier: the
 * database can be over quota or paused and the catalogue still loads. The cost
 * is that the snapshot can lag the database, so a student deserves to know
 * which they are looking at before they rely on a deadline.
 *
 * The wording is deliberately narrow. It says what is not verified - that the
 * snapshot has not been reconciled against the production database - and it
 * directs the reader to each scholarship's official source for anything that
 * matters. It does not say the data is wrong, and it does not say it is
 * current: neither is supported by evidence, and a claim in either direction
 * would be a guess dressed as a fact.
 */

/**
 * Formats the snapshot's own generated_at for display.
 *
 * Returned as null when it is missing or unparseable rather than as an empty
 * string or "Invalid Date". The notice's whole value is being trustworthy about
 * provenance, and a date that cannot be read is exactly the thing it should
 * decline to show rather than render badly.
 */
function formatSnapshotDate(value) {
  if (typeof value !== 'string' || value.trim() === '') {
    return null
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return null
  }

  return parsed.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

export default function CatalogueSourceNotice({ meta, source, className }) {
  // Only the snapshot path carries provenance worth disclosing. A live API
  // response is the database's own answer, and there is nothing deferred to
  // warn about.
  if (source !== 'snapshot' || !meta) {
    return null
  }

  const generatedAt = formatSnapshotDate(meta.generated_at)
  const runtimeLabel = source === 'snapshot' ? 'static snapshot' : 'live database'

  return (
    <aside
      className={`catalogue-source-notice${className ? ` ${className}` : ''}`}
      aria-labelledby="catalogue-source-notice-title"
      data-testid="catalogue-source-notice"
    >
      <h2 className="catalogue-source-notice__title" id="catalogue-source-notice-title">
        About this catalogue
      </h2>

      <p className="catalogue-source-notice__body">
        You are browsing a <strong>{runtimeLabel}</strong> of the scholarship
        catalogue{generatedAt ? `, generated on ${generatedAt}` : ''}. It loads
        from this site rather than from the live database, so it stays available
        when the database is resting.
      </p>

      <p className="catalogue-source-notice__body">
        This snapshot has{' '}
        <strong>not been reconciled against the production database</strong>.
        Opportunities, deadlines and funding can have changed since it was
        generated. Please open each scholarship&rsquo;s official source link to
        confirm the deadline and requirements before you rely on them or apply.
      </p>

      <p className="catalogue-source-notice__body catalogue-source-notice__body--muted">
        This snapshot does not hide a scholarship for being unverified or for
        having no image. Only the three rules above exclude a record.
      </p>

      <p className="catalogue-source-notice__body catalogue-source-notice__body--muted">
        Records shown are the ones the catalogue treats as publicly visible:
        {meta.visibility_predicate}
        {meta.deadline_passed
          ? ', and whose deadline had not passed when this snapshot was generated.'
          : '.'}
      </p>

      <p className="catalogue-source-notice__body catalogue-source-notice__body--muted">
        {meta.public_record_count !== undefined && meta.source_record_count !== undefined
          ? `${meta.public_record_count} of ${meta.source_record_count} records are included.`
          : null}
      </p>
    </aside>
  )
}
