/**
 * Latency & Transport Analysis — RTT, jitter, one-way latency, MAVLink transport.
 */

import { useEffect } from 'react';
import { useDashboardStore } from '../state/store';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    ScatterChart, Scatter, ZAxis, Legend,
} from 'recharts';

function fmt(v: number | null | undefined, digits = 2): string {
    if (v == null || isNaN(v)) return '—';
    return v.toFixed(digits);
}

const NIST_COLORS: Record<string, string> = {
    L1: '#3b82f6',
    L3: '#8b5cf6',
    L5: '#ef4444',
};

export default function LatencyAnalysis() {
    const { suites, fetchSuites } = useDashboardStore();

    useEffect(() => { fetchSuites(); }, [fetchSuites]);

    // Process suites for latency data - group by KEM family
    const kemFamilies: Record<string, { rtt: number[]; jitter: number[]; handshake: number[]; name: string }> = {};
    suites.forEach(s => {
        const kem = s.kem_algorithm || '';
        const family = kem.includes('ML-KEM') || kem.includes('mlkem') ? 'ML-KEM'
            : kem.includes('HQC') || kem.includes('hqc') ? 'HQC'
            : kem.includes('McEliece') || kem.includes('mceliece') ? 'ClassicMcEliece'
            : 'Other';
        if (!kemFamilies[family]) kemFamilies[family] = { rtt: [], jitter: [], handshake: [], name: family };
        if (s.handshake_total_duration_ms != null) kemFamilies[family].handshake.push(s.handshake_total_duration_ms);
    });

    // For scatter: handshake vs suite index colored by NIST level
    const scatterData = suites
        .filter(s => s.handshake_total_duration_ms != null)
        .map((s, i) => ({
            index: i + 1,
            handshake_ms: s.handshake_total_duration_ms,
            suite_id: s.suite_id,
            nist: s.suite_security_level || 'Unknown',
            kem: s.kem_algorithm,
            power: s.power_avg_w,
        }));

    // KEM family avg handshake bar data
    const kemBarData = Object.values(kemFamilies)
        .filter(f => f.handshake.length > 0)
        .map(f => ({
            family: f.name,
            avg_handshake: f.handshake.reduce((a, b) => a + b, 0) / f.handshake.length,
            min_handshake: Math.min(...f.handshake),
            max_handshake: Math.max(...f.handshake),
            count: f.handshake.length,
        }))
        .sort((a, b) => a.avg_handshake - b.avg_handshake);

    // Handshake distribution by NIST level
    const nistGroups: Record<string, number[]> = {};
    suites.forEach(s => {
        const nist = s.suite_security_level || 'Unknown';
        if (!nistGroups[nist]) nistGroups[nist] = [];
        if (s.handshake_total_duration_ms != null) nistGroups[nist].push(s.handshake_total_duration_ms);
    });
    const nistBarData = Object.entries(nistGroups)
        .filter(([_, vals]) => vals.length > 0)
        .map(([level, vals]) => ({
            level,
            avg: vals.reduce((a, b) => a + b, 0) / vals.length,
            min: Math.min(...vals),
            max: Math.max(...vals),
            p95: vals.sort((a, b) => a - b)[Math.floor(vals.length * 0.95)] || 0,
            count: vals.length,
        }))
        .sort((a, b) => {
            const order: Record<string, number> = { L1: 1, L3: 2, L5: 3 };
            return (order[a.level] || 99) - (order[b.level] || 99);
        });

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-white">⏱️ Latency & Transport Analysis</h1>
                <p className="text-gray-400 text-sm mt-1">Handshake timing, RTT, jitter, and transport performance — raw data, no smoothing</p>
            </div>

            {/* ── KPI Row ── */}
            <div className="grid grid-cols-4 gap-4">
                {nistBarData.map(n => (
                    <div key={n.level} className="card" style={{ borderLeft: `4px solid ${NIST_COLORS[n.level] || '#6b7280'}` }}>
                        <div className="text-xs text-gray-400 uppercase tracking-wider">NIST {n.level} ({n.count} suites)</div>
                        <div className="text-2xl font-bold text-white mt-1">{fmt(n.avg)} ms</div>
                        <div className="text-xs text-gray-500 mt-1">P95: {fmt(n.p95)} ms • Range: {fmt(n.min)}–{fmt(n.max)} ms</div>
                    </div>
                ))}
            </div>

            <div className="grid grid-cols-2 gap-6">
                {/* ── Handshake by KEM Family ── */}
                <div className="card">
                    <h2 className="text-lg font-semibold text-white mb-4">🔑 Handshake by KEM Family</h2>
                    <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={kemBarData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                            <XAxis dataKey="family" tick={{ fill: '#d1d5db', fontSize: 11 }} />
                            <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} label={{ value: 'ms', angle: -90, position: 'insideLeft', fill: '#6b7280' }} />
                            <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                                formatter={(v: number) => `${fmt(v)} ms`} />
                            <Legend />
                            <Bar dataKey="avg_handshake" fill="#3b82f6" name="Avg" radius={[4, 4, 0, 0]} />
                            <Bar dataKey="max_handshake" fill="#ef4444" name="Max" radius={[4, 4, 0, 0]} />
                            <Bar dataKey="min_handshake" fill="#10b981" name="Min" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                {/* ── Handshake by NIST Level ── */}
                <div className="card">
                    <h2 className="text-lg font-semibold text-white mb-4">🏛️ Handshake by NIST Level</h2>
                    <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={nistBarData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                            <XAxis dataKey="level" tick={{ fill: '#d1d5db', fontSize: 12 }} />
                            <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} label={{ value: 'ms', angle: -90, position: 'insideLeft', fill: '#6b7280' }} />
                            <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                                formatter={(v: number) => `${fmt(v)} ms`} />
                            <Legend />
                            <Bar dataKey="avg" fill="#8b5cf6" name="Avg" radius={[4, 4, 0, 0]} />
                            <Bar dataKey="p95" fill="#f59e0b" name="P95" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* ── Scatter: All suites handshake by NIST level ── */}
            <div className="card">
                <h2 className="text-lg font-semibold text-white mb-4">🎯 Handshake Distribution (All Suites)</h2>
                <ResponsiveContainer width="100%" height={350}>
                    <ScatterChart>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis type="number" dataKey="index" name="Suite #" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                        <YAxis type="number" dataKey="handshake_ms" name="Handshake (ms)" tick={{ fill: '#9ca3af', fontSize: 11 }}
                            label={{ value: 'ms', angle: -90, position: 'insideLeft', fill: '#6b7280' }} />
                        <ZAxis type="number" dataKey="power" range={[20, 200]} name="Power (W)" />
                        <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                            formatter={(v: any, name: string) => [typeof v === 'number' ? fmt(v, 3) : v, name]}
                            labelFormatter={(i) => {
                                const pt = scatterData[Number(i) - 1];
                                return pt ? `${pt.suite_id} (${pt.kem})` : '';
                            }} />
                        <Legend />
                        {Object.entries(NIST_COLORS).map(([level, color]) => {
                            const pts = scatterData.filter(p => p.nist === level);
                            return pts.length > 0 ? (
                                <Scatter key={level} name={`NIST ${level}`} data={pts} fill={color} />
                            ) : null;
                        })}
                        {(() => {
                            const other = scatterData.filter(p => !NIST_COLORS[p.nist]);
                            return other.length > 0 ? <Scatter name="Other" data={other} fill="#6b7280" /> : null;
                        })()}
                    </ScatterChart>
                </ResponsiveContainer>
            </div>

            {/* ── Top 10 Slowest Handshakes ── */}
            <div className="card">
                <h2 className="text-lg font-semibold text-white mb-4">🐌 Top 15 Slowest Handshakes</h2>
                <div className="overflow-x-auto">
                    <table className="data-table w-full">
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
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {suites
                                .filter(s => s.handshake_total_duration_ms != null)
                                .sort((a, b) => (b.handshake_total_duration_ms || 0) - (a.handshake_total_duration_ms || 0))
                                .slice(0, 15)
                                .map((s, i) => (
                                    <tr key={i}>
                                        <td className="text-gray-500">{i + 1}</td>
                                        <td className="font-mono text-sm text-white">{s.suite_id}</td>
                                        <td className="text-gray-300 text-xs">{s.kem_algorithm}</td>
                                        <td className="text-gray-300 text-xs">{s.sig_algorithm}</td>
                                        <td>
                                            <span className="px-1.5 py-0.5 rounded text-xs font-medium"
                                                style={{ color: NIST_COLORS[s.suite_security_level] || '#9ca3af', backgroundColor: (NIST_COLORS[s.suite_security_level] || '#9ca3af') + '22' }}>
                                                {s.suite_security_level || '?'}
                                            </span>
                                        </td>
                                        <td className="text-right font-mono text-yellow-400">{fmt(s.handshake_total_duration_ms)}</td>
                                        <td className="text-right font-mono text-white">{fmt(s.power_avg_w, 3)}</td>
                                        <td className="text-right font-mono text-white">{fmt(s.energy_total_j, 3)}</td>
                                        <td>
                                            <span className={`badge-${s.benchmark_pass_fail === 'PASS' ? 'green' : 'red'}`}>
                                                {s.benchmark_pass_fail || '?'}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
