import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import ScholarshipsPage from './pages/ScholarshipsPage'
import MatchPage from './pages/MatchPage'
import ScholarshipDetailsPage from './pages/ScholarshipDetailsPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import SavedScholarshipsPage from './pages/SavedScholarshipsPage'
import ComparePage from './pages/ComparePage'
import DashboardPage from './pages/DashboardPage'
import AdminPage from './pages/AdminPage'
import CountryPage from './pages/CountryPage'
import NotFoundPage from './pages/NotFoundPage'
import { useScrollReveal } from './hooks/useScrollReveal'
import './App.css'

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
        {/* Declared before the catch-all. The dashboard resolves its own access
            state from the server session rather than wrapping the route in a
            client-side guard, because the guard would only be able to trust a
            value the browser supplied. */}
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App
