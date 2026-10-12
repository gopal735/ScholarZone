import { Component } from 'react'

/**
 * Last line of defence against a white screen.
 *
 * Without this, any throw during render unmounts the whole tree and the browser
 * is left with an empty #root: the page is blank with nothing in the console to
 * explain it, which is exactly the failure this component exists to prevent.
 * A failed render now shows what happened and offers a way out.
 */
export class AppErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // Kept visible rather than swallowed: a render crash that only logs to a
    // console nobody opens is indistinguishable from a blank page.
    console.error('ScholarZone failed to render:', error, info?.componentStack)
  }

  render() {
    if (!this.state.error) {
      return this.props.children
    }
    return (
      <div
        role="alert"
        style={{
          minHeight: '60vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '1rem',
          padding: '2rem',
          textAlign: 'center',
          fontFamily: 'Inter, system-ui, sans-serif',
        }}
      >
        <h1 style={{ fontSize: '1.5rem', margin: 0 }}>
          ScholarZone could not load this page
        </h1>
        <p style={{ maxWidth: '32rem', margin: 0, color: '#555' }}>
          Something in the page failed to render. Reloading usually clears it. If it keeps
          happening, the details are in your browser console.
        </p>
        <pre
          style={{
            maxWidth: '40rem',
            overflowX: 'auto',
            padding: '0.75rem',
            background: '#f5f5f5',
            borderRadius: '6px',
            fontSize: '0.8rem',
            textAlign: 'left',
          }}
        >
          {String(this.state.error?.message || this.state.error)}
        </pre>
        <button
          type="button"
          onClick={() => window.location.reload()}
          style={{
            padding: '0.6rem 1.25rem',
            borderRadius: '6px',
            border: '1px solid #ccc',
            background: '#fff',
            cursor: 'pointer',
            font: 'inherit',
          }}
        >
          Reload
        </button>
      </div>
    )
  }
}

/**
 * The same guard, one level down: around whatever a route renders.
 *
 * The app boundary above wraps the whole tree, so a throw inside one route
 * takes the header, the navigation and the footer with it and leaves a single
 * full-page panel. This one replaces only the route's own content, so the
 * shell stays up, the user can still navigate, and "Try again" remounts the
 * route — an in-place retry instead of a reload that throws away the session.
 *
 * Inline styles rather than a stylesheet class: a stylesheet that failed to
 * load is one of the things this boundary has to survive.
 */
export class RouteErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null, attempt: 0 }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('ScholarZone could not render this section:', error, info?.componentStack)
  }

  render() {
    if (!this.state.error) {
      // `attempt` is only read to force a remount of the children after a
      // failure: React treats a changed key as a new subtree.
      return <div key={`ok-${this.state.attempt}`} style={{ display: 'contents' }}>{this.props.children}</div>
    }

    return (
      <div
        role="alert"
        data-testid="route-error"
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem',
          padding: '1.5rem',
          border: '1px solid rgba(20, 19, 15, 0.18)',
          borderRadius: '4px',
          background: 'var(--surface-raised, #fff)',
          color: 'var(--text-primary, #14130f)',
          fontFamily: 'Inter, system-ui, sans-serif',
        }}
      >
        <h1 style={{ fontSize: '1.25rem', margin: 0 }}>This section could not be displayed</h1>
        <p style={{ margin: 0, maxWidth: '52ch', color: 'var(--text-secondary, #24221c)' }}>
          Something in it failed to render, so it has been left out rather than left blank. The
          rest of the page still works, and you can try the section again.
        </p>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => this.setState((state) => ({ error: null, attempt: state.attempt + 1 }))}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: '2px',
              border: '1px solid var(--accent, #1b3a5c)',
              background: 'var(--accent, #1b3a5c)',
              color: '#fff',
              cursor: 'pointer',
              font: 'inherit',
            }}
          >
            Try again
          </button>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: '2px',
              border: '1px solid var(--border-strong, rgba(20, 19, 15, 0.24))',
              background: 'transparent',
              color: 'inherit',
              cursor: 'pointer',
              font: 'inherit',
            }}
          >
            Reload the page
          </button>
        </div>
      </div>
    )
  }
}