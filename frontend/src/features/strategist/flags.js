// The strategist's frontend feature flag, kept in its own module so importing it
// does not drag the wizard (and its bundled fixture) into the initial bundle.
// App.jsx imports this statically for the route guard, and lazy-imports the page
// separately, which keeps the experience properly code-split.
export const enabled = String(import.meta.env.VITE_STRATEGIST_ENABLED || '').toLowerCase() === 'true'
