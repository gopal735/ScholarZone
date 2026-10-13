/**
 * Discoverability of the tutorial system.
 *
 * The three things a reader must not have to guess:
 *
 *   1. there is a way to get help at all — the home page says so, beside the
 *      primary actions, without being behind a menu;
 *   2. the navigation label says what it is, on the visible text and not only
 *      for a screen reader;
 *   3. a deep link into one guide opens that guide, so the CTA on the home page
 *      is a real entry point rather than a landing on the directory.
 *
 * A fourth is what must NOT happen: no entry point may exist for a route that
 * has no tutorial, or a reader clicks and gets a panel saying the guide is
 * missing. That is asserted by mapping every mount against the registry.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom'
import { AuthContext } from '../../../context/authContext'
import { CompareProvider } from '../../../context/CompareContext.jsx'
import { SavedScholarshipsProvider } from '../../../context/SavedScholarshipsContext.jsx'
import { ThemeProvider } from '../../../context/ThemeContext.jsx';

import { ROUTES, ROUTES_WITHOUT_TUTORIAL } from '../lib/routeMap.js';
import { TUTORIALS, routesOf } from '../lib/registry.js';
import { TutorialLanguageProvider } from '../state/TutorialLanguageContext.jsx';
import HelpCenterPage from '../HelpCenterPage.jsx';

/** Every <HowToUse route=…> actually mounted in the app, read from source. */
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

/**
 * The source root, resolved from this file's own location.
 *
 * A directory walk up to the nearest package.json also matches `node_modules`
 * ancestors along the way, so it is pinned to the levels actually present:
 * this file is `src/features/tutorials/__tests__`, six levels below the package
 * root of the frontend package.
 */
const pagesDir = join(import.meta.dirname, '..', '..', '..', 'pages');

function listFiles(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...listFiles(full));
    else if (/\.jsx?$/.test(entry.name)) out.push(full);
  }
  return out;
}

function mountedRoutes() {
  const found = [];
  for (const file of listFiles(pagesDir)) {
    const src = readFileSync(file, 'utf8');
    const re = /<HowToUse\s+route="([^"]+)"/g;
    let m;
    while ((m = re.exec(src)) !== null) found.push(m[1]);
  }
  return found;
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/** The auth value a bare render needs; nothing here depends on it. */
const authValue = {
  status: 'unauthenticated',
  user: null,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}

function renderHelp(entry = '/help') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <TutorialLanguageProvider>
        <HelpCenterPage />
      </TutorialLanguageProvider>
    </MemoryRouter>,
  );
}

describe('the home page CTA', () => {
  /**
   * The CTA is asserted against the hero's rendered output rather than a string
   * grep, because "add a link" and "add a link a reader can see" are different
   * requirements and only the second is what was asked for.
   */
  it('is rendered, labelled, and points at the Home guide', async () => {
    const ScholarZoneHero = (await import('../../../components/ScholarZoneHero.jsx')).default;
    render(
      <MemoryRouter>
        <AuthContext.Provider value={authValue}>
          <ScholarZoneHero />
        </AuthContext.Provider>
      </MemoryRouter>,
    );

    const cta = screen.getByRole('link', { name: /How to use ScholarZone/i });
    expect(cta).toBeInTheDocument();
    expect(cta).toHaveAttribute('href', '/help?tutorial=home');
  });

  it('sits in the hero actions, beside the primary CTAs', async () => {
    const ScholarZoneHero = (await import('../../../components/ScholarZoneHero.jsx')).default;
    render(
      <MemoryRouter>
        <AuthContext.Provider value={authValue}>
          <ScholarZoneHero />
        </AuthContext.Provider>
      </MemoryRouter>,
    );

    const actions = document.querySelector('.sz-hero__actions');
    expect(actions).not.toBeNull();

    // All three, in the same group: the two browsing actions and help.
    const hrefs = Array.from(actions.querySelectorAll('a')).map((a) => a.getAttribute('href'));
    expect(hrefs).toContain('/scholarships');
    expect(hrefs).toContain('/countries');
    expect(hrefs).toContain('/help?tutorial=home');
  });

  it('is not hidden behind a menu', async () => {
    // A disclosure, a details, or a summary would make it conditional.
    const ScholarZoneHero = (await import('../../../components/ScholarZoneHero.jsx')).default;
    const { container } = render(
      <MemoryRouter>
        <AuthContext.Provider value={authValue}>
          <ScholarZoneHero />
        </AuthContext.Provider>
      </MemoryRouter>,
    );
    expect(container.querySelector('.sz-hero__actions details')).toBeNull();
    expect(container.querySelector('.sz-hero__actions summary')).toBeNull();
    expect(container.querySelector('[aria-haspopup]')).toBeNull();
  });
});

describe('the navigation label', () => {
  it('reads Help & Tutorials on the visible text', async () => {
    const Navigation = (await import('../../../components/Navigation.jsx')).default;
    // The navigation reads the compare and saved-scholarship contexts for its
    // badges, and the theme for its active-link colour, so it cannot be
    // rendered bare even though neither badge nor colour is asserted.
    render(
      <MemoryRouter>
        <ThemeProvider>
          <AuthContext.Provider value={authValue}>
            <CompareProvider>
              <SavedScholarshipsProvider>
                <Navigation />
              </SavedScholarshipsProvider>
            </CompareProvider>
          </AuthContext.Provider>
        </ThemeProvider>
      </MemoryRouter>,
    );
    const link = screen.getByRole('link', { name: /Help & Tutorials/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/help');
  });

  it('does not rely on a screen-reader-only label for its name', async () => {
    // The earlier version rendered "Help" and carried the real phrase in an
    // sz-sr-only span, so a sighted reader got a word that explains nothing
    // while a screen-reader user got the full phrase.
    const Navigation = (await import('../../../components/Navigation.jsx')).default;
    const { container } = render(
      <MemoryRouter>
        <ThemeProvider>
          <AuthContext.Provider value={authValue}>
            <CompareProvider>
              <SavedScholarshipsProvider>
                <Navigation />
              </SavedScholarshipsProvider>
            </CompareProvider>
          </AuthContext.Provider>
        </ThemeProvider>
      </MemoryRouter>,
    );
    const link = screen.getByRole('link', { name: /Help & Tutorials/i });
    // The accessible name comes from the link's own text, not a child span.
    const visible = link.textContent.replace(/\s+/g, ' ').trim();
    expect(visible).toBe('Help & Tutorials');
    expect(container.querySelector('.nav-utility-link .sz-sr-only')).toBeNull();
  });
});

describe('deep linking into one guide', () => {
  it('opens the Home guide from ?tutorial=home', async () => {
    renderHelp('/help?tutorial=home');
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /What this feature does/i })).toBeInTheDocument();
    });
    // The Home tutorial's own opening line. It appears in more than one place
    // (the card summary and the reader), so the assertion is that the guide is
    // present rather than that it is present exactly once.
    expect(screen.getAllByText(/The front door\./i).length).toBeGreaterThan(0);
  });

  it('opens the same guide by id as by route', async () => {
    renderHelp('/help?tutorial=scholarships');
    await waitFor(() => {
      expect(screen.getAllByText(/The catalogue\./i).length).toBeGreaterThan(0);
    });
  });

  it('falls back to a not-found panel for an unknown id', () => {
    renderHelp('/help?tutorial=no-such-tutorial')
    expect(screen.getByText(/Nothing matches that search/i)).toBeInTheDocument()
  })
})

describe('every mounted entry opens a real guide', () => {
  /**
   * The rule behind this: an entry point whose panel would say the guide is
   * missing is worse than no entry point. It is asserted by reading the mounts
   * out of the source, so adding a <HowToUse route> to a page without a
   * tutorial fails here rather than at a reader's click.
   */
  it('maps every mount to an enabled tutorial', () => {
    const mounted = mountedRoutes();
    expect(mounted.length).toBeGreaterThan(0)

    for (const route of mounted) {
      const entry = ROUTES[route];
      expect(entry, `route ${route} is in the route audit`).toBeTruthy();
      const id = entry?.tutorial;
      expect(id, `route ${route} has a tutorial`).toBeTruthy();

      const tutorial = TUTORIALS.find((entry) => entry.id === id);
      expect(tutorial, `tutorial ${id} exists`).toBeTruthy();
      expect(tutorial.status, `tutorial ${id} is enabled`).toBe('enabled');
    }
  })

  it('never mounts an entry for a route with no tutorial', () => {
    const disabled = new Set(ROUTES_WITHOUT_TUTORIAL);
    for (const route of mountedRoutes()) {
      expect(disabled.has(route), `route ${route} must not have a contextual entry`).toBe(false)
    }
  })

  it('mounts an entry on every route that has one, so guidance is discoverable', () => {
    // Not yet every route — the journey carries its own i18n and the admin pages
    // are staff-only. This assertion pins what is covered so a removal fails.
    const mounted = new Set(mountedRoutes());
    for (const route of sortedExpectations()) {
      expect(mounted.has(route), `route ${route} is expected to have a contextual entry`).toBe(true)
    }
  })
})

/**
 * The routes this wave commits to covering with a mounted contextual entry.
 *
 * `/` is deliberately absent: the home page reaches the Home guide through the
 * hero CTA linking to `/help?tutorial=home`, not through a `HowToUse` mount.
 * Asserting a mount here would be asserting the wrong mechanism.
 *
 * The journey and the admin routes are absent for real reasons: the journey
 * carries its own language control, and the admin pages are staff-only.
 */
function sortedExpectations() {
  return [
    '/countries',
    '/scholarships',
    '/scholarships/:id',
    '/match',
    '/saved',
    '/plan',
    '/statement',
    '/dashboard',
    '/applications',
    '/mentor',
    '/compare',
  ];
}

describe('tutorials stay closed until asked', () => {
  it('shows only the trigger on mount, with the panel absent', async () => {
    const { HowToUse } = await import('../components/HowToUse.jsx')
    render(
      <MemoryRouter>
        <TutorialLanguageProvider>
          <HowToUse route="/plan" />
        </TutorialLanguageProvider>
      </MemoryRouter>,
    )
    const trigger = screen.getByRole('button', { name: /How to use this/i })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(document.querySelector('.ts-howto__panel')).toBeNull()
  })
})

describe('dismissal and language survive a mount', () => {
  it('keeps a stored dismissal', async () => {
    window.localStorage.setItem(
      'scholarzone.tutorials.v1',
      JSON.stringify({
        schema: 'scholarzone.tutorials',
        version: 1,
        language: 'en',
        dismissed: { plan: true },
      }),
    )
    const { HowToUse } = await import('../components/HowToUse.jsx')
    render(
      <MemoryRouter>
        <TutorialLanguageProvider>
          <HowToUse route="/plan" />
        </TutorialLanguageProvider>
      </MemoryRouter>,
    )
    // The trigger is still there — dismissal hides the *auto-shown* guide, not
    // the entry point — and the panel stays closed.
    expect(screen.getByRole('button', { name: /How to use this/i })).toBeInTheDocument()
    expect(document.querySelector('.ts-howto__panel')).toBeNull()
  })

  it('keeps a stored language', async () => {
    window.localStorage.setItem(
      'scholarzone.tutorials.v1',
      JSON.stringify({
        schema: 'scholarzone.tutorials',
        version: 1,
        language: 'bn',
        dismissed: {},
      }),
    )
    const { HowToUse } = await import('../components/HowToUse.jsx')
    render(
      <MemoryRouter>
        <TutorialLanguageProvider>
          <HowToUse route="/plan" />
        </TutorialLanguageProvider>
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /কীভাবে ব্যবহার করবেন/i })).toBeInTheDocument()
    })
  })
})

describe('registry integrity for the mounts', () => {
  it('has no duplicate tutorial ids', () => {
    const ids = TUTORIALS.map((t) => t.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('has no orphan tutorials', () => {
    for (const tutorial of TUTORIALS) {
      expect(routesOf(tutorial).length, `${tutorial.id} has a route`).toBeGreaterThan(0)
    }
  })
})
