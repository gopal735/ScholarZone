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
const ItalyDsuGuidePage = lazy(() => import('./pages/ItalyDsuGuidePage'))
const StudyPlannerPage = lazy(() => import('./pages/StudyPlannerPage'))
const MentorConversationsPage = lazy(() => import('./pages/MentorConversationsPage'))

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/countries" element={<CountryPage />} />
        <Route path="/scholarships" element={<ScholarshipsPage />} />
        <Route path="/scholarships/italy-dsu" element={<ItalyDsuGuidePage />} />
        <Route path="/match" element={<MatchPage />} />
        <Route path="/scholarships/:id" element={<ScholarshipDetailsPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/saved" element={<SavedScholarshipsPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/applications" element={<ApplicationsPage />} />
        <Route path="/applications/:applicationId" element={<ApplicationsPage />} />
        <Route path="/study-planner" element={<StudyPlannerPage />} />
        <Route path="/assistant" element={<UnifiedAIPage />} />
        <Route path="/mentor" element={<Navigate to="/assistant" replace />} />
        <Route path="/mentor/conversations" element={<MentorConversationsPage />} />
        <Route path="/compare" element={<ComparePage />} />
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
        <Route path="/journey" element={<Navigate to="/bangladesh-journey" replace />} />
        <Route path="/journey/*" element={<Navigate to="/bangladesh-journey" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App