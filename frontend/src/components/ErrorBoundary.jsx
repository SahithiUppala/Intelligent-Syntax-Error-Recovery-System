import { Component } from 'react'

/**
 * Catches render errors so the IDE shell stays usable.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('UI error boundary caught:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="app-shell">
          <div className="banner banner-danger">
            <strong>Something went wrong in the UI.</strong>
            <p style={{ margin: '0.5rem 0 0' }}>
              {this.state.error.message || String(this.state.error)}
            </p>
            <button
              type="button"
              className="btn"
              style={{ marginTop: '0.75rem' }}
              onClick={() => this.setState({ error: null })}
            >
              Try to recover
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
