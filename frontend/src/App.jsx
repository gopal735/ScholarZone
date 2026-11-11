import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import './App.css'

const ScholarshipsPage = lazy(() => import('./pages/ScholarshipsPage'))
const MatchPage = lazy(() => import('./pages/MatchPage'))
const ScholarshipDetailsPage = lazy(() => import('./pages/ScholarshipDetailsPage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const SavedScholarshipsPage = lazy(() => import('./pages/SavedScholarshipsPage'))
const ComparePage = lazy(() => import('./pages/ComparePage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ApplicationsPage = lazy(() => import('./pages/ApplicationsPage'))
const CountryPage = lazy(() => import('./pages/CountryPage'))
const UnifiedAIPage = lazy(() => import('./pages/UnifiedAIPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))
const BangladeshJourneyPage = lazy(() => import('./features/journey/components/JourneyPage'))
const JourneyRoutes = lazy(() => import('./features/journey/components/JourneyRoutes'))

function App() {
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
        {/* Unified AI Assistant - merges Mentor and AI Assistant */}
        <Route path="/assistant" element={<UnifiedAIPage />} />
        {/* Redirect legacy /mentor to /assistant */}
        <Route path="/mentor" element={<Navigate to="/assistant" replace />} />
        <Route path="/compare" element={<ComparePage />} />
        {/* Bangladesh Applicant Journey - shared JourneyProvider via parent route with Outlet */}
        <Route
          element={
            <Suspense fallback={<div className="journey-loading" role="status" aria-live="polite">Loading journey…</div>}>
              <JourneyRoutes />
            </Suspense>
          }
        >
          <Route index path="/bangladesh-journey" element={<BangladeshJourneyPage />} />
          <Route path="/bangladesh-journey/:stepId" element={<BangladeshJourneyPage />} />
        </Route>
        {/* Legacy alias redirect */}
        <Route path="/journey" element={<Navigate to="/bangladesh-journey" replace />} />
        <Route path="/journey/*" element={<Navigate to="/bangladesh-journey" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App