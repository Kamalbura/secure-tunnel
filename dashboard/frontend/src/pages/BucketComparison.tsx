/**
 * Bucket Comparison View - Compare suites within predefined groupings
 * Enhanced: Per-threat-scenario comparison, heatmap, KPI summary cards
 */

import { useState, useEffect, useMemo } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell,
    RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';
import { useDashboardStore } from '../state/store';
import { RUN_TYPE_COLORS, RUN_TYPE_LABELS, type RunType } from '../types/metrics';

interface BucketSuite {
    key: string;
    suite_id: string;
    kem: string;
    sig: string;
    aead?: string;
    nist: string;
    handshake_ms: number | null;
    power_w: number | null;
    energy_j: number | null;
}

interface Buckets {
    nist_level: Record<string, BucketSuite[]>;
    nist_aead: Record<string, BucketSuite[]>;
    aead: Record<string, BucketSuite[]>;
    kem_family: Record<string, BucketSuite[]>;
    sig_family: Record<string, BucketSuite[]>;
}

type BucketType = 'nist_level' | 'nist_aead' | 'aead' | 'kem_family' | 'sig_family';

const BUCKET_LABELS: Record<BucketType, string> = {
    nist_level: 'NIST Security Level',
    nist_aead: 'NIST Level + AEAD',
    aead: 'AEAD Algorithm',
    kem_family: 'KEM Family',
    sig_family: 'Signature Family'
};

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#f97316'];

function avg(arr: number[]): number { return arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0; }

export default function BucketComparison() {
    const { settings, fetchSettings } = useDashboardStore();
    const [buckets, setBuckets] = useState<Buckets | null>(null);
    const [selectedType, setSelectedType] = useState<BucketType>('kem_family');
    const [selectedBucket, setSelectedBucket] = useState<string>('');
    const [selectedRunId, setSelectedRunId] = useState<string>('');
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => { fetchSettings(); }, [fetchSettings]);

    useEffect(() => {
        async function fetchBuckets() {
            try {
                setIsLoading(true);
                const url = selectedRunId ? `/api/buckets?run_id=${encodeURIComponent(selectedRunId)}` : '/api/buckets';
                const res = await fetch(url);
                if (!res.ok) throw new Error('Failed to fetch buckets');
                const data = await res.json();
                setBuckets(data);
                const firstKey = Object.keys(data[selectedType] || {})[0];
                if (firstKey && !Object.keys(data[selectedType] || {}).includes(selectedBucket)) {
                    setSelectedBucket(firstKey);
                }
            } catch (e) {
                setError(e instanceof Error ? e.message : 'Unknown error');
            } finally {
                setIsLoading(false);
            }
        }
        fetchBuckets();
    }, [selectedRunId, selectedType, selectedBucket]);

    useEffect(() => {
        if (buckets && buckets[selectedType]) {
            const keys = Object.keys(buckets[selectedType]);
            if (keys.length > 0 && !keys.includes(selectedBucket)) {
                setSelectedBucket(keys[0]);
            }
        }
    }, [selectedType, buckets, selectedBucket]);

    const availableRuns = settings?.available_runs || [];
    const runLabels = settings?.run_labels || {};

    // Build cross-bucket aggregate for radar comparison
    const radarData = useMemo(() => {
        if (!buckets) return [];
        const currentBucketData = buckets[selectedType] || {};
        return Object.entries(currentBucketData).map(([name, suites]) => {
            const hs = suites.map(s => s.handshake_ms).filter((v): v is number => v != null);
            const pw = suites.map(s => s.power_w).filter((v): v is number => v != null);
            const en = suites.map(s => s.energy_j).filter((v): v is number => v != null);
            return {
                bucket: name.length > 15 ? name.substring(0, 15) + '…' : name,
                Handshake: avg(hs),
                Power: avg(pw),
                Energy: avg(en),
                Suites: suites.length,
            };
        });
    }, [buckets, selectedType]);

    if (isLoading && !buckets) {
        return <div className="text-center py-12 text-gray-400">Loading comparison buckets...</div>;
    }
    if (error) {
        return <div className="text-center py-12 text-red-400">Error: {error}</div>;
    }
    if (!buckets) {
        return <div className="text-center py-12 text-gray-400">No data available</div>;
    }

    const currentBucketData = buckets[selectedType] || {};
    const bucketKeys = Object.keys(currentBucketData);
    const suites = currentBucketData[selectedBucket] || [];

    // KPI summary for selected bucket
    const kpiHandshake = suites.map(s => s.handshake_ms).filter((v): v is number => v != null);
    const kpiPower = suites.map(s => s.power_w).filter((v): v is number => v != null);
    const kpiEnergy = suites.map(s => s.energy_j).filter((v): v is number => v != null);

    const chartData = suites
        .filter(s => s.handshake_ms != null && s.power_w != null && s.energy_j != null)
        .map((s, idx) => ({
            name: s.suite_id.replace(/^cs-/, '').substring(0, 30),
            handshake_ms: s.handshake_ms,
            power_w: s.power_w,
            energy_j: s.energy_j,
            color: COLORS[idx % COLORS.length]
        }));

    // Run type info for header
    const runLabel = selectedRunId ? (runLabels[selectedRunId] as { label?: string; type?: RunType })?.label || selectedRunId : 'All Runs';
    const runType = selectedRunId ? (runLabels[selectedRunId] as { type?: RunType })?.type || 'baseline' : undefined;

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">🪣 Comparison Buckets</h1>
                    <p className="text-sm text-gray-400 mt-1">
                        Group suites by algorithm properties. Select a run to isolate threat scenarios.
                    </p>
                </div>
                {runType && (
                    <span className="px-3 py-1 rounded-full text-sm font-medium" style={{
                        backgroundColor: `${RUN_TYPE_COLORS[runType as RunType]}22`,
                        color: RUN_TYPE_COLORS[runType as RunType],
                        border: `1px solid ${RUN_TYPE_COLORS[runType as RunType]}44`,
                    }}>
                        {RUN_TYPE_LABELS[runType as RunType]}
                    </span>
                )}
            </div>

            {/* Run Selector + Bucket Type Tabs */}
            <div className="card">
                <div className="flex flex-wrap gap-4 items-end mb-4">
                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Run / Threat Scenario</label>
                        <select
                            className="select-input"
                            value={selectedRunId}
                            onChange={e => setSelectedRunId(e.target.value)}
                        >
                            <option value="">All Runs (Combined)</option>
                            {availableRuns.map((r: { run_id: string; suite_count: number }) => {
                                const rl = runLabels[r.run_id] as { label?: string; type?: RunType } | undefined;
                                return (
                                    <option key={r.run_id} value={r.run_id}>
                                        {rl?.label || r.run_id} ({r.suite_count} suites) {rl?.type ? `— ${RUN_TYPE_LABELS[rl.type]}` : ''}
                                    </option>
                                );
                            })}
                        </select>
                    </div>
                </div>
                <div className="flex flex-wrap gap-2 mb-4">
                    {(Object.keys(BUCKET_LABELS) as BucketType[]).map(type => (
                        <button
                            key={type}
                            onClick={() => setSelectedType(type)}
                            className={`px-4 py-2 rounded transition-colors text-sm ${selectedType === type
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                            }`}
                        >
                            {BUCKET_LABELS[type]}
                        </button>
                    ))}
                </div>
                <div className="flex items-center gap-4">
                    <label className="text-gray-400">Select Group:</label>
                    <select
                        className="select-input"
                        value={selectedBucket}
                        onChange={e => setSelectedBucket(e.target.value)}
                    >
                        {bucketKeys.map(key => (
                            <option key={key} value={key}>
                                {key} ({currentBucketData[key]?.length || 0} suites)
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            {/* KPI Cards for selected bucket */}
            {suites.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    <div className="card text-center">
                        <div className="text-xs text-gray-400 uppercase tracking-wider">Suites</div>
                        <div className="text-2xl font-bold text-white mt-1">{suites.length}</div>
                    </div>
                    <div className="card text-center">
                        <div className="text-xs text-gray-400 uppercase tracking-wider">Avg Handshake</div>
                        <div className="text-2xl font-bold text-blue-400 mt-1">{kpiHandshake.length ? avg(kpiHandshake).toFixed(0) : '—'}<span className="text-sm text-gray-400"> ms</span></div>
                    </div>
                    <div className="card text-center">
                        <div className="text-xs text-gray-400 uppercase tracking-wider">Max Handshake</div>
                        <div className="text-2xl font-bold text-red-400 mt-1">{kpiHandshake.length ? Math.max(...kpiHandshake).toFixed(0) : '—'}<span className="text-sm text-gray-400"> ms</span></div>
                    </div>
                    <div className="card text-center">
                        <div className="text-xs text-gray-400 uppercase tracking-wider">Avg Power</div>
                        <div className="text-2xl font-bold text-green-400 mt-1">{kpiPower.length ? avg(kpiPower).toFixed(3) : '—'}<span className="text-sm text-gray-400"> W</span></div>
                    </div>
                    <div className="card text-center">
                        <div className="text-xs text-gray-400 uppercase tracking-wider">Avg Energy</div>
                        <div className="text-2xl font-bold text-yellow-400 mt-1">{kpiEnergy.length ? avg(kpiEnergy).toFixed(1) : '—'}<span className="text-sm text-gray-400"> J</span></div>
                    </div>
                </div>
            )}

            {/* Cross-Bucket Radar Overview */}
            {radarData.length > 1 && radarData.length <= 8 && (
                <div className="card">
                    <h3 className="card-header">📊 Cross-Bucket Overview — {BUCKET_LABELS[selectedType]}</h3>
                    <p className="text-xs text-gray-400 mb-4">Radar shows relative averages across all groups for this bucket type.</p>
                    <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                            <RadarChart data={radarData}>
                                <PolarGrid stroke="#374151" />
                                <PolarAngleAxis dataKey="bucket" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                                <PolarRadiusAxis tick={{ fill: '#6b7280', fontSize: 10 }} />
                                <Radar name="Handshake (ms)" dataKey="Handshake" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} />
                                <Radar name="Power (W)" dataKey="Power" stroke="#10b981" fill="#10b981" fillOpacity={0.15} />
                                <Radar name="Energy (J)" dataKey="Energy" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.1} />
                                <Legend />
                                <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }} />
                            </RadarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}

            {/* Handshake Comparison Chart */}
            {chartData.length > 0 && (
                <div className="card">
                    <h3 className="card-header">🔑 Handshake Duration — {selectedBucket}</h3>
                    <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={chartData} layout="vertical" margin={{ left: 150 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                <XAxis type="number" stroke="#9ca3af" />
                                <YAxis dataKey="name" type="category" width={140} stroke="#9ca3af" tick={{ fontSize: 10 }} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                                    formatter={(value: number) => [`${value.toFixed(2)} ms`, 'Handshake']}
                                />
                                <Bar dataKey="handshake_ms" name="Handshake (ms)">
                                    {chartData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}

            {/* Power/Energy Comparison Chart */}
            {chartData.length > 0 && (
                <div className="card">
                    <h3 className="card-header">⚡ Power & Energy — {selectedBucket}</h3>
                    <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={chartData} layout="vertical" margin={{ left: 150 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                <XAxis type="number" stroke="#9ca3af" />
                                <YAxis dataKey="name" type="category" width={140} stroke="#9ca3af" tick={{ fontSize: 10 }} />
                                <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }} />
                                <Legend />
                                <Bar dataKey="power_w" name="Power (W)" fill="#10b981" />
                                <Bar dataKey="energy_j" name="Energy (J)" fill="#f59e0b" />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}

            {/* Suite Table */}
            {suites.length > 0 && (
                <div className="card">
                    <h3 className="card-header">📋 Suite Details — {selectedBucket} ({suites.length})</h3>
                    <div className="overflow-x-auto">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Suite ID</th>
                                    <th>KEM</th>
                                    <th>SIG</th>
                                    <th>NIST</th>
                                    <th className="text-right">Handshake (ms)</th>
                                    <th className="text-right">Power (W)</th>
                                    <th className="text-right">Energy (J)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {suites.map((s, idx) => (
                                    <tr key={s.key}>
                                        <td className="text-gray-500">{idx + 1}</td>
                                        <td className="font-mono text-sm">{s.suite_id}</td>
                                        <td>{s.kem}</td>
                                        <td>{s.sig}</td>
                                        <td>
                                            <span className={`px-2 py-0.5 rounded text-xs ${s.nist === 'L1' ? 'bg-green-500/20 text-green-400' :
                                                s.nist === 'L3' ? 'bg-yellow-500/20 text-yellow-400' :
                                                    s.nist === 'L5' ? 'bg-red-500/20 text-red-400' : 'bg-gray-500/20'
                                            }`}>
                                                {s.nist}
                                            </span>
                                        </td>
                                        <td className="text-right font-mono">{s.handshake_ms != null ? s.handshake_ms.toFixed(2) : '—'}</td>
                                        <td className="text-right font-mono">{s.power_w != null ? s.power_w.toFixed(3) : '—'}</td>
                                        <td className="text-right font-mono">{s.energy_j != null ? s.energy_j.toFixed(2) : '—'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {suites.length === 0 && (
                <div className="text-center py-12 text-gray-400">
                    No suites in this bucket. Select a different group.
                </div>
            )}
        </div>
    );
}
