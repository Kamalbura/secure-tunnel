/**
 * Suite Explorer Page - Browse and filter all suites
 */

import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useDashboardStore } from '../state/store';

export default function SuiteExplorer() {
    const {
        suites,
        filters,
        isLoading,
        selectedKemFamily,
        selectedSigFamily,
        selectedAead,
        selectedNistLevel,
        selectedRunId,
        fetchSuites,
        setFilter,
        clearFilters
    } = useDashboardStore();

    useEffect(() => {
        fetchSuites();
    }, [fetchSuites, selectedKemFamily, selectedSigFamily, selectedAead, selectedNistLevel, selectedRunId]);

    // Get reliability badge class
    const getPassBadge = (status: string) => {
        if (status === 'PASS') return 'badge-verified';
        if (status === 'FAIL') return 'bg-red-500/20 text-red-400 px-2 py-0.5 rounded text-xs font-medium';
        return 'badge-missing';
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold">Suite Explorer</h1>
                <div className="text-gray-400">
                    {suites.length} suites
                </div>
            </div>

            {/* Filters */}
            <div className="card">
                <div className="flex flex-wrap gap-4 items-end">
                    <div>
                        <label className="block text-sm text-gray-400 mb-1">KEM Family</label>
                        <select
                            className="select-input"
                            value={selectedKemFamily || ''}
                            onChange={e => setFilter('selectedKemFamily', e.target.value || null)}
                        >
                            <option value="">All KEM</option>
                            {filters?.kem_families.map(f => (
                                <option key={f} value={f}>{f}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Signature Family</label>
                        <select
                            className="select-input"
                            value={selectedSigFamily || ''}
                            onChange={e => setFilter('selectedSigFamily', e.target.value || null)}
                        >
                            <option value="">All Signatures</option>
                            {filters?.sig_families.map(f => (
                                <option key={f} value={f}>{f}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm text-gray-400 mb-1">AEAD</label>
                        <select
                            className="select-input"
                            value={selectedAead || ''}
                            onChange={e => setFilter('selectedAead', e.target.value || null)}
                        >
                            <option value="">All AEAD</option>
                            {filters?.aead_algorithms.map(f => (
                                <option key={f} value={f}>{f}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm text-gray-400 mb-1">NIST Level</label>
                        <select
                            className="select-input"
                            value={selectedNistLevel || ''}
                            onChange={e => setFilter('selectedNistLevel', e.target.value || null)}
                        >
                            <option value="">All Levels</option>
                            {filters?.nist_levels.map(f => (
                                <option key={f} value={f}>{f}</option>
                            ))}
                        </select>
                    </div>

                    <button
                        onClick={clearFilters}
                        className="px-3 py-2 text-sm text-gray-400 hover:text-white"
                    >
                        Clear Filters
                    </button>
                </div>
            </div>

            {/* Suite Table */}
            <div className="card overflow-x-auto">
                {isLoading ? (
                    <div className="text-center py-8 text-gray-400">Loading suites...</div>
                ) : suites.length === 0 ? (
                    <div className="text-center py-8 text-gray-400">No suites found with current filters</div>
                ) : (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Suite ID</th>
                                <th>KEM</th>
                                <th>Signature</th>
                                <th>AEAD</th>
                                <th>Level</th>
                                <th>Handshake (ms)</th>
                                <th>Power (W)</th>
                                <th>Energy (J)</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {suites.map(suite => (
                                <tr key={`${suite.run_id}:${suite.suite_id}`}>
                                    <td className="text-gray-500">{suite.suite_index}</td>
                                    <td>
                                        <Link
                                            to={`/suite/${encodeURIComponent(suite.run_id + ':' + suite.suite_id)}`}
                                            className="text-blue-400 hover:text-blue-300 hover:underline"
                                        >
                                            {suite.suite_id}
                                        </Link>
                                    </td>
                                    <td className="font-mono text-sm">{suite.kem_algorithm || '—'}</td>
                                    <td className="font-mono text-sm">{suite.sig_algorithm || '—'}</td>
                                    <td className="font-mono text-sm">{suite.aead_algorithm || '—'}</td>
                                    <td>
                                        {suite.suite_security_level ? (
                                            <span className="bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded text-xs">
                                                {suite.suite_security_level}
                                            </span>
                                        ) : '—'}
                                    </td>
                                    <td className="text-right font-mono">
                                        {suite.handshake_total_duration_ms !== null && suite.handshake_total_duration_ms !== undefined
                                            ? suite.handshake_total_duration_ms.toFixed(2)
                                            : 'Not collected'}
                                    </td>
                                    <td className="text-right font-mono">
                                        {suite.power_avg_w !== null && suite.power_avg_w !== undefined
                                            ? suite.power_avg_w.toFixed(2)
                                            : 'Not collected'}
                                    </td>
                                    <td className="text-right font-mono">
                                        {suite.energy_total_j !== null && suite.energy_total_j !== undefined
                                            ? suite.energy_total_j.toFixed(2)
                                            : 'Not collected'}
                                    </td>
                                    <td>
                                        <span className={getPassBadge(suite.benchmark_pass_fail)}>
                                            {suite.benchmark_pass_fail || '—'}
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}
