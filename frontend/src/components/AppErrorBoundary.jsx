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