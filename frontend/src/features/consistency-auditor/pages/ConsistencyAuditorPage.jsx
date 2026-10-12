import { useCallback, useMemo, useState } from 'react';

import AnalysisErrorBoundary from '../components/AnalysisErrorBoundary.jsx';
import DocumentInputs from '../components/DocumentInputs.jsx';
import FindingCard from '../components/FindingCard.jsx';
import { LimitsPanel, PersistentNotice } from '../components/LimitsPanel.jsx';
import PrivacyPanel from '../components/PrivacyPanel.jsx';
import SummaryPanel from '../components/SummaryPanel.jsx';
import { review } from '../engine/index.js';
import { MAX_DOCUMENT_CHARACTERS } from '../engine/index.js';import { createReviewState } from '../state/reviewState.js';
import { STRINGS } from '../strings.js';

const LABELS = {
  sop: 'SOP / motivation letter',
  cv: 'CV / resume text',
  answers: 'Additional answers / history',
};

const emptyDocuments = () => ({
  sop: { id: 'sop', label: LABELS.sop, text: '' },
  cv: { id: 'cv', label: LABELS.cv, text: '' },
  answers: { id: 'answers', label: LABELS.answers, text: '' },
});

/**
 * The page.
 *
 * The analysis runs ONLY when the user presses Run review: there is no
 * per-keystroke path into the engine, so a 20,000-character paste never
 * triggers a review. The documents' text is the single source of truth and
 * is never rewritten here; the engine receives the same strings the
 * textareas hold.
 *
 * The review state is React state (a version counter bumped by the state
 * model), not a ref: a mutation has to re-render, and React forbids reading
 * a ref during render.
 */
export default function ConsistencyAuditorPage() {
  const [documents, setDocuments] = useState(emptyDocuments);
  const [filter, setFilter] = useState('all');
  const [status, setStatus] = useState('');
  const [reviewError, setReviewError] = useState('');
  const [showDismissed, setShowDismissed] = useState(false);
  const [storageRemoved, setStorageRemoved] = useState(false);
  const [, forceRender] = useState(0);
  const [reviewState] = useState(() => {
    const created = createReviewState();
    created.subscribe(() => forceRender((value) => value + 1));
    return created;
  });

  const state = reviewState.state;
  const saving = reviewState.storage.saving;

  const setDocument = useCallback(
    (id, text) => {
      setDocuments((current) => {
        const next = { ...current, [id]: { ...current[id], text } };
        // Editing a document invalidates the previous results entirely: the
        // findings described different text, and presenting them as current
        // would be false. The notice tells the user to run a fresh review.
        reviewState.invalidate();
        return next;
      });
    },
    [reviewState],
  );

  const runReview = useCallback(() => {
    const list = [documents.sop, documents.cv, documents.answers];
    const result = review(list);
    if (!result.ok) {
      // The refusal is the message the user needs. invalidate() also sets
      // the stale flag, which the notice prefers, so the refusal is kept
      // separately and shown first: an over-limit or empty document must
      // not be reported as "documents changed".
      reviewState.invalidate();
      setReviewError(result.message);
      setStatus('');
      return;
    }
    reviewState.beginReview(result.findings);
    reviewState.restoreFromStorage(result.findings);
    setReviewError('');
    setStatus('');
  }, [documents, reviewState]);

  const overLimitId = useMemo(() => {
    for (const document of Object.values(documents)) {
      if (document.text.length > MAX_DOCUMENT_CHARACTERS) return document.id;
    }
    return null;
  }, [documents]);

  const visible = reviewState.visible(showDismissed);
  const dismissed = reviewState.dismissed();
  const filtered = filter === 'all' ? visible : visible.filter((finding) => finding.category === filter);
  const hasRun = state.ranAt !== null && !state.stale;
  const notice = reviewError || (state.stale ? STRINGS.notice.stale : status);

  const dismiss = useCallback(
    (id) => {
      reviewState.dismiss(id);
      setStatus(STRINGS.notice.dismiss);
    },
    [reviewState],
  );
  const undoDismiss = useCallback(
    (id) => {
      reviewState.undoDismiss(id);
      setStatus(STRINGS.notice.dismissUndone);
    },
    [reviewState],
  );
  const reviewFinding = useCallback(
    (id) => {
      reviewState.markReviewed(id);
      setStatus(STRINGS.notice.reviewed);
    },
    [reviewState],
  );

  return (
    <main className="ca-page" id="main-content">
      <div className="ca-page__inner">
        <header className="ca-page__head">
          <h1>{STRINGS.pageTitle}</h1>
          <p className="ca-page__intro">{STRINGS.pageIntro}</p>
          <PersistentNotice />
        </header>

        <AnalysisErrorBoundary>
          <div className="ca-page__body">
            <section className="ca-panel" aria-labelledby="ca-inputs-heading">
              <h2 id="ca-inputs-heading">{STRINGS.inputs.heading}</h2>
              <DocumentInputs documents={documents} onChange={setDocument} overLimitId={overLimitId} />
              <button
                className="glass-btn glass-btn--active"
                type="button"
                onClick={runReview}
                disabled={overLimitId !== null}
              >
                {hasRun ? STRINGS.actions.rerun : STRINGS.actions.run}
              </button>
              <p className="ca-page__status" role="status" aria-live="polite">
                {notice}
              </p>
            </section>

            {hasRun && (
              <>
                <SummaryPanel findings={visible} filter={filter} onFilterChange={setFilter} hasRun />

                <section className="ca-findings" aria-labelledby="ca-findings-heading">
                  <h2 id="ca-findings-heading">{STRINGS.findings.heading}</h2>
                  {filtered.length === 0 ? (
                    <p className="ca-findings__none">{STRINGS.findings.none}</p>
                  ) : (
                    <div className="ca-findings__list">
                      {filtered.map((finding) => (
                        <FindingCard
                          key={finding.id}
                          finding={finding}
                          isDismissed={reviewState.isDismissed(finding.id)}
                          isReviewed={reviewState.isReviewed(finding.id)}
                          onDismiss={dismiss}
                          onUndoDismiss={undoDismiss}
                          onReview={reviewFinding}
                        />
                      ))}
                    </div>
                  )}

                  {dismissed.length > 0 && (
                    <div className="ca-dismissed">
                      <button
                        className="glass-btn glass-btn--ghost glass-btn--sm"
                        type="button"
                        onClick={() => setShowDismissed((value) => !value)}
                        aria-expanded={showDismissed}
                      >
                        {showDismissed ? STRINGS.findings.hideDismissed : STRINGS.findings.showDismissed}
                        {` (${dismissed.length})`}
                      </button>
                      {showDismissed && (
                        <div className="ca-findings__list">
                          {dismissed.map((finding) => (
                            <FindingCard
                              key={finding.id}
                              finding={finding}
                              isDismissed
                              isReviewed={reviewState.isReviewed(finding.id)}
                              onDismiss={dismiss}
                              onUndoDismiss={undoDismiss}
                              onReview={reviewFinding}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </section>
              </>
            )}

            <LimitsPanel />

            <PrivacyPanel
              saving={saving}
              storageRemoved={storageRemoved}
              onEnableSaving={() => {
                const enabled = reviewState.enableSaving({ reviewed: true, documents: false });
                setStorageRemoved(false);
                setStatus(enabled ? STRINGS.notice.saved : STRINGS.notice.notSaved);
              }}
              onClearAll={() => {
                reviewState.clearAll();
                setStorageRemoved(true);
              }}
            />
          </div>
        </AnalysisErrorBoundary>

        <PersistentNotice />
        <p className="ca-page__status" role="status" aria-live="polite">
          {storageRemoved ? STRINGS.notice.cleaned : ''}
        </p>
      </div>
    </main>
  );
}
