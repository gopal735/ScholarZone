import { Link } from 'react-router-dom'
import { useEffect } from 'react'
import './NotFoundPage.css'

export default function NotFoundPage() {
  useEffect(() => {
    document.querySelectorAll('[data-sz-seo]').forEach(el => el.remove())
    
    const meta = document.createElement('meta')
    meta.name = 'robots'
    meta.content = 'noindex, nofollow'
    meta.setAttribute('data-sz-seo', 'true')
    document.head.appendChild(meta)
    
    return () => {
      document.querySelectorAll('[data-sz-seo]').forEach(el => el.remove())
    }
  }, [])

  return (
    <section className="not-found">
      <span className="not-found__code">404</span>
      <p className="not-found__eyebrow">Page unavailable</p>
      <h1>We could not find that page.</h1>
      <p>The link may be outdated, or the page may have moved.</p>
      <Link to="/" className="not-found__action">
        Return home <span aria-hidden="true">&rarr;</span>
      </Link>
    </section>
  )
}
