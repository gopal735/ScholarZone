import { describe, expect, it, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useAuth } from '../hooks/useAuth'
import { AuthProvider } from './AuthContext.jsx'
import { authService } from '../services/authService'

vi.mock('../services/authService', () => ({
  authService: {
    checkSession: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
  },
}))

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('AuthContext race safety', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authService.checkSession.mockResolvedValue({ user: null })
  })

  it('settles rejected login during initial session check', async () => {
    const initial = deferred()
    authService.checkSession.mockReturnValueOnce(initial.promise)
    authService.login.mockRejectedValue(new Error('bad credentials'))

    const { result } = renderHook(() => useAuth(), { wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider> })

    expect(result.current.status).toBe('checking')

    await act(async () => {
      await expect(result.current.login({ email: 'a', password: 'b' })).rejects.toThrow('bad credentials')
    })

    await waitFor(() => expect(result.current.status).toBe('unauthenticated'))
    expect(result.current.user).toBeNull()

    act(() => {
      initial.resolve({ user: { id: 99 } })
    })

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(result.current.status).toBe('unauthenticated')
    expect(result.current.user).toBeNull()
  })

  it('overlapping refreshSession requests settle to latest result', async () => {
    const first = deferred()
    const second = deferred()
    authService.checkSession
      .mockResolvedValueOnce({ user: null })
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)

    const { result } = renderHook(() => useAuth(), { wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider> })

    await waitFor(() => expect(result.current.status).toBe('unauthenticated'))

    act(() => {
      void result.current.refreshSession()
      void result.current.refreshSession()
    })

    // Resolve in reverse completion order: second (latest) first, then first (stale).
    act(() => {
      second.resolve({ user: { id: 2 } })
    })
    await waitFor(() => expect(result.current.user?.id).toBe(2))
    expect(result.current.status).toBe('authenticated')

    act(() => {
      first.resolve({ user: { id: 1 } })
    })
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(result.current.user?.id).toBe(2)
    expect(result.current.status).toBe('authenticated')
  })

  it('logout during in-flight refresh prevents stale auth restore', async () => {
    const refresh = deferred()
    authService.checkSession
      .mockResolvedValueOnce({ user: null })
      .mockReturnValueOnce(refresh.promise)
    authService.logout.mockResolvedValue(undefined)

    const { result } = renderHook(() => useAuth(), { wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider> })
    await waitFor(() => expect(result.current.status).toBe('unauthenticated'))

    act(() => {
      void result.current.refreshSession()
    })

    await act(async () => {
      await result.current.logout()
    })

    expect(result.current.status).toBe('unauthenticated')
    expect(result.current.user).toBeNull()

    act(() => {
      refresh.resolve({ user: { id: 7 } })
    })

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(result.current.status).toBe('unauthenticated')
    expect(result.current.user).toBeNull()
  })
})
