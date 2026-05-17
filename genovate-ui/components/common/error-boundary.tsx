'use client';

import * as React from 'react';

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * React error boundary used by the dashboard layout to contain client-side
 * failures and present a recoverable UI rather than a blank page.
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error('Genovate UI error boundary:', error, info);
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div className="m-6 rounded-lg border border-destructive/40 bg-destructive/5 p-6 text-sm">
            <p className="font-semibold text-destructive">Something went wrong.</p>
            <p className="mt-1 text-muted-foreground">{this.state.error.message}</p>
            <button
              type="button"
              onClick={this.reset}
              className="mt-3 rounded-md border px-3 py-1 text-xs hover:bg-accent"
            >
              Try again
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
