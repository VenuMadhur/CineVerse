import { Component } from 'react';
import { FiAlertTriangle } from 'react-icons/fi';

/**
 * Catches unexpected render-time errors anywhere below it in the tree
 * and shows a friendly fallback instead of a blank white screen. This
 * is separate from per-page ErrorState (which handles expected API
 * errors) -- this is the last-resort safety net for genuine bugs.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('CineVerse crashed:', error, info);
  }

  handleReload = () => {
    this.setState({ hasError: false });
    window.location.assign('/dashboard');
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-[#0F172A] px-4 text-center">
          <FiAlertTriangle className="mb-4 text-[#E50914]" size={48} />
          <h1 className="text-2xl font-bold text-white">Something went wrong</h1>
          <p className="mt-2 max-w-sm text-slate-400">
            CineVerse hit an unexpected error. Try heading back to your dashboard.
          </p>
          <button onClick={this.handleReload} className="btn-primary mt-6">
            Back to Dashboard
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
