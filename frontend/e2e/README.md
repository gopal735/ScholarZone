# Study-to-Career Strategist E2E

Committed Playwright coverage for the strategist's happy path and insufficient-data
path, on both a mobile (Pixel 5) and a desktop viewport.

## Run

```
npm run test:e2e:strategist
```

This builds the frontend with `VITE_STRATEGIST_ENABLED=true`, serves the production
build (`e2e/preview-server.mjs`), and drives the real route using captured data
(`?fixture=1`) so no backend is required.

## First-time setup

Playwright needs its browser binary, which is not pre-provisioned by the project's
CI:

```
npx playwright install chromium
```

## Residual gap (documented, per task §5)

The GitHub workflow does **not** run this E2E job because browser binaries are not
installed in CI (adding a browser-install step is an infra change deferred from this
PR). It has been run locally and passes (4/4). CI continues to run unit/component
tests, lint and build. To wire E2E into CI, add `npx playwright install --with-deps
chromium` and `npm run test:e2e:strategist` as a workflow step.
