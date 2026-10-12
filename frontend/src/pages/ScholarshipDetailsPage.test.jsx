/**
 * Scholarship detail page — the IntersectionObserver regression.
 *
 * This page reveals its sections on scroll: `useReveal`
 * (`./ScholarshipDetailsPage.jsx:42`) constructs an
 * `IntersectionObserver` for every non-immediate `Reveal`. jsdom implements
 * neither the observer nor `IntersectionObserverEntry`, so before
 * `src/test/setup.js` supplied a lifecycle stub, rendering this page threw
 *   ReferenceError: IntersectionObserver is not defined
 * at the first effect to run. The failure is latent rather than loud: it only
 * appears once a test renders the page, which is what this file does.
 *
 * What is asserted, and what is not:
 *
 *   - the page finishes rendering after its fetch resolves, which is the thing
 *     that broke;
 *   - the reveal wrapper is mounted, so the effects did run rather than the
 *     page short-circuiting to a state with no reveal children.
 *
 * What is deliberately NOT asserted: that any reveal became visible. The setup
 * stub never invokes the observer callback, and reading an `is-visible` class
 * from it would be asserting on the stub's inertness, not on a browser scroll.
 * A test that needs a callback to fire has to supply its own controllable mock
 * — `ScholarshipsPage.test.jsx` is the existing precedent for that.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

/**
 * Both are stubbed rather than given real data. The goal is to isolate the
 * reveal path from an HTTP round trip and from the catalogue directory, which
 * the detail page reads separately to build its "more like this" links.
 */
vi.mock('../services/scholarshipService', () => ({
  fetchScholarshipById: vi.fn().mockResolvedValue({
    id: '1',
    title: 'Scholarship of Record',
    provider: 'Recording University',
    scholarship_status: 'open',
    country: 'Denmark',
    degree_level: ['Masters'],
    funding_type: 'Full',
    deadline_display: '15 January 2027',
    last_verified: '2026-10-01',
  }),
  ScholarshipApiError: class ScholarshipApiError extends Error {},
}));
vi.mock('../hooks/useScholarshipDirectory', () => ({
  useScholarshipDirectory: () => ({
    scholarships: [],
    isLoading: false,
    error: null,
    isUsingFallback: false,
    catalogueMeta: null,
  }),
}));
/* Two children whose own behaviour is covered elsewhere; keeping them inert so
   a failure here can only be the reveal path. */
vi.mock('../components/ScholarshipActions', () => ({
  default: () => <div data-testid="actions" />,
}));
vi.mock('../components/SupervisorPanel', () => ({
  default: () => <div data-testid="supervisors" />,
}));

import ScholarshipDetailsPage from './ScholarshipDetailsPage.jsx';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderDetailPage() {
  return render(
    <MemoryRouter initialEntries={['/scholarship/1']}>
      <Routes>
        <Route path="/scholarship/:id" element={<ScholarshipDetailsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ScholarshipDetailsPage under jsdom', () => {
  it('exposes an IntersectionObserver, which is what jsdom omits', () => {
    // The setup stub is the thing under test indirectly: without it this is
    // 'undefined' and every test below fails with a ReferenceError.
    expect(typeof IntersectionObserver).toBe('function');
  });

  it('renders the loaded record without an observer error', async () => {
    const { container } = renderDetailPage();

    // Waiting on the record proves the async path finished; a throw in a
    // Reveal effect would otherwise surface as an empty container.
    await waitFor(() => {
      expect(container.textContent).toContain('Scholarship of Record');
    });
  });

  it('mounts the reveal wrappers, so the observer effects did run', async () => {
    const { container } = renderDetailPage();

    await waitFor(() => {
      expect(container.textContent).toContain('Scholarship of Record');
    });

    // Every section is wrapped in a Reveal, so the presence of any wrapper with
    // no error means the effects reached the observer call and came back.
    const reveals = container.querySelectorAll('.sz-reveal');
    expect(reveals.length).toBeGreaterThan(0);
  });

  it('leaves the reveal un-triggered rather than faking a visible one', async () => {
    const { container } = renderDetailPage();

    await waitFor(() => {
      expect(container.textContent).toContain('Scholarship of Record');
    });

    // The immediate reveals are visible from initial state (`useState(immediate)`
    // in useReveal) and never touch an observer. Every other reveal starts
    // hidden and can only become visible through the observer callback, which
    // the stub never invokes. So the invariant is: strictly fewer elements are
    // visible than exist. That is the guard against a future change
    // "helpfully" firing callbacks and letting a test assert on a scroll that
    // never happened.
    const total = container.querySelectorAll('.sz-reveal').length;
    const visible = container.querySelectorAll('.sz-reveal.is-visible').length;
    expect(total).toBeGreaterThan(0);
    expect(visible).toBeLessThan(total);
  });
});
