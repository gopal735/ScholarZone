import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext.jsx'
import { CompareProvider } from './context/CompareContext.jsx'
import { SavedScholarshipsProvider } from './context/SavedScholarshipsContext.jsx'
import { ThemeProvider } from './context/ThemeContext.jsx'
import { RedirectHandler } from './components/RedirectHandler.jsx'
import { AppErrorBoundary } from './components/AppErrorBoundary.jsx'
import './index.css'
import App from './App.jsx'
import './theme.css'
// Imported last so the density, provenance and motion layer wins over the
// component defaults without every component having to know about it.
import './Ledger.css'
// Imported after Ledger.css because it corrects the density layer rather than
// competing with it: one container, one type floor, one touch-target floor and
// one wrapping policy for every page, applied once.
import './styles/responsive.css'

// The router has to agree with where the app is actually served. Vite sets
// BASE_URL from the same `base` that rewrites every asset URL, so reading it
// here keeps the two from drifting: '/ScholarZone/' on GitHub Pages and '/' on a
// root domain.
//
// It used to be the literal string '/ScholarZone'. On the Vercel root domain
// that told the router it lived one directory deep, so no route matched and the
// page rendered nothing at all. Hardcoding the GitHub Pages path is what made
// this a second, separate blank-screen bug after the asset base was fixed.
const basename = (import.meta.env.BASE_URL || '/').replace(/\/$/, '') || '/'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AppErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <SavedScholarshipsProvider>
            <CompareProvider>
              <BrowserRouter basename={basename}>
                <RedirectHandler />
                <App />
              </BrowserRouter>
            </CompareProvider>
          </SavedScholarshipsProvider>
        </AuthProvider>
      </ThemeProvider>
    </AppErrorBoundary>
  </StrictMode>,
)