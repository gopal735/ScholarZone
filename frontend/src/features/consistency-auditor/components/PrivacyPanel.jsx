import { STRINGS } from '../strings.js';

/**
 * The privacy panel: what is stored, where, who can read it, and how to
 * remove it.
 *
 * The two controls are deliberately separate from the review itself: saving
 * is opt-in and explained BEFORE the choice, and clearing removes only this
 * feature's namespaced keys and confirms through an aria-live message.
 */
export default function PrivacyPanel({ saving, storageRemoved, onEnableSaving, onClearAll }) {
  return (
    <section className="ca-panel ca-privacy" aria-labelledby="ca-privacy-heading">
      <h3 id="ca-privacy-heading">{STRINGS.privacy.heading}</h3>
      {STRINGS.privacy.beforeSave.map((paragraph, index) => (
        <p key={index}>{paragraph}</p>
      ))}

      <div className="ca-privacy__controls">
        <button
          className={`glass-btn glass-btn--sm${saving ? ' glass-btn--active' : ''}`}
          type="button"
          onClick={onEnableSaving}
          aria-pressed={saving}
        >
          {STRINGS.privacy.saveOn}
        </button>
        <button className="glass-btn glass-btn--ghost glass-btn--sm" type="button" onClick={onClearAll}>
          {STRINGS.privacy.clear}
        </button>
        <span className="ca-privacy__confirm">{STRINGS.privacy.clearConfirm}</span>
      </div>

      <p className="ca-privacy__status" role="status" aria-live="polite">
        {storageRemoved ? STRINGS.notice.cleaned : saving ? STRINGS.notice.saved : STRINGS.notice.notSaved}
      </p>
    </section>
  );
}
