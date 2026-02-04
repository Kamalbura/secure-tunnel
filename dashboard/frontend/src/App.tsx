/**
 * PQC Benchmark Dashboard - Main App Component
 */

import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { useEffect, Component, type ErrorInfo, type ReactNode } from 'react';
import { useDashboardStore } from './state/store';
import Overview from './pages/Overview';
import SuiteExplorer from './pages/SuiteExplorer';
import SuiteDetail from './pages/SuiteDetail';
import ComparisonView from './pages/ComparisonView';
import BucketComparison from './pages/BucketComparison';
import PowerAnalysis from './pages/PowerAnalysis';
import IntegrityMonitor from './pages/IntegrityMonitor';
import MetricSemantics from './pages/MetricSemantics';

// Navigation component
function Navigation() {
    const location = useLocation();

    const navItems = [
        { path: '/', label: 'Overview' },
        { path: '/suites', label: 'Suite Explorer' },
        { path: '/buckets', label: 'Buckets' },
        { path: '/compare', label: 'Comparison' },
        { path: '/power', label: 'Power Analysis' },
        { path: '/integrity', label: 'Integrity Monitor' },
        { path: '/semantics', label: 'Metric Semantics' },
    ];

    return (
        <nav className="bg-gray-800 border-b border-gray-700">
            <div className="max-w-7xl mx-auto px-4">
                <div className="flex items-center justify-between h-16">
                    <div className="flex items-center gap-2">
                        <div className="text-xl font-bold text-blue-400">PQC</div>
                        <div className="text-gray-500">Benchmark Dashboard</div>
                    </div>
                    <div className="flex gap-1">
                        {navItems.map(item => (
                            <Link
                                key={item.path}
                                to={item.path}
                                className={`nav-link ${location.pathname === item.path ? 'active' : ''}`}
                            >
                                {item.label}
                            </Link>
                        ))}
                    </div>
                </div>
            </div>
        </nav>
    );
}

// Disclaimer banner
function DisclaimerBanner() {
    return (
        <div className="max-w-7xl mx-auto px-4 mt-4">
            <div className="disclaimer-banner flex items-center gap-2">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <span><strong>No causal inference implied.</strong> Observational data only. Missing data shown explicitly.</span>
            </div>
        </div>
    );
}

// Error display
function ErrorDisplay() {
    const error = useDashboardStore(state => state.error);
    const clearError = useDashboardStore(state => state.clearError);

    if (!error) return null;

    return (
        <div className="max-w-7xl mx-auto px-4 mt-4">
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 flex items-center justify-between">
                <span className="text-red-400">{error}</span>
                <button
                    onClick={clearError}
                    className="text-red-400 hover:text-red-300"
                >
                    ✕
                </button>
            </div>
        </div>
    );
}

// Error Boundary
class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
    constructor(props: { children: ReactNode }) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error) {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("Uncaught error:", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="p-8 text-center text-gray-300">
                    <h1 className="text-xl font-bold text-red-500 mb-4">Something went wrong</h1>
                    <div className="text-left bg-gray-800 p-4 rounded border border-red-900/50 mb-4 overflow-auto max-w-3xl mx-auto font-mono text-xs">
                        {this.state.error?.toString()}
                    </div>
                    <button
                        className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-500 text-white font-medium transition-colors"
                        onClick={() => window.location.reload()}
                    >
                        Reload Page
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}

// Main App
function App() {
    const fetchFilters = useDashboardStore(state => state.fetchFilters);

    useEffect(() => {
        fetchFilters();
    }, [fetchFilters]);

    return (
        <Router>
            <div className="min-h-screen bg-gray-900">
                <Navigation />
                <DisclaimerBanner />
                <ErrorDisplay />
                <main className="max-w-7xl mx-auto px-4 py-6">
                    <ErrorBoundary>
                        <Routes>
                            <Route path="/" element={<Overview />} />
                            <Route path="/suites" element={<SuiteExplorer />} />
                            <Route path="/suite/:suiteKey" element={<SuiteDetail />} />
                            <Route path="/buckets" element={<BucketComparison />} />
                            <Route path="/compare" element={<ComparisonView />} />
                            <Route path="/power" element={<PowerAnalysis />} />
                            <Route path="/integrity" element={<IntegrityMonitor />} />
                            <Route path="/semantics" element={<MetricSemantics />} />
                        </Routes>
                    </ErrorBoundary>
                </main>
            </div>
        </Router>
    );
}

export default App;
