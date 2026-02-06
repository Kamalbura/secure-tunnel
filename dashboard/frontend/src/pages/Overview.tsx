/**
 * Overview Page v3 — Multi-run KPIs, anomaly highlights, aggressive charts.
 */

import { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useDashboardStore } from '../state/store';
import { RUN_TYPE_COLORS, RUN_TYPE_LABELS, type RunType } from '../types/metrics';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell,
} from 'recharts';

type HealthResponse = { status: string; suites_loaded: number; runs_loaded: number };
type AggregateRow = Record<string, string | number>;

function fmt(v: number | null | undefined, digits = 2): string {
    if (v == null || isNaN(v)) return '—';
    return v.toFixed(digits);
}

export default function Overview() {
    const {
        runs, suites, isLoading, fetchSuites, fetchRuns, clearFilters,
        multiRunOverview, fetchMultiRunOverview, anomalies, fetchSettings,
    } = useDashboardStore();
    const [health, setHealth] = useState<HealthResponse | null>(null);
    const [kemFamilyData, setKemFamilyData] = useState<AggregateRow[]>([]);
    const [aggWarning, setAggWarning] = useState<string | null>(null);

    useEffect(() => {
        clearFilters();
        fetchSuites();
        fetchRuns();
        fetchSettings();
        fetchMultiRunOverview();
        // Anomalies are loaded by App.tsx scoped to latest run — no duplicate fetch here
        fetch('/api/health')
            .then(res => res.json())
            .then(setHealth)
            .catch(() => setHealth(null));
        fetch('/api/aggregate/kem-family')
            .then(res => res.json())
            .then(payload => {
                if (payload?.warning) { setAggWarning(payload.warning); setKemFamilyData([]); }
                else { setAggWarning(null); setKemFamilyData(payload?.data ?? []); }
            })
            .catch(() => { setAggWarning('Aggregation unavailable'); setKemFamilyData([]); });
    }, [fetchSuites, fetchRuns, clearFilters, fetchMultiRunOverview, fetchSettings]);

    const { passRate, failedSuitesCount } = useMemo(() => {
        if (!suites.length) return { passRate: 0, failedSuitesCount: 0 };
        const total = suites.length;
        const passed = suites.filter(s => s.benchmark_pass_fail === 'PASS').length;
        const failed = suites.filter(s => s.benchmark_pass_fail === 'FAIL').length;
        return { passRate: (passed / total) * 100, failedSuitesCount: failed };
    }, [suites]);

    const criticalAnomalies = anomalies.filter(a => a.severity === 'critical').length;

    if (isLoading && runs.length === 0) {
        return <div className="flex items-center justify-center h-64"><div className="text-gray-400">Loading dashboard…</div></div>;
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold text-white">🔬 PQC Benchmark Overview</h1>
                <div className="flex gap-2">
                    <Link to="/settings" className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm text-gray-300 transition-colors">⚙️ Settings</Link>
                    <Link to="/security" className="px-3 py-1.5 bg-red-900/30 hover:bg-red-900/50 border border-red-500/30 rounded text-sm text-red-400 transition-colors">
                        🚨 {criticalAnomalies} Critical
                    </Link>
                </div>
            </div>

            {/* ── Global KPI Cards ── */}
            <div className="grid grid-cols-5 gap-4">
                <div className="card border-l-4 border-l-blue-500">
                    <div className="text-xs text-gray-400 uppercase tracking-wider">Total Suites</div>
                    <div className="text-3xl font-bold text-blue-400">{health?.suites_loaded ?? '—'}</div>
                </div>
                <div className="card border-l-4 border-l-purple-500">
                    <div className="text-xs text-gray-400 uppercase tracking-wider">Benchmark Runs</div>
                    <div className="text-3xl font-bold text-purple-400">{health?.runs_loaded ?? '—'}</div>
                </div>
                <div className="card border-l-4 border-l-green-500">
                    <div className="text-xs text-gray-400 uppercase tracking-wider">Pass Rate</div>
                    <div className="text-3xl font-bold text-green-400">{suites.length > 0 ? `${passRate.toFixed(1)}%` : '—'}</div>
                </div>
                <div className="card border-l-4 border-l-red-500">
                    <div className="text-xs text-gray-400 uppercase tracking-wider">Failed Suites</div>
                    <div className="text-3xl font-bold text-red-400">{suites.length > 0 ? failedSuitesCount : '—'}</div>
                </div>
                <div className="card border-l-4 border-l-yellow-500">
                    <div className="text-xs text-gray-400 uppercase tracking-wider">Anomalies</div>
                    <div className="text-3xl font-bold text-yellow-400">{anomalies.length}</div>
                </div>
            </div>

            {/* ── Multi-Run Comparison Cards ── */}
            {multiRunOverview.length > 0 && (
                <div>
                    <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                        <span>📊</span> Run Comparison
                    </h2>
                    <div className="grid grid-cols-3 gap-4">
                        {multiRunOverview.map(r => {
                            const color = RUN_TYPE_COLORS[r.run_type as RunType] || '#6b7280';
                            return (
                                <div key={r.run_id} className="card" style={{ borderTop: `3px solid ${color}` }}>
                                    <div className="flex items-center gap-2 mb-3">
                                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                                        <span className="text-white font-medium">{r.label}</span>
                                        <span className="text-xs px-1.5 py-0.5 rounded" style={{ color, backgroundColor: color + '22' }}>
                                            {RUN_TYPE_LABELS[r.run_type as RunType] || r.run_type}
                                        </span>
                                    </div>
                                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                                        <span className="text-gray-400">Suites</span>
                                        <span className="text-white font-mono">{r.total_suites}</span>
                                        <span className="text-gray-400">Pass Rate</span>
                                        <span className={`font-mono font-bold ${r.pass_rate >= 95 ? 'text-green-400' : r.pass_rate >= 80 ? 'text-yellow-400' : 'text-red-400'}`}>{r.pass_rate}%</span>
                                        <span className="text-gray-400">Avg Handshake</span>
                                        <span className="text-white font-mono">{fmt(r.avg_handshake_ms)} ms</span>
                                        <span className="text-gray-400">Avg Power</span>
                                        <span className="text-white font-mono">{fmt(r.avg_power_w, 3)} W</span>
                                        <span className="text-gray-400">Total Energy</span>
                                        <span className="text-white font-mono">{fmt(r.total_energy_j, 2)} J</span>
                                        <span className="text-gray-400">Avg Pkt Loss</span>
                                        <span className="text-white font-mono">{fmt(r.avg_packet_loss, 6)}</span>
                                        <span className="text-gray-400">Anomalies</span>
                                        <span className={`font-mono font-bold ${r.anomaly_count > 0 ? 'text-red-400' : 'text-green-400'}`}>{r.anomaly_count}</span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* ── Charts Row 1: Handshake & Power ── */}
            <div className="grid grid-cols-2 gap-6">
                <div className="card">
                    <h3 className="card-header">🔑 Avg Handshake by KEM Family</h3>
                    <div className="h-64">
                        {aggWarning ? <div className="text-gray-400 text-sm">{aggWarning}</div> : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={kemFamilyData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                    <XAxis dataKey="crypto_identity_kem_family" tick={{ fill: '#d1d5db', fontSize: 11 }} />
                                    <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} label={{ value: 'ms', angle: -90, position: 'insideLeft', fill: '#6b7280' }} />
                                    <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }} />
                                    <Bar dataKey="handshake_handshake_total_duration_ms_mean" fill="#3b82f6" name="Avg Handshake (ms)" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>
                <div className="card">
                    <h3 className="card-header">⚡ Avg Power by KEM Family</h3>
                    <div className="h-64">
                        {aggWarning ? <div className="text-gray-400 text-sm">{aggWarning}</div> : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={kemFamilyData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                    <XAxis dataKey="crypto_identity_kem_family" tick={{ fill: '#d1d5db', fontSize: 11 }} />
                                    <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} label={{ value: 'W', angle: -90, position: 'insideLeft', fill: '#6b7280' }} />
                                    <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }} />
                                    <Bar dataKey="power_energy_power_avg_w_mean" fill="#10b981" name="Avg Power (W)" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>
            </div>

            {/* ── Charts Row 2: Goodput & Packet Loss ── */}
            <div className="grid grid-cols-2 gap-6">
                <div className="card">
                    <h3 className="card-header">📡 Avg Goodput by KEM Family</h3>
                    <div className="h-64">
                        {aggWarning ? <div className="text-gray-400 text-sm">{aggWarning}</div> : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={kemFamilyData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                    <XAxis dataKey="crypto_identity_kem_family" tick={{ fill: '#d1d5db', fontSize: 11 }} />
                                    <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} label={{ value: 'Mbps', angle: -90, position: 'insideLeft', fill: '#6b7280' }} />
                                    <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }} />
                                    <Bar dataKey="data_plane_goodput_mbps_mean" fill="#0ea5e9" name="Avg Goodput (Mbps)" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>
                <div className="card">
                    <h3 className="card-header">📉 Avg Packet Loss by KEM Family</h3>
                    <div className="h-64">
                        {aggWarning ? <div className="text-gray-400 text-sm">{aggWarning}</div> : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={kemFamilyData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                    <XAxis dataKey="crypto_identity_kem_family" tick={{ fill: '#d1d5db', fontSize: 11 }} />
                                    <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} label={{ value: 'ratio', angle: -90, position: 'insideLeft', fill: '#6b7280' }} />
                                    <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }} />
                                    <Bar dataKey="data_plane_packet_loss_ratio_mean" fill="#f59e0b" name="Avg Loss Ratio" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>
            </div>

            {/* ── Recent Runs ── */}
            <div className="card">
                <h3 className="card-header">📋 Benchmark Runs</h3>
                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Run ID</th>
                            <th>Start Time</th>
                            <th>GCS</th>
                            <th>Drone</th>
                            <th>Suites</th>
                            <th>Git Commit</th>
                        </tr>
                    </thead>
                    <tbody>
                        {runs.slice(0, 5).map(run => (
                            <tr key={run.run_id}>
                                <td className="font-mono text-blue-400">{run.run_id}</td>
                                <td>{run.run_start_time_wall ? new Date(run.run_start_time_wall).toLocaleString() : '—'}</td>
                                <td>{run.gcs_hostname || '—'}</td>
                                <td>{run.drone_hostname || '—'}</td>
                                <td>{run.suite_count}</td>
                                <td className="font-mono text-xs">{run.git_commit_hash?.slice(0, 8) || '—'}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* ── Quick Navigation ── */}
            <div className="flex flex-wrap gap-3">
                <Link to="/suites" className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-white text-sm font-medium transition-colors">Browse All Suites →</Link>
                <Link to="/multi-run" className="px-4 py-2 bg-purple-600 hover:bg-purple-500 rounded text-white text-sm font-medium transition-colors">Multi-Run Compare →</Link>
                <Link to="/security" className="px-4 py-2 bg-red-600 hover:bg-red-500 rounded text-white text-sm font-medium transition-colors">Security Impact →</Link>
                <Link to="/latency" className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded text-white text-sm font-medium transition-colors">Latency Analysis →</Link>
                <Link to="/buckets" className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white text-sm font-medium transition-colors">Bucket Comparison →</Link>
            </div>
        </div>
    );
}
