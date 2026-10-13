// Accessible, bilingual primitives for the strategist.
//
// Rules applied throughout: meaning is never carried by colour alone (icons + text
// accompany it), every control has a real label, lists and regions are semantic,
// and Bangla + English are both present by default so a screen reader can read
// either. These are the building blocks the wizard and results compose from.

export function BiText({ pair, mode, className, as = 'span' }) {
  const { en, bn } = pair
  const Tag = as
  if (mode === 'en') return <Tag className={className}>{en}</Tag>
  if (mode === 'bn') return <Tag className={className} lang="bn-BD">{bn}</Tag>
  return (
    <Tag className={className}>
      <span lang="bn-BD">{bn}</span>
      <span className="strategist-en-sub" lang="en-GB"> · {en}</span>
    </Tag>
  )
}

export function SectionTitle({ children, id }) {
  return <h2 id={id} className="strategist-h2">{children}</h2>
}

export function Loading({ label, mode }) {
  return (
    <div className="strategist-state" role="status" aria-live="polite" data-testid="state-loading">
      <span className="strategist-spinner" aria-hidden="true" />
      <BiText pair={label} mode={mode} />
    </div>
  )
}

export function ErrorState({ onRetry, t, mode }) {
  return (
    <div className="strategist-state strategist-state-error" role="alert" data-testid="state-error">
      <BiText pair={t('state.error')} mode={mode} as="p" />
      <button type="button" onClick={onRetry} className="strategist-btn">{t('btn.compare').en}</button>
    </div>
  )
}

export function EmptyState({ t, mode }) {
  return (
    <div className="strategist-state" data-testid="state-empty">
      <BiText pair={t('results.empty')} mode={mode} as="p" />
    </div>
  )
}

export function OfflineBanner({ t, mode }) {
  return (
    <div className="strategist-offline" role="status" data-testid="state-offline">
      <BiText pair={t('state.offline')} mode={mode} as="p" />
    </div>
  )
}

// A badge whose meaning is text, not just colour, so it survives greyscale and
// screen readers.
export function StatusBadge({ status, children }) {
  const tone = status === 'sourced' ? 'ok' : status === 'informational' ? 'warn' : 'bad'
  return (
    <span className={`strategist-badge strategist-badge-${tone}`} data-status={status}>
      <span aria-hidden="true" className="strategist-badge-icon">{status === 'sourced' ? '✓' : status === 'informational' ? '!' : '×'}</span>
      {children}
    </span>
  )
}

export function SourceLink({ source }) {
  if (!source) return null
  return (
    <a className="strategist-source" href={source.url} target="_blank" rel="noopener noreferrer nofollow">
      {source.publisher || source.id}
      <span aria-hidden="true"> ↗</span>
    </a>
  )
}

export function EvidenceMeter({ completeness }) {
  const { sourced, total, fraction } = completeness
  const pct = total ? Math.round((sourced / total) * 100) : 0
  return (
    <div className="strategist-meter" data-testid="evidence-meter">
      <div className="strategist-meter-label">
        <span>Evidence completeness</span>
        <strong>{fraction}</strong>
      </div>
      <div
        className="strategist-meter-track"
        role="meter"
        aria-valuenow={sourced}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-label={`Evidence completeness ${fraction} criteria sourced`}
      >
        <div className="strategist-meter-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
