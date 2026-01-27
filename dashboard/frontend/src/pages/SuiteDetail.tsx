/**
 * Suite Detail Page - Deep-dive into single suite metrics
 */

import { useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useDashboardStore } from '../state/store';
import type { ReliabilityClass, MetricStatus } from '../types/metrics';

// Reliability badge component
function ReliabilityBadge({ reliability }: { reliability: ReliabilityClass }) {
    const classes: Record<ReliabilityClass, string> = {
        VERIFIED: 'badge-verified',
        CONDITIONAL: 'badge-conditional',
        DEPRECATED: 'badge-deprecated',
        MISSING: 'badge-missing',
    };
    return <span className={classes[reliability]}>{reliability}</span>;
}

// Metric display component
function MetricValue({
    value,
    unit = '',
    status,
}: {
    value: number | string | boolean | null | undefined;
    unit?: string;
    status?: MetricStatus;
}) {
    if (status?.status === 'invalid') {
        return <span className="text-red-400 italic">Invalid{status.reason ? ` (${status.reason})` : ''}</span>;
    }
    if (status?.status === 'not_implemented') {
        return <span className="text-gray-500 italic">Not implemented</span>;
    }
    if (status?.status === 'not_collected') {
        return <span className="text-gray-500 italic">Not collected</span>;
    }
    if (value === null || value === undefined || value === '') {
        return <span className="text-gray-500 italic">Not collected</span>;
    }
    if (typeof value === 'boolean') {
        return <span className={value ? 'text-green-400' : 'text-red-400'}>{value ? 'Yes' : 'No'}</span>;
    }
    if (typeof value === 'number') {
        return <span className="font-mono">{value.toFixed(2)} {unit}</span>;
    }
    return <span>{value} {unit}</span>;
}

// Metric card component
function MetricCard({ title, children, reliability = 'VERIFIED' as ReliabilityClass }: { title: string; children: React.ReactNode; reliability?: ReliabilityClass }) {
    return (
        <div className="card">
            <div className="flex items-center justify-between mb-3">
                <h3 className="card-header mb-0">{title}</h3>
                <ReliabilityBadge reliability={reliability} />
            </div>
            {children}
        </div>
    );
}

export default function SuiteDetail() {
    const { suiteKey } = useParams<{ suiteKey: string }>();
    const { selectedSuite, isLoading, fetchSuiteDetail } = useDashboardStore();

    useEffect(() => {
        if (suiteKey) {
            fetchSuiteDetail(decodeURIComponent(suiteKey));
        }
    }, [suiteKey, fetchSuiteDetail]);

    if (isLoading || !selectedSuite) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-gray-400">Loading suite details...</div>
            </div>
        );
    }

    const suite = selectedSuite;
    const statusMap = suite.validation.metric_status || {};
    const getStatus = (path: string): MetricStatus | undefined => statusMap[path];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Link to="/suites" className="text-gray-400 hover:text-white">← Back</Link>
                <h1 className="text-2xl font-bold">{suite.run_context.suite_id}</h1>
                <span className={suite.validation.benchmark_pass_fail === 'PASS'
                    ? 'badge-verified'
                    : suite.validation.benchmark_pass_fail === 'FAIL'
                        ? 'bg-red-500/20 text-red-400 px-2 py-0.5 rounded text-xs'
                        : 'badge-missing'}>
                    {suite.validation.benchmark_pass_fail || 'Not collected'}
                </span>
            </div>

            {/* A. Run Context */}
            <MetricCard title="A. Run Context">
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                    <div><span className="text-gray-400">Run ID:</span> <span className="font-mono">{suite.run_context.run_id}</span></div>
                    <div><span className="text-gray-400">Suite Index:</span> {suite.run_context.suite_index}</div>
                    <div><span className="text-gray-400">Git Commit:</span> <span className="font-mono"><MetricValue value={suite.run_context.git_commit_hash} status={getStatus('run_context.git_commit_hash')} /></span></div>
                    <div><span className="text-gray-400">GCS Host:</span> <MetricValue value={suite.run_context.gcs_hostname} status={getStatus('run_context.gcs_hostname')} /></div>
                    <div><span className="text-gray-400">Drone Host:</span> <MetricValue value={suite.run_context.drone_hostname} status={getStatus('run_context.drone_hostname')} /></div>
                    <div><span className="text-gray-400">Start Time:</span> {suite.run_context.run_start_time_wall ? new Date(suite.run_context.run_start_time_wall).toLocaleString() : 'Not collected'}</div>
                </div>
            </MetricCard>

            {/* B. Crypto Identity */}
            <MetricCard title="B. Crypto Identity">
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                    <div><span className="text-gray-400">KEM:</span> <span className="font-mono text-blue-400"><MetricValue value={suite.crypto_identity.kem_algorithm} status={getStatus('crypto_identity.kem_algorithm')} /></span></div>
                    <div><span className="text-gray-400">KEM Family:</span> <MetricValue value={suite.crypto_identity.kem_family} status={getStatus('crypto_identity.kem_family')} /></div>
                    <div><span className="text-gray-400">Signature:</span> <span className="font-mono text-purple-400"><MetricValue value={suite.crypto_identity.sig_algorithm} status={getStatus('crypto_identity.sig_algorithm')} /></span></div>
                    <div><span className="text-gray-400">Sig Family:</span> <MetricValue value={suite.crypto_identity.sig_family} status={getStatus('crypto_identity.sig_family')} /></div>
                    <div><span className="text-gray-400">AEAD:</span> <span className="font-mono"><MetricValue value={suite.crypto_identity.aead_algorithm} status={getStatus('crypto_identity.aead_algorithm')} /></span></div>
                    <div><span className="text-gray-400">Security Level:</span> <MetricValue value={suite.crypto_identity.suite_security_level} status={getStatus('crypto_identity.suite_security_level')} /></div>
                </div>
            </MetricCard>

            {/* D. Handshake */}
            <MetricCard title="D. Handshake Metrics">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                        <div className="text-gray-400 text-xs">Total Duration</div>
                        <div className="text-xl"><MetricValue value={suite.handshake.handshake_total_duration_ms} unit="ms" /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Success</div>
                        <div className="text-xl"><MetricValue value={suite.handshake.handshake_success} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Failure Reason</div>
                        <div><MetricValue value={suite.handshake.handshake_failure_reason} /></div>
                    </div>
                </div>
            </MetricCard>

            {/* M. Control Plane */}
            <MetricCard title="M. Control Plane">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                        <div className="text-gray-400 text-xs">Scheduler Tick</div>
                        <div className="font-mono"><MetricValue value={suite.control_plane.scheduler_tick_interval_ms} unit="ms" /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Policy Name</div>
                        <div className="font-mono"><MetricValue value={suite.control_plane.policy_name} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Policy State</div>
                        <div className="font-mono"><MetricValue value={suite.control_plane.policy_state} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Action Type</div>
                        <div className="font-mono"><MetricValue value={suite.control_plane.scheduler_action_type} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Action Reason</div>
                        <div className="font-mono"><MetricValue value={suite.control_plane.scheduler_action_reason} /></div>
                    </div>
                </div>
            </MetricCard>

            {/* G. Data Plane */}
            <MetricCard title="G. Data Plane">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                        <div className="text-gray-400 text-xs">Packets Sent</div>
                        <div className="font-mono"><MetricValue value={suite.data_plane.packets_sent} status={getStatus('data_plane')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Packets Received</div>
                        <div className="font-mono"><MetricValue value={suite.data_plane.packets_received} status={getStatus('data_plane')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Packets Dropped</div>
                        <div className="font-mono">
                            <MetricValue value={suite.data_plane.packets_dropped} status={getStatus('data_plane')} />
                        </div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Delivery Ratio</div>
                        <div className="font-mono">
                            <MetricValue value={suite.data_plane.packet_delivery_ratio !== null && suite.data_plane.packet_delivery_ratio !== undefined ? suite.data_plane.packet_delivery_ratio * 100 : null} unit="%" status={getStatus('data_plane')} />
                        </div>
                    </div>
                </div>
            </MetricCard>

            {/* H. Latency & Jitter */}
            <MetricCard title="H. Latency & Jitter">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                        <div className="text-gray-400 text-xs">One-way Avg</div>
                        <div className="font-mono"><MetricValue value={suite.latency_jitter.one_way_latency_avg_ms} unit="ms" status={getStatus('latency_jitter.one_way_latency_avg_ms')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">One-way P95</div>
                        <div className="font-mono"><MetricValue value={suite.latency_jitter.one_way_latency_p95_ms} unit="ms" status={getStatus('latency_jitter.one_way_latency_avg_ms')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Jitter Avg</div>
                        <div className="font-mono"><MetricValue value={suite.latency_jitter.jitter_avg_ms} unit="ms" status={getStatus('latency_jitter.one_way_latency_avg_ms')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Jitter P95</div>
                        <div className="font-mono"><MetricValue value={suite.latency_jitter.jitter_p95_ms} unit="ms" status={getStatus('latency_jitter.one_way_latency_avg_ms')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">RTT Avg</div>
                        <div className="font-mono"><MetricValue value={suite.latency_jitter.rtt_avg_ms} unit="ms" status={getStatus('latency_jitter.rtt_avg_ms')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">RTT P95</div>
                        <div className="font-mono"><MetricValue value={suite.latency_jitter.rtt_p95_ms} unit="ms" status={getStatus('latency_jitter.rtt_avg_ms')} /></div>
                    </div>
                </div>
            </MetricCard>

            {/* K. MAVLink Integrity */}
            <MetricCard
                title="K. MAVLink Integrity"
                reliability={suite.mavlink_integrity.mavlink_out_of_order_count && suite.mavlink_integrity.mavlink_out_of_order_count > 0 ? 'CONDITIONAL' : 'VERIFIED'}
            >
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                        <div className="text-gray-400 text-xs">Out of Order</div>
                        <div className="font-mono">
                            <MetricValue value={suite.mavlink_integrity.mavlink_out_of_order_count} status={getStatus('mavlink_integrity')} />
                        </div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">CRC Errors</div>
                        <div className="font-mono">
                            <MetricValue value={suite.mavlink_integrity.mavlink_packet_crc_error_count} status={getStatus('mavlink_integrity')} />
                        </div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Decode Errors</div>
                        <div className="font-mono">
                            <MetricValue value={suite.mavlink_integrity.mavlink_decode_error_count} status={getStatus('mavlink_integrity')} />
                        </div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Duplicates</div>
                        <div className="font-mono"><MetricValue value={suite.mavlink_integrity.mavlink_duplicate_count} status={getStatus('mavlink_integrity')} /></div>
                    </div>
                </div>
            </MetricCard>

            {/* N. System Resources Drone */}
            <MetricCard title="N. System Resources (Drone)">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                        <div className="text-gray-400 text-xs">CPU Avg</div>
                        <div className="font-mono"><MetricValue value={suite.system_drone.cpu_usage_avg_percent} unit="%" status={getStatus('system_drone')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">CPU Peak</div>
                        <div className="font-mono"><MetricValue value={suite.system_drone.cpu_usage_peak_percent} unit="%" status={getStatus('system_drone')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Memory RSS</div>
                        <div className="font-mono"><MetricValue value={suite.system_drone.memory_rss_mb} unit="MB" status={getStatus('system_drone')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Temperature</div>
                        <div className="font-mono"><MetricValue value={suite.system_drone.temperature_c} unit="°C" status={getStatus('system_drone')} /></div>
                    </div>
                </div>
            </MetricCard>

            {/* O. System Resources GCS */}
            <MetricCard title="O. System Resources (GCS)">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                        <div className="text-gray-400 text-xs">CPU Avg</div>
                        <div className="font-mono"><MetricValue value={suite.system_gcs.cpu_usage_avg_percent} unit="%" status={getStatus('system_gcs')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">CPU Peak</div>
                        <div className="font-mono"><MetricValue value={suite.system_gcs.cpu_usage_peak_percent} unit="%" status={getStatus('system_gcs')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Memory RSS</div>
                        <div className="font-mono"><MetricValue value={suite.system_gcs.memory_rss_mb} unit="MB" status={getStatus('system_gcs')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Temperature</div>
                        <div className="font-mono"><MetricValue value={suite.system_gcs.temperature_c} unit="°C" status={getStatus('system_gcs')} /></div>
                    </div>
                </div>
            </MetricCard>

            {/* P. Power & Energy */}
            <MetricCard title="P. Power & Energy">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                        <div className="text-gray-400 text-xs">Sensor Type</div>
                        <div className="font-mono"><MetricValue value={suite.power_energy.power_sensor_type} status={getStatus('power_energy')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Power Avg</div>
                        <div className="text-xl text-green-400"><MetricValue value={suite.power_energy.power_avg_w} unit="W" status={getStatus('power_energy')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Power Peak</div>
                        <div className="font-mono"><MetricValue value={suite.power_energy.power_peak_w} unit="W" status={getStatus('power_energy')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Energy Total</div>
                        <div className="text-xl text-blue-400"><MetricValue value={suite.power_energy.energy_total_j} unit="J" status={getStatus('power_energy')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Voltage Avg</div>
                        <div className="font-mono"><MetricValue value={suite.power_energy.voltage_avg_v} unit="V" status={getStatus('power_energy')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Current Avg</div>
                        <div className="font-mono"><MetricValue value={suite.power_energy.current_avg_a} unit="A" status={getStatus('power_energy')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Energy/Handshake</div>
                        <div className="font-mono"><MetricValue value={suite.power_energy.energy_per_handshake_j} unit="J" status={getStatus('power_energy')} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Sampling Rate</div>
                        <div className="font-mono"><MetricValue value={suite.power_energy.power_sampling_rate_hz} unit="Hz" status={getStatus('power_energy')} /></div>
                    </div>
                </div>
            </MetricCard>

            {/* R. Validation */}
            <MetricCard title="R. Validation">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                        <div className="text-gray-400 text-xs">Collected Samples</div>
                        <div className="font-mono"><MetricValue value={suite.validation.collected_samples} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Lost Samples</div>
                        <div className="font-mono"><MetricValue value={suite.validation.lost_samples} /></div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Success Rate</div>
                        <div className="font-mono">
                            <MetricValue value={suite.validation.success_rate_percent !== null && suite.validation.success_rate_percent !== undefined ? suite.validation.success_rate_percent : null} unit="%" />
                        </div>
                    </div>
                    <div>
                        <div className="text-gray-400 text-xs">Result</div>
                        <div className={suite.validation.benchmark_pass_fail === 'PASS' ? 'text-green-400' : 'text-red-400'}>
                            {suite.validation.benchmark_pass_fail || '—'}
                        </div>
                    </div>
                </div>
            </MetricCard>
        </div>
    );
}
