import React, { useEffect, useState } from 'react';
import { Search, Filter, ShieldCheck, ShieldAlert, Cpu } from 'lucide-react';
import api from '../api/client';
import { AuditLog } from '../types';

const AuditTrail: React.FC = () => {
    const [logs, setLogs] = useState<AuditLog[]>([]);

    const fetchLogs = async () => {
        try {
            const res = await api.get<AuditLog[]>('/audit-logs');
            setLogs(res.data);
        } catch (err) {
            console.error(err);
        }
    };

    useEffect(() => {
        fetchLogs();
        const inv = setInterval(fetchLogs, 3000);
        return () => clearInterval(inv);
    }, []);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Live Audit Trail</h2>
                    <p className="text-dark-muted mt-1">Immutable cryptographic log of inter-agent interactions and verification decisions.</p>
                </div>
            </div>

            <div className="card">
                <div className="p-4 border-b border-dark-border flex space-x-4 bg-white/5">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-dark-muted" size={18} />
                        <input
                            type="text"
                            placeholder="Filter by agent, action, or outcome..."
                            className="w-full bg-dark-bg border border-dark-border rounded-lg pl-10 pr-4 py-2 text-sm focus:outline-none focus:border-accent text-white transition-colors"
                        />
                    </div>
                    <button className="btn-secondary flex items-center">
                        <Filter size={16} className="mr-2" />
                        Filters
                    </button>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse" style={{ tableLayout: 'fixed' }}>
                        <colgroup>
                            <col style={{ width: '110px' }} />
                            <col style={{ width: '180px' }} />
                            <col style={{ width: '180px' }} />
                            <col style={{ width: '110px' }} />
                            <col />
                            <col style={{ width: '120px' }} />
                        </colgroup>
                        <thead>
                            <tr className="bg-dark-bg/50 border-b border-dark-border text-xs uppercase tracking-wider text-dark-muted font-bold">
                                <th className="px-4 py-4">Status</th>
                                <th className="px-4 py-4">Sender</th>
                                <th className="px-4 py-4">Receiver</th>
                                <th className="px-4 py-4">Action</th>
                                <th className="px-4 py-4">Reason</th>
                                <th className="px-4 py-4 text-right">Timestamp</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-dark-border">
                            {logs.map((log) => (
                                <tr key={log.id} className="hover:bg-white/5 transition-colors group">
                                    <td className="px-4 py-4 whitespace-nowrap">
                                        <div className="flex items-center">
                                            {log.outcome === 'ACCEPTED' ? (
                                                <span className="flex items-center text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded-md text-xs font-bold font-mono">
                                                    <ShieldCheck size={14} className="mr-1.5" /> ACCEPT
                                                </span>
                                            ) : (
                                                <span className="flex items-center text-red-400 bg-red-400/10 px-2 py-1 rounded-md text-xs font-bold font-mono">
                                                    <ShieldAlert size={14} className="mr-1.5" /> REJECT
                                                </span>
                                            )}
                                        </div>
                                    </td>
                                    <td className="px-4 py-4">
                                        <div className="flex items-center text-sm font-medium truncate">
                                            <Cpu size={14} className="mr-2 text-dark-muted flex-shrink-0" />
                                            <span className="truncate">{log.sender_name}</span>
                                        </div>
                                        <div className="text-xs text-dark-muted font-mono mt-0.5">{log.sender_id.substring(0, 8)}</div>
                                    </td>
                                    <td className="px-4 py-4">
                                        <div className="flex items-center text-sm font-medium truncate">
                                            <Cpu size={14} className="mr-2 text-dark-muted flex-shrink-0" />
                                            <span className="truncate">{log.receiver_name}</span>
                                        </div>
                                        <div className="text-xs text-dark-muted font-mono mt-0.5">{log.receiver_id.substring(0, 8)}</div>
                                    </td>
                                    <td className="px-4 py-4 whitespace-nowrap">
                                        <span className="font-mono text-sm text-blue-300 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                                            {log.action}
                                        </span>
                                    </td>
                                    <td className="px-4 py-4 text-sm truncate text-dark-muted">
                                        {log.reason || <span className="opacity-50">Fully Validated</span>}
                                    </td>
                                    <td className="px-4 py-4 whitespace-nowrap text-right text-xs text-dark-muted tabular-nums">
                                        {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                    </td>
                                </tr>
                            ))}
                            {logs.length === 0 && (
                                <tr>
                                    <td colSpan={6} className="px-4 py-8 text-center text-dark-muted">
                                        <div className="flex flex-col items-center justify-center">
                                            <ShieldCheck className="w-12 h-12 opacity-20 mb-3" />
                                            No cryptographic instruction signatures recorded yet.
                                        </div>
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default AuditTrail;
