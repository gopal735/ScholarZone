import { STRINGS } from '../strings.js';

/**
 * One finding.
 *
 * Every piece of user text here is rendered as a text node ({"{text}"}), so
 * a document containing "<script>" is displayed as that literal text and
 * never parsed as markup. There is no dangerouslySetInnerHTML anywhere in
 * this feature. The integration test pastes a document with HTML and
 * asserts it appears as text.
 *
 * The category is signalled by its name as well as its colour, so the
 * meaning does not depend on seeing colour.
 */
export default function FindingCard({
  finding,
  isDismissed,
  isReviewed,
  onDismiss,
  onUndoDismiss,
  onReview,
}) {
  return (
    <article className={`ca-finding${isDismissed ? ' ca-finding--dismissed' : ''}`} data-rule={finding.ruleId}>
      <header className="ca-finding__head">
        <span className="ca-finding__category">{finding.category}</span>
        <span className="ca-finding__confidence">
          {STRINGS.findings.confidence}: {finding.confidence}
        </span>
        {isReviewed && <span className="ca-finding__badge ca-finding__badge--reviewed">{STRINGS.findings.reviewed}</span>}
      </header>

      <div className="ca-finding__body">
        <p className="ca-finding__reason">
          <strong>{STRINGS.findings.why}:</strong> {finding.reason}
        </p>

        {finding.question && (
          <p className="ca-finding__question">
            <strong>{STRINGS.findings.question}:</strong> {finding.question}
          </p>
        )}

        <div className="ca-finding__excerpts">
          <p className="ca-finding__excerpts-label">{STRINGS.findings.excerpts}</p>
          <ul>
            {finding.excerpts.map((excerpt, index) => (
              <li key={`${excerpt.documentId}-${excerpt.start}-${index}`}>
                <span className="ca-finding__doc">{excerpt.documentLabel}</span>
                <blockquote className="ca-finding__excerpt">{excerpt.text}</blockquote>
              </li>
            ))}
          </ul>
        </div>

        {finding.support?.length > 0 && (
          <div className="ca-finding__support">
            <p className="ca-finding__support-label">{STRINGS.findings.support}</p>
            <ul>
              {finding.support.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        )}

        <p className="ca-finding__rule">
          {STRINGS.findings.rule}: {finding.ruleId} — {finding.ruleName}
        </p>
      </div>

      <footer className="ca-finding__actions">
        {isDismissed ? (
          <button className="glass-btn glass-btn--ghost glass-btn--sm" type="button" onClick={() => onUndoDismiss(finding.id)}>
            {STRINGS.findings.undo}
          </button>
        ) : (
          <button className="glass-btn glass-btn--ghost glass-btn--sm" type="button" onClick={() => onDismiss(finding.id)}>
            {STRINGS.findings.dismiss}
          </button>
        )}
        <button
          className="glass-btn glass-btn--ghost glass-btn--sm"
          type="button"
          onClick={() => onReview(finding.id)}
          aria-pressed={isReviewed}
        >
          {isReviewed ? STRINGS.findings.reviewed : STRINGS.findings.review}
        </button>
      </footer>
    </article>
  );
}
