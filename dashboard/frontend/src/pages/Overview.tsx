/**
 * Overview Page - Dashboard summary with key metrics
 */

import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useDashboardStore } from '../state/store';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    LineChart, Line, Legend
} from 'recharts';

export default function Overview() {
    const { suites, runs, isLoading, fetchSuites, fetchRuns } = useDashboardStore();

    useEffect(() => {
        fetchSuites();
        fetchRuns();
    }, [fetchSuites, fetchRuns]);

    // Aggregate data for charts
    const kemFamilyData = suites.reduce((acc, suite) => {
        const family = suite.kem_algorithm.split('-')[0] || 'Unknown';
        const existing = acc.find(d => d.name === family);
        if (existing) {
            existing.count++;
            existing.avgHandshake = (existing.avgHandshake * (existing.count - 1) + suite.handshake_total_duration_ms) / existing.count;
            existing.avgPower = (existing.avgPower * (existing.count - 1) + suite.power_avg_w) / existing.count;
        } else {
            acc.push({
                name: family,
                count: 1,
                avgHandshake: suite.handshake_total_duration_ms,
                avgPower: suite.power_avg_w
            });
        }
        return acc;
    }, [] as { name: string; count: number; avgHandshake: number; avgPower: number }[]);

    // Pass/fail summary
    const passCount = suites.filter(s => s.benchmark_pass_fail === 'PASS').length;
    const failCount = suites.filter(s => s.benchmark_pass_fail === 'FAIL').length;

    if (isLoading && suites.length === 0) {
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
                    <div className="text-3xl font-bold text-blue-400">{suites.length}</div>
                </div>
                <div className="card">
                    <div className="text-gray-400 text-sm">Benchmark Runs</div>
                    <div className="text-3xl font-bold text-purple-400">{runs.length}</div>
                </div>
                <div className="card">
                    <div className="text-gray-400 text-sm">Pass Rate</div>
                    <div className="text-3xl font-bold text-green-400">
                        {suites.length > 0 ? ((passCount / suites.length) * 100).toFixed(1) : 0}%
                    </div>
                </div>
                <div className="card">
                    <div className="text-gray-400 text-sm">Failed Suites</div>
                    <div className="text-3xl font-bold text-red-400">{failCount}</div>
                </div>
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Handshake Duration by KEM Family */}
                <div className="card">
                    <h3 className="card-header">Avg Handshake Duration by KEM Family</h3>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={kemFamilyData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                <XAxis dataKey="name" stroke="#9ca3af" tick={{ fontSize: 12 }} />
                                <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} label={{ value: 'ms', angle: -90, position: 'insideLeft', fill: '#9ca3af' }} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                                    labelStyle={{ color: '#9ca3af' }}
                                />
                                <Bar dataKey="avgHandshake" fill="#3b82f6" name="Avg Handshake (ms)" />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Power by KEM Family */}
                <div className="card">
                    <h3 className="card-header">Avg Power by KEM Family</h3>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={kemFamilyData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                <XAxis dataKey="name" stroke="#9ca3af" tick={{ fontSize: 12 }} />
                                <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} label={{ value: 'W', angle: -90, position: 'insideLeft', fill: '#9ca3af' }} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                                    labelStyle={{ color: '#9ca3af' }}
                                />
                                <Bar dataKey="avgPower" fill="#10b981" name="Avg Power (W)" />
                            </BarChart>
                        </ResponsiveContainer>
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
