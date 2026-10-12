import { Routes, Route } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import ScholarshipsPage from './pages/ScholarshipsPage'
import MatchPage from './pages/MatchPage'
import ScholarshipDetailsPage from './pages/ScholarshipDetailsPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import SavedScholarshipsPage from './pages/SavedScholarshipsPage'
import PlanPage from './pages/PlanPage'
import ComparePage from './pages/ComparePage'
import DashboardPage from './pages/DashboardPage'
import ApplicationsPage from './pages/ApplicationsPage'
import MentorPage from './pages/MentorPage'
import AdminPage from './pages/AdminPage'
import AdminVerificationPage from './pages/AdminVerificationPage'
import AdminScholarshipPage from './pages/AdminScholarshipManager'
import SopBuilderPage from './pages/SopBuilderPage'
import CountryPage from './pages/CountryPage'
import NotFoundPage from './pages/NotFoundPage'
import { useScrollReveal } from './hooks/useScrollReveal'
import './App.css'

/**
 * The Bangladesh Applicant Journey is lazy-loaded.
 *
 * It is the one route in the app that a first-time visitor to the catalogue
 * never opens, so its code — the seven modules, the Bangla dictionary and the
 * cost planner — would otherwise sit in the initial bundle and cost every
 * reader a download they never use. Splitting it here is the whole reason this
 * route is a separate chunk rather than another eager import.
 */
const JourneyPage = lazy(() =>
  import('./features/journey').then((module) => ({ default: module.JourneyPage })),
)

const JourneyProvider = lazy(() =>
  import('./features/journey').then((module) => ({ default: module.JourneyProvider })),
)

function JourneyFallback() {
  return (
    <div className="jroute-fallback" role="status">
      <p>Loading…</p>
    </div>
  )
}

function App() {
  // Sections and cards arrive as they enter view. Runs on the route change
  // too, so navigating to the catalogue reveals the new page's content rather
  // than waiting for a scroll event that will never come.
  useScrollReveal()

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/countries" element={<CountryPage />} />
        <Route path="/scholarships" element={<ScholarshipsPage />} />
        <Route path="/match" element={<MatchPage />} />
        <Route path="/scholarships/:id" element={<ScholarshipDetailsPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/saved" element={<SavedScholarshipsPage />} />
        {/* The local planning workspace: recently viewed, checklist, deadlines,
            notes and a backup. Declared before the catch-all. It is the
            anonymous half of the workspace, so it sits outside the routes that
            resolve their own server session. */}
        <Route path="/plan" element={<PlanPage />} />
        {/* The statement-of-purpose builder. Declared before the catch-all, and
            deliberately beside /plan rather than inside it: it is the second
            browser-local workspace, with no server, no account and no sync, so
            it needs no session resolution of its own. */}
        <Route path="/statement" element={<SopBuilderPage />} />
        {/* Declared before the catch-all. The dashboard resolves its own access
            state from the server session rather than wrapping the route in a
            client-side guard, because the guard would only be able to trust a
            value the browser supplied. */}
        <Route path="/dashboard" element={<DashboardPage />} />
        {/* Declared before the catch-all. Like the dashboard, it resolves its
            own access state from the server session rather than wrapping the route
            in a client-side guard that could only trust a browser-supplied value. */}
        <Route path="/applications" element={<ApplicationsPage />} />
        {/* The workspace itself, so a refresh or a shared link lands on it. */}
        <Route path="/applications/:applicationId" element={<ApplicationsPage />} />
        {/* The mentor. Like the dashboard and the workspace, it resolves its own
            access state from the server session rather than wrapping the route in
            a client-side guard that could only trust a browser-supplied value. */}
        <Route path="/mentor" element={<MentorPage />} />
        <Route path="/compare" element={<ComparePage />} />
        {/* The applicant journey, behind Suspense because it is code-split.
            The fallback keeps the route's own region quiet rather than
            replacing the page, so the header and footer stay put while the
            chunk arrives.

            Two entries: the bare path for a fresh visit, and the step segment
            so a reader can be sent to one module. JourneyPage reads the segment
            from the router and opens that step, so without the second entry a
            deep link to /timeline lands on the 404 route instead. */}
        <Route
          path="/bangladesh-journey"
          element={
            <Suspense fallback={<JourneyFallback />}>
              <JourneyProvider>
                <JourneyPage />
              </JourneyProvider>
            </Suspense>
          }
        />
        <Route
          path="/bangladesh-journey/:stepId"
          element={
            <Suspense fallback={<JourneyFallback />}>
              <JourneyProvider>
                <JourneyPage />
              </JourneyProvider>
            </Suspense>
          }
        />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/admin/verification" element={<AdminVerificationPage />} />
        <Route path="/admin/scholarships" element={<AdminScholarshipPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App
