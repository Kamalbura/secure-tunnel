/**
 * Zustand store for dashboard state management.
 */

import { create } from 'zustand';
import type { SuiteSummary, ComprehensiveSuiteMetrics, FiltersResponse, RunSummary } from '../types/metrics';

// =============================================================================
// API FUNCTIONS
// =============================================================================

const API_BASE = '/api';

async function fetchJson<T>(url: string): Promise<T> {
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error(`API error: ${res.status} ${res.statusText}`);
    }
    return res.json();
}

// =============================================================================
// STORE TYPES
// =============================================================================

interface DashboardState {
    // Data
    suites: SuiteSummary[];
    runs: RunSummary[];
    selectedSuite: ComprehensiveSuiteMetrics | null;
    comparisonSuiteA: ComprehensiveSuiteMetrics | null;
    comparisonSuiteB: ComprehensiveSuiteMetrics | null;
    filters: FiltersResponse | null;

    // UI State
    isLoading: boolean;
    error: string | null;

    // Filter State
    selectedKemFamily: string | null;
    selectedSigFamily: string | null;
    selectedAead: string | null;
    selectedNistLevel: string | null;
    selectedRunId: string | null;

    // Baseline
    baselineSuiteKey: string | null;

    // Actions
    fetchSuites: () => Promise<void>;
    fetchRuns: () => Promise<void>;
    fetchFilters: () => Promise<void>;
    fetchSuiteDetail: (suiteKey: string) => Promise<void>;
    fetchComparison: (suiteKeyA: string, suiteKeyB: string) => Promise<void>;
    setFilter: (key: keyof Pick<DashboardState, 'selectedKemFamily' | 'selectedSigFamily' | 'selectedAead' | 'selectedNistLevel' | 'selectedRunId'>, value: string | null) => void;
    clearFilters: () => void;
    setBaseline: (suiteKey: string | null) => void;
    clearError: () => void;
}

// =============================================================================
// STORE
// =============================================================================

export const useDashboardStore = create<DashboardState>((set, get) => ({
    // Initial Data
    suites: [],
    runs: [],
    selectedSuite: null,
    comparisonSuiteA: null,
    comparisonSuiteB: null,
    filters: null,

    // Initial UI State
    isLoading: false,
    error: null,

    // Initial Filters
    selectedKemFamily: null,
    selectedSigFamily: null,
    selectedAead: null,
    selectedNistLevel: null,
    selectedRunId: null,

    // Baseline
    baselineSuiteKey: null,

    // Actions
    fetchSuites: async () => {
        set({ isLoading: true, error: null });
        try {
            const state = get();
            const params = new URLSearchParams();
            if (state.selectedKemFamily) params.set('kem_family', state.selectedKemFamily);
            if (state.selectedSigFamily) params.set('sig_family', state.selectedSigFamily);
            if (state.selectedAead) params.set('aead', state.selectedAead);
            if (state.selectedNistLevel) params.set('nist_level', state.selectedNistLevel);
            if (state.selectedRunId) params.set('run_id', state.selectedRunId);

            const url = `${API_BASE}/suites${params.toString() ? '?' + params.toString() : ''}`;
            const suites = await fetchJson<SuiteSummary[]>(url);
            set({ suites, isLoading: false });
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Failed to fetch suites', isLoading: false });
        }
    },

    fetchRuns: async () => {
        set({ isLoading: true, error: null });
        try {
            const runs = await fetchJson<RunSummary[]>(`${API_BASE}/runs`);
            set({ runs, isLoading: false });
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Failed to fetch runs', isLoading: false });
        }
    },

    fetchFilters: async () => {
        try {
            const filters = await fetchJson<FiltersResponse>(`${API_BASE}/suites/filters`);
            set({ filters });
        } catch (err) {
            console.error('Failed to fetch filters:', err);
        }
    },

    fetchSuiteDetail: async (suiteKey: string) => {
        set({ isLoading: true, error: null });
        try {
            const suite = await fetchJson<ComprehensiveSuiteMetrics>(`${API_BASE}/suite/${encodeURIComponent(suiteKey)}`);
            set({ selectedSuite: suite, isLoading: false });
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Failed to fetch suite', isLoading: false });
        }
    },

    fetchComparison: async (suiteKeyA: string, suiteKeyB: string) => {
        set({ isLoading: true, error: null });
        try {
            const [suiteA, suiteB] = await Promise.all([
                fetchJson<ComprehensiveSuiteMetrics>(`${API_BASE}/suite/${encodeURIComponent(suiteKeyA)}`),
                fetchJson<ComprehensiveSuiteMetrics>(`${API_BASE}/suite/${encodeURIComponent(suiteKeyB)}`)
            ]);
            set({ comparisonSuiteA: suiteA, comparisonSuiteB: suiteB, isLoading: false });
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Failed to fetch comparison', isLoading: false });
        }
    },

    setFilter: (key, value) => {
        set({ [key]: value } as Partial<DashboardState>);
    },

    clearFilters: () => {
        set({
            selectedKemFamily: null,
            selectedSigFamily: null,
            selectedAead: null,
            selectedNistLevel: null,
            selectedRunId: null,
        });
    },

    setBaseline: (suiteKey) => {
        set({ baselineSuiteKey: suiteKey });
    },

    clearError: () => {
        set({ error: null });
    },
}));
