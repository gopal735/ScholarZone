import { useEffect, useState } from 'react'
import { ThemeContext } from './themeContext'

const THEME_STORAGE_KEY = 'scholarzone.theme.v1'

function getStoredTheme() {
  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)
    return storedTheme === 'light' || storedTheme === 'dark' ? storedTheme : null
  } catch {
    return null
  }
}

function getSystemTheme() {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme
}

export function ThemeProvider({ children }) {
  const initialStoredTheme = getStoredTheme()
  const [theme, setTheme] = useState(() => {
    const initialTheme = initialStoredTheme ?? getSystemTheme()
    applyTheme(initialTheme)
    return initialTheme
  })
  const [hasExplicitPreference, setHasExplicitPreference] = useState(Boolean(initialStoredTheme))

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  useEffect(() => {
    if (hasExplicitPreference || !window.matchMedia) {
      return undefined
    }

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const syncSystemTheme = (event) => setTheme(event.matches ? 'dark' : 'light')

    mediaQuery.addEventListener('change', syncSystemTheme)
    return () => mediaQuery.removeEventListener('change', syncSystemTheme)
  }, [hasExplicitPreference])

  function toggleTheme() {
    const nextTheme = theme === 'dark' ? 'light' : 'dark'
    setTheme(nextTheme)
    setHasExplicitPreference(true)

    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme)
    } catch {
      // The in-memory choice still applies if storage is unavailable.
    }
  }

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>
}
