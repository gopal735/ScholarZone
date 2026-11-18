import { useEffect, useRef, useState } from 'react'
import { authService } from '../services/authService'
import { AuthContext } from './authContext'

export function AuthProvider({ children }) {
  const [status, setStatus] = useState('checking')
  const [user, setUser] = useState(null)
  const mutationRef = useRef(0)
  const sessionRef = useRef(0)

  useEffect(() => {
    let isActive = true
    const mutationGen = mutationRef.current
    const sessionGen = ++sessionRef.current

    async function checkSession() {
      try {
        const session = await authService.checkSession()

        if (!isActive || mutationGen !== mutationRef.current || sessionGen !== sessionRef.current) {
          return
        }

        setUser(session?.user ?? null)
        setStatus(session?.user ? 'authenticated' : 'unauthenticated')
      } catch {
        if (isActive && mutationGen === mutationRef.current && sessionGen === sessionRef.current) {
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
    const mutationGen = ++mutationRef.current
    try {
      const session = await authService.login(credentials)
      if (mutationGen !== mutationRef.current) return session
      setUser(session?.user ?? null)
      setStatus(session?.user ? 'authenticated' : 'unauthenticated')
      return session
    } catch (error) {
      if (mutationGen === mutationRef.current) {
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
    const mutationGen = ++mutationRef.current
    await authService.logout()
    if (mutationGen !== mutationRef.current) return
    setUser(null)
    setStatus('unauthenticated')
  }

  async function refreshSession() {
    const mutationGen = mutationRef.current
    const sessionGen = ++sessionRef.current
    try {
      const session = await authService.checkSession()
      if (mutationGen !== mutationRef.current || sessionGen !== sessionRef.current) {
        return session
      }
      setUser(session?.user ?? null)
      setStatus(session?.user ? 'authenticated' : 'unauthenticated')
      return session
    } catch {
      if (mutationGen === mutationRef.current && sessionGen === sessionRef.current) {
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
