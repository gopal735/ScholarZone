import { useEffect, useState } from 'react'
import { authService } from '../services/authService'
import { AuthContext } from './authContext'

export function AuthProvider({ children }) {
  const [status, setStatus] = useState('checking')
  const [user, setUser] = useState(null)

  useEffect(() => {
    let isActive = true

    async function checkSession() {
      try {
        const session = await authService.checkSession()

        if (!isActive) {
          return
        }

        setUser(session?.user ?? null)
        setStatus(session?.user ? 'authenticated' : 'unauthenticated')
      } catch {
        if (isActive) {
          setUser(null)
          setStatus('unauthenticated')
        }
      }
    }

    checkSession()

    return () => {
      isActive = false
    }
  }, [])

  async function login(credentials) {
    const session = await authService.login(credentials)
    setUser(session?.user ?? null)
    setStatus(session?.user ? 'authenticated' : 'unauthenticated')
    return session
  }

  async function register(credentials) {
    return authService.register(credentials)
  }

  async function logout() {
    await authService.logout()
    setUser(null)
    setStatus('unauthenticated')
  }

  const value = {
    status,
    user,
    login,
    register,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
