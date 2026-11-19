/**
 * Error boundary: an unexpected render crash shows a clean recovery screen
 * (with a reload action) instead of a blank page. Catches render-time errors
 * in the component tree; API errors are handled per-panel as usual.
 */

import { Component } from 'react'

import type { ErrorInfo, ReactNode } from 'react'

interface ErrorBoundaryProps {
    children: ReactNode
}

interface ErrorBoundaryState {
    error: Error | null
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    state: ErrorBoundaryState = { error: null }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { error }
    }

    componentDidCatch(error: Error, info: ErrorInfo): void {
        // Console only — no external reporting exists (D5), and no secrets ever leave.
        console.error('UI render error:', error, info.componentStack)
    }

    render(): ReactNode {
        if (this.state.error !== null) {
            return (
                <div className="workspace" role="alert">
                    <section className="panel">
                        <h2>Something went wrong</h2>
                        <p className="muted">
                            The workspace hit an unexpected rendering error. Your engines are
                            unaffected — reload the page to continue.
                        </p>
                        <p>
                            <code>{this.state.error.message}</code>
                        </p>
                        <button type="button" onClick={() => window.location.reload()}>
                            Reload workspace
                        </button>
                    </section>
                </div>
            )
        }
        return this.props.children
    }
}
