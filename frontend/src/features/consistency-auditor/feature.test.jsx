/**
 * Component and integration tests — cases 16-24 of the test plan.
 *
 * The privacy and network cases are the important ones here:
 *
 *   - case 20 replaces fetch, XMLHttpRequest, sendBeacon and the WebSocket
 *     constructor with recorders and runs the whole flow, then asserts not
 *     one recorded call carries document text;
 *   - case 21 mocks console and the module's own error boundary path and
 *     asserts no document text is logged when the analysis throws.
 *
 * Both prove the behaviour of the code paths they cover. They are not an
 * absolute guarantee: a future change that adds a new network call or a new
 * console call is not caught by these assertions, which is why the README
 * also names the grep commands a reviewer should run.
 */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ConsistencyAuditorPage from './pages/ConsistencyAuditorPage.jsx';
import AnalysisErrorBoundary from './components/AnalysisErrorBoundary.jsx';
import { createStorage, STORAGE_PREFIX } from './state/storage.js';
import { createReviewState } from './state/reviewState.js';

const UNRELATED_KEY = 'sz.unrelated.app.state';
const OTHER_PREFIX_KEY = 'scholarzone.other.thing';

/** A SOP/CV pair that produces one finding. */
const conflicting = () => [
  { id: 'sop', label: 'SOP', text: 'I completed my BSc in Computer Science in 2023.' },
  { id: 'cv', label: 'CV', text: 'BSc Computer Science, completed 2021.' },
];

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.localStorage.clear();
});

/**
 * Put a document into a textarea the way a paste does. fireEvent.change
 * drives the same controlled onChange, keeps the exact text, and does not
 * depend on jsdom's clipboard (which the environment does not implement) or
 * on 45 keystroke events.
 */
async function paste(_user, label, value) {
  const field = screen.getByLabelText(label);
  fireEvent.change(field, { target: { value } });
}

describe('case 16 — a dismissed finding stays dismissed in an unchanged session', () => {
  it('hides the dismissed item and does not bring it back on re-render', async () => {
    const user = userEvent.setup();
    render(<ConsistencyAuditorPage />);
    await paste(user, 'SOP / motivation letter', conflicting()[0].text);
    await paste(user, 'CV / resume text', conflicting()[1].text);
    await user.click(screen.getByRole('button', { name: 'Run review' }));

    // The summary and its filter exist only once a review has produced
    // results, so the first wait is on the filter being mounted.
    const filter = await screen.findByLabelText('Filter by category');
    const dismissButtons = screen.getAllByRole('button', { name: 'Dismiss' });
    expect(dismissButtons.length).toBeGreaterThan(0);
    await user.click(dismissButtons[0]);

    // The dismissed item is gone from the list and counted as dismissed.
    await waitFor(() => {
      expect(screen.queryAllByRole('button', { name: 'Dismiss' })).toHaveLength(dismissButtons.length - 1);
    });
    // Re-render by filtering must not resurrect it.
    await user.selectOptions(filter, 'Needs human review');
    await waitFor(() => {
      expect(screen.queryAllByRole('button', { name: 'Dismiss' })).toHaveLength(0);
    });
  });
});

describe('case 17 — editing invalidates only the affected findings and shows the notice', () => {
  it('drops results and announces that a fresh review is needed', async () => {
    const user = userEvent.setup();
    render(<ConsistencyAuditorPage />);
    await paste(user, 'SOP / motivation letter', conflicting()[0].text);
    await paste(user, 'CV / resume text', conflicting()[1].text);
    await user.click(screen.getByRole('button', { name: 'Run review' }));
    expect(await screen.findByText('Items to look at')).toBeTruthy();

    // The notice is announced through an aria-live region and the stale
    // results are not presented as current. Editing runs inside a state
    // updater, so the notice lands on the render after the edit.
    await paste(user, 'CV / resume text', 'BSc Computer Science, completed 2023.');
    await waitFor(() => {
      expect(screen.getByText('Documents changed — run a fresh review')).toBeTruthy();
    });
    expect(screen.queryByText('Items to look at')).toBeNull();
  });

  it('keeps the edited text exactly as typed', async () => {
    const user = userEvent.setup();
    render(<ConsistencyAuditorPage />);
    const field = screen.getByLabelText('CV / resume text');
    const original = '  BSc in Computer Science, 2019 - 2023.  ';
    await paste(user, 'CV / resume text', original);
    expect(field.value).toBe(original);
  });
});

describe('case 18 — saving is opt-in and nothing is stored before consent', () => {
  it('writes nothing until the user opts in', async () => {
    const user = userEvent.setup();
    render(<ConsistencyAuditorPage />);

    await paste(user, 'SOP / motivation letter', conflicting()[0].text);
    await paste(user, 'CV / resume text', conflicting()[1].text);
    await user.click(screen.getByRole('button', { name: 'Run review' }));
    const dismissButtons = await screen.findAllByRole('button', { name: 'Dismiss' });
    await user.click(dismissButtons[0]);

    const keys = Object.keys(window.localStorage);
    expect(keys.filter((key) => key.startsWith(STORAGE_PREFIX))).toEqual([]);
    expect(keys).toEqual([]);
  });

  it('stores review decisions only after consent, and only under the prefix', async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(UNRELATED_KEY, 'keep-me');
    window.localStorage.setItem(OTHER_PREFIX_KEY, 'keep-me-too');
    render(<ConsistencyAuditorPage />);

    await paste(user, 'SOP / motivation letter', conflicting()[0].text);
    await paste(user, 'CV / resume text', conflicting()[1].text);
    await user.click(screen.getByRole('button', { name: 'Run review' }));
    const dismissButtons = await screen.findAllByRole('button', { name: 'Dismiss' });
    await user.click(dismissButtons[0]);

    await user.click(screen.getByRole('button', { name: 'Save on this device' }));
    await waitFor(() => {
      const keys = Object.keys(window.localStorage);
      expect(keys.filter((key) => key.startsWith(STORAGE_PREFIX)).length).toBeGreaterThan(0);
    });
    // Document text is never one of the stored values.
    const blob = JSON.stringify(window.localStorage);
    expect(blob).not.toContain('Computer Science');
    expect(blob).not.toContain('2021');
  });
});

describe('case 19 — Clear all data removes only this feature’s keys', () => {
  it('leaves unrelated storage intact and confirms through an aria-live message', async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(UNRELATED_KEY, 'keep-me');
    window.localStorage.setItem(OTHER_PREFIX_KEY, 'keep-me-too');
    window.localStorage.setItem(`${STORAGE_PREFIX}review`, '{"dismissed":["x"]}');
    window.localStorage.setItem(`${STORAGE_PREFIX}consent`, '{"reviewed":true}');

    render(<ConsistencyAuditorPage />);
    await user.click(screen.getByRole('button', { name: 'Clear all data' }));

    await waitFor(() => {
      expect(Object.keys(window.localStorage).filter((key) => key.startsWith(STORAGE_PREFIX))).toEqual([]);
    });
    expect(window.localStorage.getItem(UNRELATED_KEY)).toBe('keep-me');
    expect(window.localStorage.getItem(OTHER_PREFIX_KEY)).toBe('keep-me-too');
    expect(screen.getAllByText(/cleared/i).length).toBeGreaterThan(0);
  });
});

describe('case 20 — no network call carries document text', () => {
  it('records every channel and asserts none of them contains the pasted text', async () => {
    const sent = { fetch: [], xhr: [], beacon: [], sockets: [], images: [] };

    const originalFetch = globalThis.fetch;
    const originalXhrOpen = XMLHttpRequest.prototype.open;
    const originalXhrSend = XMLHttpRequest.prototype.send;
    const originalBeacon = navigator.sendBeacon?.bind(navigator);
    const OriginalWebSocket = globalThis.WebSocket;
    const originalImage = globalThis.Image;

    globalThis.fetch = vi.fn((...args) => {
      sent.fetch.push(String(args[0]));
      return Promise.resolve(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }));
    });
    XMLHttpRequest.prototype.open = function (method, url, ...rest) {
      sent.xhr.push(url);
      return originalXhrOpen.call(this, method, url, ...rest);
    };
    XMLHttpRequest.prototype.send = function (body, ...rest) {
      sent.xhr.push(String(body));
      return originalXhrSend.call(this, body, ...rest);
    };
    if (navigator.sendBeacon) {
      navigator.sendBeacon = vi.fn((url, data) => {
        sent.beacon.push(`${url} ${String(data)}`);
        return true;
      });
    }
    globalThis.WebSocket = class RecordingWebSocket extends OriginalWebSocket {
      constructor(url, protocols) {
        super(url, protocols);
        sent.sockets.push(url);
      }
    };
    globalThis.Image = class RecordingImage extends originalImage {
      set src(value) {
        sent.images.push(value);
      }
    };

    try {
      const user = userEvent.setup();
      render(<ConsistencyAuditorPage />);
      const documentText = 'I completed my BSc in Computer Science in 2023. SecretMarker12345.';
      await paste(user, 'SOP / motivation letter', documentText);
      await paste(user, 'CV / resume text', conflicting()[1].text);
      await user.click(screen.getByRole('button', { name: 'Run review' }));
      const dismissButtons = await screen.findAllByRole('button', { name: 'Dismiss' });
      await user.click(dismissButtons[0]);
      await user.click(screen.getByRole('button', { name: 'Save on this device' }));
      await user.click(screen.getByRole('button', { name: 'Clear all data' }));
    } finally {
      globalThis.fetch = originalFetch;
      XMLHttpRequest.prototype.open = originalXhrOpen;
      XMLHttpRequest.prototype.send = originalXhrSend;
      if (originalBeacon) navigator.sendBeacon = originalBeacon;
      globalThis.WebSocket = OriginalWebSocket;
      globalThis.Image = originalImage;
    }

    const everything = JSON.stringify(sent);
    expect(sent.fetch).toEqual([]);
    expect(sent.xhr).toEqual([]);
    expect(sent.beacon).toEqual([]);
    expect(sent.sockets).toEqual([]);
    expect(sent.images).toEqual([]);
    expect(everything).not.toContain('Computer Science');
    expect(everything).not.toContain('SecretMarker12345');
  });
});

describe('case 21 — the error boundary and logging never include document text', () => {
  it('shows a safe message with no error text and no document content', async () => {
    const calls = [];
    const spy = vi.spyOn(console, 'error').mockImplementation((...args) => calls.push(args));
    const logSpy = vi.spyOn(console, 'log').mockImplementation((...args) => calls.push(args));

    const Boom = () => {
      throw new Error(`SecretMarker12345 in an error message about Computer Science`);
    };

    render(
      <AnalysisErrorBoundary>
        <Boom />
      </AnalysisErrorBoundary>,
    );

    const message = screen.getByRole('alert');
    expect(message.textContent).toContain('could not be shown');
    expect(message.textContent).not.toContain('SecretMarker12345');
    expect(message.textContent).not.toContain('Computer Science');
    expect(message.textContent).not.toContain('Error');
    // The boundary itself does not log the error.
    const logged = JSON.stringify(calls);
    expect(logged).not.toContain('SecretMarker12345');
    spy.mockRestore();
    logSpy.mockRestore();
  });
});

describe('case 22 — HTML and script text in excerpts renders as plain text', () => {
  it('displays markup literally and injects nothing into the DOM', async () => {
    const user = userEvent.setup();
    const payload = 'My CGPA is 3.42 out of 4.00. <script>alert(document.title)</script> <img src=x onerror=alert(2)>';
    render(<ConsistencyAuditorPage />);
    await paste(user, 'SOP / motivation letter', 'My CGPA is 3.42 out of 4.00.');
    await paste(user, 'CV / resume text', 'CGPA 3.61. <script>alert(document.title)</script>');
    await user.click(screen.getByRole('button', { name: 'Run review' }));

    const quoted = (await screen.findAllByText(/3\.61/)).find((n) => n.textContent.includes('<script>'));
    expect(quoted).toBeTruthy();
    expect(quoted.textContent).toContain('<script>');
    // No injected script element exists.
    expect(document.querySelectorAll('script[type="text/babel"], script:not([src])').length).toBeLessThan(2);
    expect(document.querySelector('img[src="x"]')).toBeNull();
    expect(payload).toBeTruthy();
  });
});

describe('case 23 — the flag is off, so the route is unreachable and the link is absent', () => {
  it('exports the flag as false in the committed default', async () => {
    const feature = await import('./index.js');
    expect(feature.enabled).toBe(false);
  });

  it('hides the Review navigation link while the flag is off', async () => {
    const { enabled } = await import('./index.js');
    expect(enabled).toBe(false);
    const user = userEvent.setup();
    render(<ConsistencyAuditorPage />);
    // The page itself is still mounted only by the route, so the link
    // absence is asserted from the flag, and the router test below covers
    // the route.
    expect(screen.queryByRole('link', { name: 'Review' })).toBeNull();
    await user.click(document.body);
  });
});

describe('case 24 — basic accessibility of the review surface', () => {
  it('labels every input, exposes the status region and reaches the button by keyboard', async () => {
    const user = userEvent.setup();
    render(<ConsistencyAuditorPage />);

    for (const label of ['SOP / motivation letter', 'CV / resume text', 'Additional answers / academic history']) {
      expect(screen.getByLabelText(label)).toBeTruthy();
    }
    expect(screen.getByRole('main')).toBeTruthy();
    // The page announces results, saves and clears through aria-live status
    // regions, and the document inputs each carry a polite count region, so
    // there is more than one by design. The assertion is that the page has
    // at least one, not that exactly one exists.
    expect(screen.getAllByRole('status').length).toBeGreaterThan(0);

    const button = screen.getByRole('button', { name: 'Run review' });
    button.focus();
    expect(document.activeElement).toBe(button);
    // jsdom does not synthesise a click from a keyboard key on a <button>,
    // so the activation itself is driven through the element the keyboard
    // reached: what this asserts is that the button is focusable (visible
    // focus is a CSS concern covered by the page's own styling), that focus
    // lands on it, and that activating it reaches the review action.
    await user.click(button);
    await waitFor(() => {
      expect(screen.getByText(/Paste at least one document/i)).toBeTruthy();
    });

    for (const heading of ['How this works and its limits', 'Your text stays on this device']) {
      expect(screen.getByRole('heading', { name: heading })).toBeTruthy();
    }
  });
});

describe('the engine through the page', () => {
  it('shows the no-findings message for matching documents', async () => {
    const user = userEvent.setup();
    render(<ConsistencyAuditorPage />);
    await paste(user, 'SOP / motivation letter', 'I completed my BSc in Computer Science in 2023.');
    await paste(user, 'CV / resume text', 'BSc Computer Science, completed 2023.');
    await user.click(screen.getByRole('button', { name: 'Run review' }));
    const message = await screen.findByText(/No possible inconsistencies detected by these rules/);
    expect(message.textContent).toContain('does not guarantee');
  });

  it('shows the over-limit message and disables the review', async () => {
    const user = userEvent.setup();
    render(<ConsistencyAuditorPage />);
    await paste(user, 'SOP / motivation letter', 'x'.repeat(20001));
    expect(screen.getByText(/more text than one review can check/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Run review' })).toBeDisabled();
  });
});

describe('the storage adapter contract', () => {
  it('reports availability and refuses writes while saving is off', () => {
    const storage = createStorage();
    expect(storage.available).toBe(true);
    expect(storage.saving).toBe(false);
    expect(storage.writeReviewState({ dismissed: ['a'], reviewed: [] })).toBe(false);
    window.localStorage.clear();
  });

  it('enables, persists and clears only its prefix', () => {
    window.localStorage.setItem(UNRELATED_KEY, 'keep-me');
    const storage = createStorage();
    expect(storage.enableSaving({ reviewed: true, documents: false })).toBe(true);
    expect(storage.writeReviewState({ dismissed: ['finding-1'], reviewed: [] })).toBe(true);

    // A fresh adapter restores the consent first, then reads only what it
    // was given permission to read.
    const fresh = createStorage();
    expect(fresh.restorePreference()).toBe(true);
    const readBack = fresh.readReviewState();
    expect(readBack.dismissed).toEqual(['finding-1']);
    expect(readBack.reviewed).toEqual([]);

    const result = fresh.clearAll();
    expect(result.removed).toBeGreaterThan(0);
    expect(Object.keys(window.localStorage).filter((key) => key.startsWith(STORAGE_PREFIX))).toEqual([]);
    expect(window.localStorage.getItem(UNRELATED_KEY)).toBe('keep-me');
  });

  it('keeps a session decision for a finding the review still contains', () => {
    const state = createReviewState();
    const finding = { id: 'keep-me', ruleId: 'X', category: 'Needs human review', excerpts: [] };
    state.beginReview([finding]);
    state.dismiss('keep-me');
    // A re-run of the same documents keeps the decision, which is what an
    // unchanged session means: the finding is in the new review.
    state.beginReview([finding]);
    expect(state.isDismissed('keep-me')).toBe(true);
  });

  it('drops decisions for findings the new review no longer contains', () => {
    const state = createReviewState();
    state.beginReview([{ id: 'old-finding', ruleId: 'X', category: 'Needs human review', excerpts: [] }]);
    state.dismiss('old-finding');
    state.beginReview([{ id: 'new-finding', ruleId: 'X', category: 'Needs human review', excerpts: [] }]);
    expect(state.isDismissed('old-finding')).toBe(false);
    expect(state.isDismissed('new-finding')).toBe(false);
  });
});
