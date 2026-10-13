// Global Study-to-Career Strategist feature entry.
//
// Ships inert by default (see flags.js): the route and any navigation are guarded
// on `enabled`, which is false unless a deployment opts in with
// VITE_STRATEGIST_ENABLED=true. The backend has an independent switch; both must
// be on for the full experience. The page is exported from here for the lazy
// import in App.jsx; the flag lives in flags.js so it stays statically importable
// without pulling the page into the initial chunk.
export { StrategistPage } from './StrategistPage.jsx'
export { enabled } from './flags.js'
