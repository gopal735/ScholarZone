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

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme
}

export function ThemeProvider({ children }) {
  const initialStoredTheme = getStoredTheme()
  const [theme, setTheme] = useState(() => {
    // Light unless the visitor has explicitly chosen otherwise.
    //
    // This used to follow the operating system, which meant a visitor with a
    // dark desktop silently got a different identity from one with a light
    // desktop. The light direction is the product's face, so it is the default
    // rather than a coin flip on the visitor's OS.
    const initialTheme = initialStoredTheme ?? 'light'
    applyTheme(initialTheme)
    return initialTheme
  })

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  function toggleTheme() {
    const nextTheme = theme === 'dark' ? 'light' : 'dark'
    setTheme(nextTheme)

    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme)
    } catch {
      // The in-memory choice still applies if storage is unavailable.
    }
  }

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>
}
