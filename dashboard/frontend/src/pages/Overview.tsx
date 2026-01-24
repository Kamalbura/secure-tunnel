/**
 * Overview Page - Dashboard summary with key metrics
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useDashboardStore } from '../state/store';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    LineChart, Line, Legend
} from 'recharts';

type HealthResponse = { status: string; suites_loaded: number; runs_loaded: number };
type AggregateRow = Record<string, string | number>;

export default function Overview() {
    const { runs, isLoading, fetchSuites, fetchRuns } = useDashboardStore();
    const [health, setHealth] = useState<HealthResponse | null>(null);
    const [kemFamilyData, setKemFamilyData] = useState<AggregateRow[]>([]);
    const [aggWarning, setAggWarning] = useState<string | null>(null);

    useEffect(() => {
        fetchSuites();
        fetchRuns();
        fetch('/api/health')
            .then(res => res.json())
            .then(setHealth)
            .catch(() => setHealth(null));

        fetch('/api/aggregate/kem-family')
            .then(res => res.json())
            .then(payload => {
                if (payload?.warning) {
                    setAggWarning(payload.warning);
                    setKemFamilyData([]);
                } else {
                    setAggWarning(null);
                    setKemFamilyData(payload?.data ?? []);
                }
            })
            .catch(() => {
                setAggWarning('Aggregation unavailable');
                setKemFamilyData([]);
            });
    }, [fetchSuites, fetchRuns]);

    if (isLoading && runs.length === 0) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-gray-400">Loading dashboard...</div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold">PQC Benchmark Overview</h1>

            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="card">
                    <div className="text-gray-400 text-sm">Total Suites</div>
                    <div className="text-3xl font-bold text-blue-400">{health?.suites_loaded ?? '—'}</div>
                </div>
                <div className="card">
                    <div className="text-gray-400 text-sm">Benchmark Runs</div>
                    <div className="text-3xl font-bold text-purple-400">{health?.runs_loaded ?? '—'}</div>
                </div>
                <div className="card">
                    <div className="text-gray-400 text-sm">Pass Rate</div>
                    <div className="text-3xl font-bold text-gray-400">NOT AVAILABLE</div>
                </div>
                <div className="card">
                    <div className="text-gray-400 text-sm">Failed Suites</div>
                    <div className="text-3xl font-bold text-gray-400">NOT AVAILABLE</div>
                </div>
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Handshake Duration by KEM Family */}
                <div className="card">
                    <h3 className="card-header">Avg Handshake Duration by KEM Family (Derived, Server)</h3>
                    <div className="h-64">
                        {aggWarning ? (
                            <div className="text-gray-400 text-sm">{aggWarning}</div>
                        ) : (
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={kemFamilyData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                <XAxis dataKey="crypto_identity_kem_family" stroke="#9ca3af" tick={{ fontSize: 12 }} />
                                <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} label={{ value: 'ms', angle: -90, position: 'insideLeft', fill: '#9ca3af' }} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                                    labelStyle={{ color: '#9ca3af' }}
                                />
                                <Bar dataKey="handshake_handshake_total_duration_ms_mean" fill="#3b82f6" name="Avg Handshake (ms)" />
                            </BarChart>
                        </ResponsiveContainer>
                        )}
                    </div>
                </div>

                {/* Power by KEM Family */}
                <div className="card">
                    <h3 className="card-header">Avg Power by KEM Family (Derived, Server)</h3>
                    <div className="h-64">
                        {aggWarning ? (
                            <div className="text-gray-400 text-sm">{aggWarning}</div>
                        ) : (
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={kemFamilyData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                <XAxis dataKey="crypto_identity_kem_family" stroke="#9ca3af" tick={{ fontSize: 12 }} />
                                <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} label={{ value: 'W', angle: -90, position: 'insideLeft', fill: '#9ca3af' }} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                                    labelStyle={{ color: '#9ca3af' }}
                                />
                                <Bar dataKey="power_energy_power_avg_w_mean" fill="#10b981" name="Avg Power (W)" />
                            </BarChart>
                        </ResponsiveContainer>
                        )}
                    </div>
                </div>
            </div>

            {/* Recent Runs */}
            <div className="card">
                <h3 className="card-header">Recent Benchmark Runs</h3>
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
                                <td className="font-mono text-blue-400">{run.run_id.slice(0, 20)}...</td>
                                <td>{run.run_start_time_wall ? new Date(run.run_start_time_wall).toLocaleString() : '—'}</td>
                                <td>{run.gcs_hostname || '—'}</td>
                                <td>{run.drone_hostname || '—'}</td>
                                <td>{run.suite_count}</td>
                                <td className="font-mono text-xs">{run.git_commit_hash || '—'}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Quick Links */}
            <div className="flex gap-4">
                <Link to="/suites" className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded text-white transition-colors">
                    Browse All Suites →
                </Link>
                <Link to="/compare" className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded text-white transition-colors">
                    Compare Suites
                </Link>
            </div>
        </div>
    );
}
