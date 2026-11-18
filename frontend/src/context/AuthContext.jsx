import { useEffect, useRef, useState } from 'react'
import { authService } from '../services/authService'
import { AuthContext } from './authContext'

export function AuthProvider({ children }) {
  const [status, setStatus] = useState('checking')
  const [user, setUser] = useState(null)
  const authGenRef = useRef(0)
  const refreshGenRef = useRef(0)

  useEffect(() => {
    let isActive = true
    const gen = authGenRef.current

    async function checkSession() {
      try {
        const session = await authService.checkSession()

        if (!isActive || gen !== authGenRef.current || refreshGenRef.current !== 0) {
          return
        }

        setUser(session?.user ?? null)
        setStatus(session?.user ? 'authenticated' : 'unauthenticated')
      } catch {
        if (isActive && gen === authGenRef.current && refreshGenRef.current === 0) {
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
    const gen = ++authGenRef.current
    try {
      const session = await authService.login(credentials)
      if (gen !== authGenRef.current) return session
      setUser(session?.user ?? null)
      setStatus(session?.user ? 'authenticated' : 'unauthenticated')
      return session
    } catch (error) {
      if (gen === authGenRef.current) {
        setUser(null)
        setStatus('unauthenticated')
      }
      throw error
    }
  }

  async function register(credentials) {
    return authService.register(credentials)
  }

  async function logout() {
    const gen = ++authGenRef.current
    await authService.logout()
    if (gen !== authGenRef.current) return
    setUser(null)
    setStatus('unauthenticated')
  }

  async function refreshSession() {
    const rgen = ++refreshGenRef.current
    const authGenAtStart = authGenRef.current
    try {
      const session = await authService.checkSession()
      if (rgen !== refreshGenRef.current) {
        return session
      }
      if (authGenAtStart !== authGenRef.current) {
        return session
      }
      setUser(session?.user ?? null)
      setStatus(session?.user ? 'authenticated' : 'unauthenticated')
      return session
    } catch {
      if (rgen === refreshGenRef.current && authGenAtStart === authGenRef.current) {
        setUser(null)
        setStatus('unauthenticated')
      }
      return { user: null }
    }
  }

  const value = {
    status,
    user,
    login,
    register,
    logout,
    refreshSession,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
