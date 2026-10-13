// Playwright config for the Study-to-Career Strategist E2E.
//
// Two viewports - a mobile project (390x844) and a desktop project (1280x900) - so
// the happy path and the insufficient-data path are each asserted on both, per the
// feature's mobile-first requirement. The webServer builds the app with the
// strategist flag on and serves the production build; the spec renders captured
// data via ?fixture=1 so the run needs no backend.
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: '.',
  timeout: 120000,
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:4173' },
  projects: [
    { name: 'mobile', use: { ...devices['Pixel 5'] } },
    { name: 'desktop', use: { viewport: { width: 1280, height: 900 } } },
  ],
  webServer: {
    command: 'node preview-server.mjs',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: true,
    timeout: 180000,
  },
})
