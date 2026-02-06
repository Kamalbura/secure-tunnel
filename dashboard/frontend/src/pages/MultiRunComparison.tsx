/**
 * MultiRunComparison Page — Compare same suite across 3 run scenarios.
 * No DDoS vs DDoS XGBoost vs DDoS TXT — side-by-side.
 */

import { useEffect, useState } from 'react';
import { useDashboardStore } from '../state/store';
import { RUN_TYPE_COLORS, RUN_TYPE_LABELS, type RunType } from '../types/metrics';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from 'recharts';

function fmt(v: number | null | undefined, digits = 2): string {
    if (v == null || isNaN(v)) return '—';
    return v.toFixed(digits);
}

export default function MultiRunComparison() {
    const {
        suites, fetchSuites, multiRunCompare, fetchMultiRunCompare, fetchSettings,
    } = useDashboardStore();

    const [selectedSuiteId, setSelectedSuiteId] = useState<string>('');

    useEffect(() => { fetchSuites(); fetchSettings(); }, [fetchSuites, fetchSettings]);

    // Unique suite IDs
    const uniqueSuiteIds = [...new Set(suites.map(s => s.suite_id))].sort();

    useEffect(() => {
        if (uniqueSuiteIds.length > 0 && !selectedSuiteId) {
            setSelectedSuiteId(uniqueSuiteIds[0]);
        }
    }, [uniqueSuiteIds, selectedSuiteId]);

    useEffect(() => {
        if (selectedSuiteId) fetchMultiRunCompare(selectedSuiteId);
    }, [selectedSuiteId, fetchMultiRunCompare]);

    const runs = multiRunCompare?.runs || [];

    // Build bar chart data for key metrics
    const barMetrics = [
        { key: 'handshake_ms', label: 'Handshake (ms)', extract: (s: any) => s.handshake?.handshake_total_duration_ms },
        { key: 'power_w', label: 'Power Avg (W)', extract: (s: any) => s.power_energy?.power_avg_w },
        { key: 'energy_j', label: 'Energy (J)', extract: (s: any) => s.power_energy?.energy_total_j },
        { key: 'packet_loss', label: 'Packet Loss Ratio', extract: (s: any) => s.data_plane?.packet_loss_ratio },
        { key: 'cpu_drone', label: 'Drone CPU (%)', extract: (s: any) => s.system_drone?.cpu_usage_avg_percent },
        { key: 'rtt_ms', label: 'RTT Avg (ms)', extract: (s: any) => s.latency_jitter?.rtt_avg_ms },
    ];

    const barData = barMetrics.map(m => {
        const row: Record<string, any> = { metric: m.label };
        runs.forEach(r => {
            row[r.run_type] = m.extract(r.suite);
        });
        return row;
    });

    // Radar data (normalized to 0-100 for visibility)
    const radarMetrics = [
        { key: 'Handshake', extract: (s: any) => s.handshake?.handshake_total_duration_ms ?? 0, max: 50000 },
        { key: 'Power', extract: (s: any) => s.power_energy?.power_avg_w ?? 0, max: 10 },
        { key: 'Energy', extract: (s: any) => s.power_energy?.energy_total_j ?? 0, max: 200 },
        { key: 'CPU', extract: (s: any) => s.system_drone?.cpu_usage_avg_percent ?? 0, max: 100 },
        { key: 'Memory', extract: (s: any) => s.system_drone?.memory_rss_mb ?? 0, max: 500 },
        { key: 'PktLoss', extract: (s: any) => (s.data_plane?.packet_loss_ratio ?? 0) * 10000, max: 100 },
    ];

    const radarData = radarMetrics.map(m => {
        const row: Record<string, any> = { metric: m.key };
        runs.forEach(r => {
            const raw = m.extract(r.suite);
            row[r.run_type] = Math.min((raw / m.max) * 100, 100);
        });
        return row;
    });

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">🔀 Multi-Run Comparison</h1>
                    <p className="text-gray-400 text-sm mt-1">Same suite across different threat scenarios — no smoothing, raw critical data</p>
                </div>
                <select
                    value={selectedSuiteId}
                    onChange={e => setSelectedSuiteId(e.target.value)}
                    className="select-input w-80"
                >
                    <option value="">Select Suite…</option>
                    {uniqueSuiteIds.map(id => (
                        <option key={id} value={id}>{id}</option>
                    ))}
                </select>
            </div>

            {runs.length === 0 ? (
                <div className="card text-center py-12 text-gray-500">
                    <p className="text-lg mb-2">No comparison data available</p>
                    <p className="text-sm">Configure active runs in Settings, then select a suite above.</p>
                </div>
            ) : (
                <>
                    {/* ── Run Cards ── */}
                    <div className="grid grid-cols-3 gap-4">
                        {runs.map(r => {
                            const color = RUN_TYPE_COLORS[r.run_type as RunType] || '#888';
                            const s = r.suite;
                            return (
                                <div key={r.run_id} className="card" style={{ borderTop: `3px solid ${color}` }}>
                                    <div className="flex items-center gap-2 mb-3">
                                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                                        <span className="text-white font-medium">{r.label}</span>
                                        <span className="badge-blue text-xs">{RUN_TYPE_LABELS[r.run_type as RunType]}</span>
                                    </div>
                                    <div className="grid grid-cols-2 gap-2 text-sm">
                                        <div className="text-gray-400">Handshake</div>
                                        <div className="text-white font-mono">{fmt(s.handshake?.handshake_total_duration_ms)} ms</div>
                                        <div className="text-gray-400">Power Avg</div>
                                        <div className="text-white font-mono">{fmt(s.power_energy?.power_avg_w, 3)} W</div>
                                        <div className="text-gray-400">Energy</div>
                                        <div className="text-white font-mono">{fmt(s.power_energy?.energy_total_j, 3)} J</div>
                                        <div className="text-gray-400">Pkt Loss</div>
                                        <div className="text-white font-mono">{fmt(s.data_plane?.packet_loss_ratio, 6)}</div>
                                        <div className="text-gray-400">Drone CPU</div>
                                        <div className="text-white font-mono">{fmt(s.system_drone?.cpu_usage_avg_percent)}%</div>
                                        <div className="text-gray-400">RTT Avg</div>
                                        <div className="text-white font-mono">{fmt(s.latency_jitter?.rtt_avg_ms)} ms</div>
                                        <div className="text-gray-400">Goodput</div>
                                        <div className="text-white font-mono">{fmt(s.data_plane?.goodput_mbps, 3)} Mbps</div>
                                        <div className="text-gray-400">Status</div>
                                        <div className={`font-mono font-bold ${s.validation?.benchmark_pass_fail === 'PASS' ? 'text-green-400' : 'text-red-400'}`}>
                                            {s.validation?.benchmark_pass_fail || '—'}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    {/* ── Side-by-Side Bar Charts ── */}
                    <div className="card">
                        <h2 className="text-lg font-semibold text-white mb-4">📊 Metric Comparison Bars</h2>
                        <div className="grid grid-cols-2 gap-6">
                            {barMetrics.map(m => {
                                const singleData = [barData.find(d => d.metric === m.label)].filter(Boolean);
                                return (
                                    <div key={m.key}>
                                        <h3 className="text-sm text-gray-400 mb-2">{m.label}</h3>
                                        <ResponsiveContainer width="100%" height={120}>
                                            <BarChart data={singleData} layout="vertical">
                                                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                                <XAxis type="number" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                                                <YAxis type="category" dataKey="metric" hide />
                                                <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }} />
                                                {['no_ddos', 'ddos_xgboost', 'ddos_txt'].map(rt => (
                                                    <Bar key={rt} dataKey={rt} fill={RUN_TYPE_COLORS[rt as RunType]} name={RUN_TYPE_LABELS[rt as RunType]} barSize={18} />
                                                ))}
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* ── Radar Chart ── */}
                    {runs.length >= 2 && (
                        <div className="card">
                            <h2 className="text-lg font-semibold text-white mb-4">🕸️ Radar Footprint (Normalized)</h2>
                            <ResponsiveContainer width="100%" height={400}>
                                <RadarChart data={radarData}>
                                    <PolarGrid stroke="#374151" />
                                    <PolarAngleAxis dataKey="metric" tick={{ fill: '#d1d5db', fontSize: 12 }} />
                                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 10 }} />
                                    {['no_ddos', 'ddos_xgboost', 'ddos_txt'].filter(rt => runs.some(r => r.run_type === rt)).map(rt => (
                                        <Radar key={rt} name={RUN_TYPE_LABELS[rt as RunType]} dataKey={rt}
                                            stroke={RUN_TYPE_COLORS[rt as RunType]} fill={RUN_TYPE_COLORS[rt as RunType]}
                                            fillOpacity={0.15} strokeWidth={2} />
                                    ))}
                                    <Legend />
                                    <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }} />
                                </RadarChart>
                            </ResponsiveContainer>
                        </div>
                    )}

                    {/* ── Full Detail Table ── */}
                    <div className="card">
                        <h2 className="text-lg font-semibold text-white mb-4">📋 Complete Metric Table</h2>
                        <div className="overflow-x-auto">
                            <table className="data-table w-full">
                                <thead>
                                    <tr>
                                        <th className="text-left">Category</th>
                                        <th className="text-left">Metric</th>
                                        {runs.map(r => (
                                            <th key={r.run_id} className="text-right">
                                                <span style={{ color: RUN_TYPE_COLORS[r.run_type as RunType] }}>{r.label}</span>
                                            </th>
                                        ))}
                                        {runs.length >= 2 && <th className="text-right">Δ (max-min)</th>}
                                    </tr>
                                </thead>
                                <tbody>
                                    {[
                                        { cat: 'Handshake', metric: 'Total Duration (ms)', extract: (s: any) => s.handshake?.handshake_total_duration_ms },
                                        { cat: 'Handshake', metric: 'Protocol Duration (ms)', extract: (s: any) => s.handshake?.protocol_handshake_duration_ms },
                                        { cat: 'Handshake', metric: 'E2E Duration (ms)', extract: (s: any) => s.handshake?.end_to_end_handshake_duration_ms },
                                        { cat: 'Crypto', metric: 'KEM Keygen (ms)', extract: (s: any) => s.crypto_primitives?.kem_keygen_time_ms },
                                        { cat: 'Crypto', metric: 'KEM Encaps (ms)', extract: (s: any) => s.crypto_primitives?.kem_encapsulation_time_ms },
                                        { cat: 'Crypto', metric: 'KEM Decaps (ms)', extract: (s: any) => s.crypto_primitives?.kem_decapsulation_time_ms },
                                        { cat: 'Crypto', metric: 'Sig Sign (ms)', extract: (s: any) => s.crypto_primitives?.signature_sign_time_ms },
                                        { cat: 'Crypto', metric: 'Sig Verify (ms)', extract: (s: any) => s.crypto_primitives?.signature_verify_time_ms },
                                        { cat: 'Data Plane', metric: 'Goodput (Mbps)', extract: (s: any) => s.data_plane?.goodput_mbps },
                                        { cat: 'Data Plane', metric: 'Packets Sent', extract: (s: any) => s.data_plane?.packets_sent },
                                        { cat: 'Data Plane', metric: 'Packets Dropped', extract: (s: any) => s.data_plane?.packets_dropped },
                                        { cat: 'Data Plane', metric: 'Packet Loss Ratio', extract: (s: any) => s.data_plane?.packet_loss_ratio },
                                        { cat: 'Data Plane', metric: 'Replay Drops', extract: (s: any) => s.data_plane?.drop_replay },
                                        { cat: 'Data Plane', metric: 'Auth Drops', extract: (s: any) => s.data_plane?.drop_auth },
                                        { cat: 'Latency', metric: 'RTT Avg (ms)', extract: (s: any) => s.latency_jitter?.rtt_avg_ms },
                                        { cat: 'Latency', metric: 'RTT P95 (ms)', extract: (s: any) => s.latency_jitter?.rtt_p95_ms },
                                        { cat: 'Latency', metric: 'Jitter Avg (ms)', extract: (s: any) => s.latency_jitter?.jitter_avg_ms },
                                        { cat: 'Power', metric: 'Power Avg (W)', extract: (s: any) => s.power_energy?.power_avg_w },
                                        { cat: 'Power', metric: 'Power Peak (W)', extract: (s: any) => s.power_energy?.power_peak_w },
                                        { cat: 'Power', metric: 'Energy Total (J)', extract: (s: any) => s.power_energy?.energy_total_j },
                                        { cat: 'Power', metric: 'Energy/Handshake (J)', extract: (s: any) => s.power_energy?.energy_per_handshake_j },
                                        { cat: 'System', metric: 'Drone CPU Avg (%)', extract: (s: any) => s.system_drone?.cpu_usage_avg_percent },
                                        { cat: 'System', metric: 'Drone CPU Peak (%)', extract: (s: any) => s.system_drone?.cpu_usage_peak_percent },
                                        { cat: 'System', metric: 'Drone Mem (MB)', extract: (s: any) => s.system_drone?.memory_rss_mb },
                                        { cat: 'System', metric: 'Drone Temp (°C)', extract: (s: any) => s.system_drone?.temperature_c },
                                        { cat: 'MAVLink', metric: 'CRC Errors', extract: (s: any) => s.mavlink_integrity?.mavlink_packet_crc_error_count },
                                        { cat: 'MAVLink', metric: 'Decode Errors', extract: (s: any) => s.mavlink_integrity?.mavlink_decode_error_count },
                                        { cat: 'MAVLink', metric: 'Out of Order', extract: (s: any) => s.mavlink_integrity?.mavlink_out_of_order_count },
                                        { cat: 'MAVLink', metric: 'Duplicates', extract: (s: any) => s.mavlink_integrity?.mavlink_duplicate_count },
                                    ].map((row, i) => {
                                        const values = runs.map(r => row.extract(r.suite));
                                        const numValues = values.filter((v): v is number => v != null && !isNaN(v));
                                        const delta = numValues.length >= 2 ? Math.max(...numValues) - Math.min(...numValues) : null;
                                        return (
                                            <tr key={i}>
                                                <td className="text-gray-500 text-xs">{row.cat}</td>
                                                <td className="text-gray-300">{row.metric}</td>
                                                {values.map((v, j) => (
                                                    <td key={j} className="text-right font-mono text-white">{v != null ? (typeof v === 'number' ? fmt(v, 4) : String(v)) : '—'}</td>
                                                ))}
                                                {runs.length >= 2 && (
                                                    <td className={`text-right font-mono ${delta && delta > 0 ? 'text-yellow-400' : 'text-gray-600'}`}>
                                                        {delta != null ? `±${fmt(delta, 4)}` : '—'}
                                                    </td>
                                                )}
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
