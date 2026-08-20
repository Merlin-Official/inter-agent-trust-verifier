import React, { useEffect, useState } from 'react';
import { Key, ShieldOff, ShieldAlert, Plus } from 'lucide-react';
import api from '../api/client';
import { Agent } from '../types';

const Agents: React.FC = () => {
    const [agents, setAgents] = useState<Agent[]>([]);

    const fetchAgents = async () => {
        try {
            const res = await api.get<Agent[]>('/agents');
            setAgents(res.data);
        } catch (err) {
            console.error(err);
        }
    };

    useEffect(() => {
        fetchAgents();
        const inv = setInterval(fetchAgents, 5000);
        return () => clearInterval(inv);
    }, []);

    const handleCreateDemo = async () => {
        try {
            await api.post('/agents/register', {
                name: `Agent-${Math.floor(Math.random() * 1000)}`,
                description: 'Dynamically provisioned agent',
                policy_scope: ['query_data', 'read_logs']
            });
            fetchAgents();
        } catch (err) {
            console.error(err);
        }
    };

    const handleRevoke = async (agentId: string) => {
        try {
            await api.post(`/revocation/${agentId}/revoke`, {
                reason: 'Manual suspension via dashboard',
                revoked_by: 'admin'
            });
            fetchAgents();
        } catch (err) {
            console.error(err);
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Agent Registry</h2>
                    <p className="text-dark-muted mt-1">Manage agent cryptographic identities and access status.</p>
                </div>
                <button onClick={handleCreateDemo} className="btn-primary flex items-center">
                    <Plus size={16} className="mr-2" />
                    Provision Agent
                </button>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                {agents.map((agent) => (
                    <div key={agent.id} className="card p-6 flex flex-col justify-between">
                        <div>
                            <div className="flex justify-between items-start mb-4">
                                <div className="flex items-center space-x-3">
                                    <div className={`w-12 h-12 rounded-full flex items-center justify-center ${agent.status === 'ACTIVE' ? 'bg-blue-500/10 text-blue-400' : 'bg-red-500/10 text-red-400'}`}>
                                        {agent.status === 'ACTIVE' ? <Key size={24} /> : <ShieldOff size={24} />}
                                    </div>
                                    <div>
                                        <h3 className="text-lg font-bold">{agent.name}</h3>
                                        <p className="text-xs text-dark-muted font-mono">{agent.id.substring(0, 13)}...</p>
                                    </div>
                                </div>
                                <span className={`badge ${agent.status === 'ACTIVE' ? 'badge-success' : 'badge-danger'}`}>
                                    {agent.status}
                                </span>
                            </div>

                            <div className="bg-dark-bg p-3 rounded-lg border border-dark-border mb-4">
                                <p className="text-xs text-dark-muted mb-1 uppercase font-semibold tracking-wider">Public Key (Ed25519)</p>
                                <div className="font-mono text-xs text-emerald-400 truncate opacity-80 select-all">
                                    {agent.public_key.replace(/-----BEGIN PUBLIC KEY-----|-----END PUBLIC KEY-----|\n/g, '').trim()}
                                </div>
                            </div>

                            <div className="flex flex-wrap gap-2 mb-4">
                                {agent.policy_scope.map((scope, idx) => (
                                    <span key={idx} className="badge badge-info bg-indigo-500/10 text-indigo-400 border-indigo-500/30">
                                        {scope}
                                    </span>
                                ))}
                            </div>
                        </div>

                        <div className="flex items-center justify-between mt-2 pt-4 border-t border-dark-border">
                            <span className="text-xs text-dark-muted">Added {new Date(agent.created_at).toLocaleDateString()}</span>
                            {agent.status === 'ACTIVE' ? (
                                <button onClick={() => handleRevoke(agent.id)} className="btn-danger text-xs px-3 py-1.5 flex items-center">
                                    <ShieldAlert size={14} className="mr-1" /> Revoke Keys
                                </button>
                            ) : (
                                <span className="text-xs text-red-400/70 italic flex items-center">
                                    Credentials Revoked
                                </span>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default Agents;
