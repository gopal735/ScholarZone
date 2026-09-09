import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { useNavigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext.jsx'
import { CompareProvider } from './context/CompareContext.jsx'
import { SavedScholarshipsProvider } from './context/SavedScholarshipsContext.jsx'
import { ThemeProvider } from './context/ThemeContext.jsx'
import './index.css'
import App from './App.jsx'
import './theme.css'

function RedirectHandler() {
  const navigate = useNavigate()
  const redirect = sessionStorage.getItem('redirect')
  if (redirect) {
    sessionStorage.removeItem('redirect')
    navigate(redirect, { replace: true })
  }
  return null
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <SavedScholarshipsProvider>
          <CompareProvider>
            <BrowserRouter>
              <RedirectHandler />
              <App />
            </BrowserRouter>
          </CompareProvider>
        </SavedScholarshipsProvider>
      </AuthProvider>
    </ThemeProvider>
  </StrictMode>,
)
