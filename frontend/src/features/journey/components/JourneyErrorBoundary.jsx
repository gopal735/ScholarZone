import { Component } from 'react'

/**
 * Route-level error boundary for the journey page.
 *
 * A throw inside one of the seven modules must not take the rest of ScholarZone
 * down with it. The boundary renders a statement and a recovery action, and it
 * deliberately does not touch stored data: an error in rendering is not evidence
 * that the student's progress is bad, and discarding it would destroy work
 * because of a display fault.
 */
export class JourneyErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  handleRetry = () => {
    this.setState({ error: null })
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className="jerror" role="alert">
        <h1 className="jerror__title">Something went wrong</h1>
        <p className="jerror__body">
          The journey workspace could not be displayed. Your saved data has not been changed.
        </p>
        <div className="jerror__actions">
          <button type="button" className="jbtn jbtn--primary" onClick={this.handleRetry}>
            Try this step again
          </button>
          <button type="button" className="jbtn jbtn--quiet" onClick={() => window.location.reload()}>
            Reload the page
          </button>
        </div>
      </div>
    )
  }
}

export default JourneyErrorBoundary
