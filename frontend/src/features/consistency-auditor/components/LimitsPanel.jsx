import { STRINGS } from '../strings.js';

/**
 * The limits panel and the persistent notice.
 *
 * Their wording is part of the product contract: the feature is a reading
 * aid for the student's own text, so the panel has to say, in the middle of
 * the page where a reader will see it, that the results are suggestions and
 * that no verdict about truth, authorship or admission is being made.
 */
export function LimitsPanel() {
  return (
    <section className="ca-panel" aria-labelledby="ca-limits-heading">
      <h3 id="ca-limits-heading">{STRINGS.limits.heading}</h3>
      {STRINGS.limits.body.map((paragraph, index) => (
        <p key={index}>{paragraph}</p>
      ))}
      <p className="ca-panel__note">{STRINGS.limits.languageNote}</p>
    </section>
  );
}

/** Shown above and below the results, so it is never off-screen. */
export function PersistentNotice() {
  return (
    <p className="ca-notice" role="note">
      {STRINGS.persistentNotice}
    </p>
  );
}
