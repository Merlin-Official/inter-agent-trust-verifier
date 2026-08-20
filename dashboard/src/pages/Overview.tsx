import React, { useEffect, useState } from 'react';
import { Activity, ShieldAlert, CheckCircle, XCircle, Shield, Lock, Cpu, Zap } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, AreaChart, Area } from 'recharts';
import api from '../api/client';
import type { DashboardStats, ReputationScore, AuditLog } from '../types';

const Overview: React.FC = () => {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [scores, setScores] = useState<ReputationScore[]>([]);
    const [recentLogs, setRecentLogs] = useState<AuditLog[]>([]);
    const [uptime, setUptime] = useState(0);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [statsRes, scoresRes, logsRes] = await Promise.all([
                    api.get<DashboardStats>('/stats'),
                    api.get<ReputationScore[]>('/reputation'),
                    api.get<AuditLog[]>('/audit-logs'),
                ]);
                setStats(statsRes.data);
                setScores(scoresRes.data);
                setRecentLogs(logsRes.data.slice(0, 5));
            } catch (err) {
                console.error('Failed to fetch overview data', err);
            }
        };
        fetchData();
        const interval = setInterval(fetchData, 5000);
        const uptimeInterval = setInterval(() => setUptime((p) => p + 1), 1000);
        return () => {
            clearInterval(interval);
            clearInterval(uptimeInterval);
        };
    }, []);

    const pieData = stats
        ? [
            { name: 'Accepted', value: stats.total_accepted, fill: '#10b981' },
            { name: 'Rejected', value: stats.total_rejected, fill: '#ef4444' },
        ]
        : [];

    const formatUptime = (s: number) => {
        const h = Math.floor(s / 3600);
        const m = Math.floor((s % 3600) / 60);
        const sec = s % 60;
        return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    };

    return (
        <div className="space-y-8">
            {/* Header with live indicators */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-extrabold tracking-tight">
                        System <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-cyan-400 to-emerald-400">Overview</span>
                    </h2>
                    <p className="text-dark-muted mt-1 text-sm">Deterministic cryptographic verification engine status</p>
                </div>
                <div className="flex items-center gap-6">
                    <div className="flex items-center gap-2 text-sm text-dark-muted">
                        <Zap className="w-4 h-4 text-yellow-400 animate-pulse" />
                        <span className="font-mono text-xs">{formatUptime(uptime)}</span>
                    </div>
                    <div className="flex items-center space-x-2 text-sm">
                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.6)]"></div>
                        <span className="text-emerald-400 font-medium">Engine Active</span>
                    </div>
                </div>
            </div>

            {/* ─── Verification Pipeline Visualization ──────────────────── */}
            <div className="card p-6 bg-gradient-to-r from-dark-card via-slate-800/50 to-dark-card border-dark-border">
                <h3 className="text-sm font-bold text-dark-muted uppercase tracking-wider mb-4 flex items-center">
                    <Shield className="w-4 h-4 mr-2 text-blue-400" />
                    Trust Verification Pipeline
                </h3>
                <div className="flex items-center justify-between overflow-x-auto pb-2">
                    {[
                        { label: 'Ed25519 Sig', icon: <Lock size={16} />, color: 'blue' },
                        { label: 'Agent Status', icon: <Cpu size={16} />, color: 'indigo' },
                        { label: 'Delegation Sig', icon: <Shield size={16} />, color: 'violet' },
                        { label: 'CRL Check', icon: <ShieldAlert size={16} />, color: 'purple' },
                        { label: 'Expiry Check', icon: <Activity size={16} />, color: 'pink' },
                        { label: 'Scope Check', icon: <CheckCircle size={16} />, color: 'cyan' },
                        { label: 'Policy Check', icon: <Shield size={16} />, color: 'teal' },
                        { label: 'Reputation', icon: <Zap size={16} />, color: 'emerald' },
                    ].map((step, i) => (
                        <React.Fragment key={step.label}>
                            <div className="flex flex-col items-center group min-w-[80px]">
                                <div
                                    className={`w-10 h-10 rounded-full flex items-center justify-center bg-${step.color}-500/15 text-${step.color}-400 border border-${step.color}-500/30 group-hover:scale-110 transition-transform shadow-lg`}
                                >
                                    {step.icon}
                                </div>
                                <span className="text-[10px] text-dark-muted mt-2 text-center font-medium">{step.label}</span>
                            </div>
                            {i < 7 && (
                                <div className="flex-1 h-px bg-gradient-to-r from-blue-500/40 to-emerald-500/40 min-w-[20px] mx-1 relative">
                                    <div
                                        className="absolute top-0 left-0 h-full w-8 bg-gradient-to-r from-blue-400 to-cyan-400 rounded-full animate-pulse"
                                        style={{ animationDelay: `${i * 200}ms` }}
                                    ></div>
                                </div>
                            )}
                        </React.Fragment>
                    ))}
                </div>
            </div>

            {/* ─── Stat cards ──────────────────────────────────────────── */}
            {stats ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
                    <StatCard
                        title="Active Agents"
                        value={stats.active_agents}
                        icon={<Cpu className="text-blue-400" size={22} />}
                        trend={`${stats.total_agents} total registered`}
                        gradient="from-blue-500/10 to-blue-500/5"
                    />
                    <StatCard
                        title="Instructions Verified"
                        value={stats.total_instructions}
                        icon={<Shield className="text-indigo-400" size={22} />}
                        trend="All cryptographically signed"
                        gradient="from-indigo-500/10 to-indigo-500/5"
                    />
                    <StatCard
                        title="Acceptance Rate"
                        value={`${stats.acceptance_rate.toFixed(1)}%`}
                        icon={<CheckCircle className="text-emerald-400" size={22} />}
                        trend="Deterministic engine"
                        gradient="from-emerald-500/10 to-emerald-500/5"
                    />
                    <StatCard
                        title="Threats Blocked"
                        value={stats.total_rejected}
                        icon={<XCircle className="text-red-400" size={22} />}
                        trend="MITM, scope, revocation"
                        gradient="from-red-500/10 to-red-500/5"
                    />
                </div>
            ) : (
                <div className="h-32 flex items-center justify-center border border-dark-border rounded-xl bg-dark-card">
                    <div className="flex items-center text-dark-muted">
                        <div className="w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mr-3"></div>
                        Connecting to Trust Engine...
                    </div>
                </div>
            )}

            {/* ─── Charts row ─────────────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Reputation Bar Chart */}
                <div className="card p-6 lg:col-span-2">
                    <h3 className="text-base font-bold mb-4 flex items-center">
                        <Activity className="w-4 h-4 mr-2 text-blue-400" />
                        Agent Trust Scores
                    </h3>
                    <div className="h-56">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={scores} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
                                <XAxis dataKey="agent_name" stroke="#64748b" fontSize={11} tickLine={false} axisLine={false} />
                                <YAxis stroke="#64748b" fontSize={11} tickLine={false} axisLine={false} domain={[0, 120]} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: '8px', fontSize: '12px' }}
                                    itemStyle={{ color: '#f8fafc' }}
                                />
                                <Bar dataKey="score" radius={[6, 6, 0, 0]} barSize={36}>
                                    {scores.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.score >= 50 ? '#3b82f6' : '#ef4444'} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Outcome Pie Chart */}
                <div className="card p-6">
                    <h3 className="text-base font-bold mb-4 flex items-center">
                        <Shield className="w-4 h-4 mr-2 text-emerald-400" />
                        Verification Outcomes
                    </h3>
                    <div className="h-56 flex items-center justify-center">
                        {pieData.some((d) => d.value > 0) ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie
                                        data={pieData}
                                        cx="50%"
                                        cy="50%"
                                        innerRadius={50}
                                        outerRadius={75}
                                        paddingAngle={4}
                                        dataKey="value"
                                        stroke="none"
                                    >
                                        {pieData.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={entry.fill} />
                                        ))}
                                    </Pie>
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: '8px', fontSize: '12px' }}
                                    />
                                </PieChart>
                            </ResponsiveContainer>
                        ) : (
                            <p className="text-dark-muted text-sm">No verification data yet</p>
                        )}
                    </div>
                    <div className="flex justify-center gap-6 mt-2">
                        <div className="flex items-center text-xs">
                            <div className="w-3 h-3 rounded-full bg-emerald-500 mr-2"></div>
                            <span className="text-dark-muted">Accepted</span>
                        </div>
                        <div className="flex items-center text-xs">
                            <div className="w-3 h-3 rounded-full bg-red-500 mr-2"></div>
                            <span className="text-dark-muted">Rejected</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* ─── Recent Activity Feed ───────────────────────────────── */}
            <div className="card p-6">
                <h3 className="text-base font-bold mb-4 flex items-center">
                    <Zap className="w-4 h-4 mr-2 text-yellow-400" />
                    Recent Verification Activity
                </h3>
                <div className="space-y-3">
                    {recentLogs.length > 0 ? (
                        recentLogs.map((log) => (
                            <div key={log.id} className="flex items-center justify-between p-3 rounded-lg bg-dark-bg/50 border border-dark-border hover:border-dark-muted/30 transition-colors">
                                <div className="flex items-center gap-3">
                                    {log.outcome === 'ACCEPTED' ? (
                                        <CheckCircle className="text-emerald-400 flex-shrink-0" size={18} />
                                    ) : (
                                        <XCircle className="text-red-400 flex-shrink-0" size={18} />
                                    )}
                                    <div>
                                        <span className="text-sm font-medium">{log.sender_name}</span>
                                        <span className="text-dark-muted mx-2">→</span>
                                        <span className="text-sm font-medium">{log.receiver_name}</span>
                                        <span className="font-mono text-xs text-blue-300 bg-blue-500/10 px-1.5 py-0.5 rounded ml-2">{log.action}</span>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <span className={`badge text-[10px] ${log.outcome === 'ACCEPTED' ? 'badge-success' : 'badge-danger'}`}>{log.outcome}</span>
                                    <span className="text-xs text-dark-muted font-mono">
                                        {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                    </span>
                                </div>
                            </div>
                        ))
                    ) : (
                        <p className="text-dark-muted text-center text-sm py-4">No activity yet — run simulations to see live results</p>
                    )}
                </div>
            </div>
        </div>
    );
};

const StatCard = ({
    title,
    value,
    icon,
    trend,
    gradient,
}: {
    title: string;
    value: string | number;
    icon: React.ReactNode;
    trend: string;
    gradient: string;
}) => (
    <div className={`card p-5 bg-gradient-to-br ${gradient} hover:scale-[1.02] transition-transform cursor-default`}>
        <div className="flex items-start justify-between">
            <div>
                <p className="text-dark-muted text-xs font-semibold uppercase tracking-wider">{title}</p>
                <h4 className="text-3xl font-extrabold text-white mt-2">{value}</h4>
                <p className="text-[11px] text-dark-muted mt-2">{trend}</p>
            </div>
            <div className="p-3 rounded-xl bg-dark-bg/60">{icon}</div>
        </div>
    </div>
);

export default Overview;
