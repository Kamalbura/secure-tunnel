/**
 * Comparison View Page - Side-by-side suite comparison
 */

import { useState, useEffect } from 'react';
import { useDashboardStore } from '../state/store';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export default function ComparisonView() {
    const { suites, comparisonSuiteA, comparisonSuiteB, isLoading, fetchSuites, fetchComparison } = useDashboardStore();
    const [suiteAKey, setSuiteAKey] = useState<string>('');
    const [suiteBKey, setSuiteBKey] = useState<string>('');

    useEffect(() => {
        fetchSuites();
    }, [fetchSuites]);

    const handleCompare = () => {
        if (suiteAKey && suiteBKey) {
            fetchComparison(suiteAKey, suiteBKey);
        }
    };

    // Build comparison data for charts
    const comparisonData = comparisonSuiteA && comparisonSuiteB ? [
        {
            metric: 'Handshake (ms)',
            'Suite A': comparisonSuiteA.handshake.handshake_total_duration_ms,
            'Suite B': comparisonSuiteB.handshake.handshake_total_duration_ms,
        },
        {
            metric: 'Power Avg (W)',
            'Suite A': comparisonSuiteA.power_energy.power_avg_w,
            'Suite B': comparisonSuiteB.power_energy.power_avg_w,
        },
        {
            metric: 'Energy (J)',
            'Suite A': comparisonSuiteA.power_energy.energy_total_j,
            'Suite B': comparisonSuiteB.power_energy.energy_total_j,
        },
        {
            metric: 'CPU Avg (%)',
            'Suite A': comparisonSuiteA.system_drone.cpu_usage_avg_percent,
            'Suite B': comparisonSuiteB.system_drone.cpu_usage_avg_percent,
        },
    ] : [];

    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold">Suite Comparison</h1>

            {/* Suite Selection */}
            <div className="card">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Suite A (Baseline)</label>
                        <select
                            className="select-input w-full"
                            value={suiteAKey}
                            onChange={e => setSuiteAKey(e.target.value)}
                        >
                            <option value="">Select Suite A</option>
                            {suites.map(s => (
                                <option key={`${s.run_id}:${s.suite_id}`} value={`${s.run_id}:${s.suite_id}`}>
                                    {s.suite_id}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Suite B</label>
                        <select
                            className="select-input w-full"
                            value={suiteBKey}
                            onChange={e => setSuiteBKey(e.target.value)}
                        >
                            <option value="">Select Suite B</option>
                            {suites.map(s => (
                                <option key={`${s.run_id}:${s.suite_id}`} value={`${s.run_id}:${s.suite_id}`}>
                                    {s.suite_id}
                                </option>
                            ))}
                        </select>
                    </div>

                    <button
                        onClick={handleCompare}
                        disabled={!suiteAKey || !suiteBKey || isLoading}
                        className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-4 py-2 rounded text-white transition-colors"
                    >
                        Compare
                    </button>
                </div>
            </div>

            {/* Comparison Results */}
            {comparisonSuiteA && comparisonSuiteB && (
                <>
                    {/* Suite Headers */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="card bg-blue-900/20">
                            <h3 className="text-lg font-semibold text-blue-400">Suite A: {comparisonSuiteA.run_context.suite_id}</h3>
                            <div className="text-sm text-gray-400 mt-1">
                                {comparisonSuiteA.crypto_identity.kem_algorithm} + {comparisonSuiteA.crypto_identity.sig_algorithm}
                            </div>
                        </div>
                        <div className="card bg-purple-900/20">
                            <h3 className="text-lg font-semibold text-purple-400">Suite B: {comparisonSuiteB.run_context.suite_id}</h3>
                            <div className="text-sm text-gray-400 mt-1">
                                {comparisonSuiteB.crypto_identity.kem_algorithm} + {comparisonSuiteB.crypto_identity.sig_algorithm}
                            </div>
                        </div>
                    </div>

                    {/* Comparison Chart */}
                    <div className="card">
                        <h3 className="card-header">Metric Comparison</h3>
                        <div className="h-80">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={comparisonData} layout="vertical">
                                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                    <XAxis type="number" stroke="#9ca3af" />
                                    <YAxis dataKey="metric" type="category" width={120} stroke="#9ca3af" />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                                    />
                                    <Legend />
                                    <Bar dataKey="Suite A" fill="#3b82f6" />
                                    <Bar dataKey="Suite B" fill="#a855f7" />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* Detailed Comparison Table */}
                    <div className="card">
                        <h3 className="card-header">Detailed Comparison</h3>
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Metric</th>
                                    <th className="text-right">Suite A</th>
                                    <th className="text-right">Suite B</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td>Handshake Duration</td>
                                    <td className="text-right font-mono">{comparisonSuiteA.handshake.handshake_total_duration_ms.toFixed(2)} ms</td>
                                    <td className="text-right font-mono">{comparisonSuiteB.handshake.handshake_total_duration_ms.toFixed(2)} ms</td>
                                </tr>
                                <tr>
                                    <td>Power Avg</td>
                                    <td className="text-right font-mono">{comparisonSuiteA.power_energy.power_avg_w.toFixed(2)} W</td>
                                    <td className="text-right font-mono">{comparisonSuiteB.power_energy.power_avg_w.toFixed(2)} W</td>
                                </tr>
                                <tr>
                                    <td>Energy Total</td>
                                    <td className="text-right font-mono">{comparisonSuiteA.power_energy.energy_total_j.toFixed(2)} J</td>
                                    <td className="text-right font-mono">{comparisonSuiteB.power_energy.energy_total_j.toFixed(2)} J</td>
                                </tr>
                                <tr>
                                    <td>Packets Sent</td>
                                    <td className="text-right font-mono">{comparisonSuiteA.data_plane.packets_sent}</td>
                                    <td className="text-right font-mono">{comparisonSuiteB.data_plane.packets_sent}</td>
                                </tr>
                                <tr>
                                    <td>CPU Avg</td>
                                    <td className="text-right font-mono">{comparisonSuiteA.system_drone.cpu_usage_avg_percent.toFixed(1)}%</td>
                                    <td className="text-right font-mono">{comparisonSuiteB.system_drone.cpu_usage_avg_percent.toFixed(1)}%</td>
                                </tr>
                                <tr>
                                    <td>Memory RSS</td>
                                    <td className="text-right font-mono">{comparisonSuiteA.system_drone.memory_rss_mb.toFixed(2)} MB</td>
                                    <td className="text-right font-mono">{comparisonSuiteB.system_drone.memory_rss_mb.toFixed(2)} MB</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </>
            )}

            {!comparisonSuiteA && !comparisonSuiteB && (
                <div className="text-center py-12 text-gray-400">
                    Select two suites above to compare their metrics side-by-side.
                </div>
            )}
        </div>
    );
}
