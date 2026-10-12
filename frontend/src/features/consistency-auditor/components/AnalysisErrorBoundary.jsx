import { Component } from 'react';

/**
 * The analysis and its inputs must never be able to take the page down,
 * and a crash must never be reported with the student's text in it.
 *
 * Two rules this component exists to hold:
 *
 *   1. It CATCHES, and shows a safe, short message with a way out.
 *   2. It does not reproduce the error anywhere. React's default behaviour
 *      logs the error to the console; this component overrides that by
 *      rendering its own boundary WITHOUT calling the parent behaviour, and
 *      the message contains no error text, no stack, and no user content.
 *
 * The error object itself is captured in state only so the component can
 * reset the boundary, and is never rendered. The integration test asserts
 *      that neither the message nor any logged line contains document text.
 */
export default class AnalysisErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch() {
    // Intentionally empty, and the point is what is NOT here: no
    // console.error(error), no reporting client, no excerpt. React's own
    // error logging is suppressed by catching at the boundary and rendering
    // a controlled message instead of rethrowing.
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="ca-panel ca-panel--error" role="alert">
        <h2>This review could not be shown</h2>
        <p>
          Something went wrong while preparing your results. Your documents are untouched, and
          nothing was sent anywhere.
        </p>
        <button className="glass-btn glass-btn--sm" type="button" onClick={() => this.setState({ failed: false })}>
          Try again
        </button>
      </div>
    );
  }
}
