import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

export function RedirectHandler() {
  const navigate = useNavigate()

  useEffect(() => {
    const redirect = sessionStorage.getItem('redirect')
    if (redirect) {
      sessionStorage.removeItem('redirect')
      navigate(redirect, { replace: true })
    }
  }, [navigate])

  return null
}