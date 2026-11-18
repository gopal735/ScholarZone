import { useEffect, useRef, useState } from 'react'
import { authService } from '../services/authService'
import { AuthContext } from './authContext'

export function AuthProvider({ children }) {
  const [status, setStatus] = useState('checking')
  const [user, setUser] = useState(null)
  const generationRef = useRef(0)

  useEffect(() => {
    let isActive = true
    const gen = generationRef.current

    async function checkSession() {
      try {
        const session = await authService.checkSession()

        if (!isActive || gen !== generationRef.current) {
          return
        }

        setUser(session?.user ?? null)
        setStatus(session?.user ? 'authenticated' : 'unauthenticated')
      } catch {
        if (isActive && gen === generationRef.current) {
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
    const gen = ++generationRef.current
    try {
      const session = await authService.login(credentials)
      if (gen !== generationRef.current) return session
      setUser(session?.user ?? null)
      setStatus(session?.user ? 'authenticated' : 'unauthenticated')
      return session
    } catch (error) {
      if (gen === generationRef.current) {
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
    const gen = ++generationRef.current
    await authService.logout()
    if (gen !== generationRef.current) return
    setUser(null)
    setStatus('unauthenticated')
  }

  async function refreshSession() {
    const gen = ++generationRef.current
    try {
      const session = await authService.checkSession()
      if (gen !== generationRef.current) {
        return session
      }
      setUser(session?.user ?? null)
      setStatus(session?.user ? 'authenticated' : 'unauthenticated')
      return session
    } catch {
      if (gen === generationRef.current) {
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
