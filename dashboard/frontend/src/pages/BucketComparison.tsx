/**
 * Bucket Comparison View - Compare suites within predefined groupings
 */

import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell } from 'recharts';

interface BucketSuite {
    key: string;
    suite_id: string;
    kem: string;
    sig: string;
    aead?: string;
    nist: string;
    handshake_ms: number;
    power_w: number;
    energy_j: number;
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

export default function BucketComparison() {
    const [buckets, setBuckets] = useState<Buckets | null>(null);
    const [selectedType, setSelectedType] = useState<BucketType>('kem_family');
    const [selectedBucket, setSelectedBucket] = useState<string>('');
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function fetchBuckets() {
            try {
                setIsLoading(true);
                const res = await fetch('http://localhost:8000/api/buckets');
                if (!res.ok) throw new Error('Failed to fetch buckets');
                const data = await res.json();
                setBuckets(data);
                // Auto-select first bucket
                const firstType = 'kem_family';
                const firstKey = Object.keys(data[firstType] || {})[0];
                if (firstKey) setSelectedBucket(firstKey);
            } catch (e) {
                setError(e instanceof Error ? e.message : 'Unknown error');
            } finally {
                setIsLoading(false);
            }
        }
        fetchBuckets();
    }, []);

    // Update selected bucket when type changes
    useEffect(() => {
        if (buckets && buckets[selectedType]) {
            const keys = Object.keys(buckets[selectedType]);
            if (keys.length > 0 && !keys.includes(selectedBucket)) {
                setSelectedBucket(keys[0]);
            }
        }
    }, [selectedType, buckets, selectedBucket]);

    if (isLoading) {
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

    // Prepare chart data
    const chartData = suites.map((s, idx) => ({
        name: s.suite_id.replace(/^cs-/, '').substring(0, 30),
        handshake_ms: s.handshake_ms,
        power_w: s.power_w,
        energy_j: s.energy_j,
        color: COLORS[idx % COLORS.length]
    }));

    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold">Comparison Buckets</h1>

            {/* Bucket Type Tabs */}
            <div className="card">
                <div className="flex flex-wrap gap-2 mb-4">
                    {(Object.keys(BUCKET_LABELS) as BucketType[]).map(type => (
                        <button
                            key={type}
                            onClick={() => setSelectedType(type)}
                            className={`px-4 py-2 rounded transition-colors ${selectedType === type
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                }`}
                        >
                            {BUCKET_LABELS[type]}
                        </button>
                    ))}
                </div>

                {/* Sub-bucket Selection */}
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

            {/* Handshake Comparison Chart */}
            {suites.length > 0 && (
                <div className="card">
                    <h3 className="card-header">Handshake Duration Comparison</h3>
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
            {suites.length > 0 && (
                <div className="card">
                    <h3 className="card-header">Power & Energy Comparison</h3>
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
                    <h3 className="card-header">Suite Details</h3>
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
                                        <td className="text-right font-mono">{s.handshake_ms.toFixed(2)}</td>
                                        <td className="text-right font-mono">{s.power_w.toFixed(2)}</td>
                                        <td className="text-right font-mono">{s.energy_j.toFixed(2)}</td>
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
