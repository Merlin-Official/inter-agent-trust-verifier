import React, { useState, useEffect } from 'react';
import { Play, ShieldAlert, Key, AlertTriangle, ShieldCheck } from 'lucide-react';
import api from '../api/client';
import { Agent } from '../types';

const Simulation: React.FC = () => {
    const [agents, setAgents] = useState<Agent[]>([]);
    const [logs, setLogs] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const init = async () => {
            try {
                const res = await api.get<Agent[]>('/agents');
                setAgents(res.data);
            } catch (err) {
                console.error(err);
            }
        };
        init();
    }, []);

    const addLog = (msg: string) => {
        setLogs(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev]);
    };

    const getAgents = async () => {
        addLog("Provisioning fresh agents for simulation run...");
        const nameA = `Sim-Agent-A-${Math.floor(Math.random() * 900 + 100)}`;
        const nameB = `Sim-Agent-B-${Math.floor(Math.random() * 900 + 100)}`;
        const resA = await api.post('/agents/register', { name: nameA, policy_scope: ["query_db"] });
        const resB = await api.post('/agents/register', { name: nameB, policy_scope: ["query_db"] });
        return { sender: resA.data, receiver: resB.data };
    };

    const runSimulation = async (type: 'VALID' | 'MITM' | 'SCOPE' | 'REVOKED') => {
        setLoading(true);
        try {
            const { sender, receiver } = await getAgents();
            addLog(`Agents ready. Sender: ${sender.agent.name}, Receiver: ${receiver.agent.name}`);

            // Issue delegation
            addLog(`Issuing delegation token to ${sender.agent.name} for action: query_db`);
            const delegationRes = await api.post('/delegations', {
                issuer_id: sender.agent.id,
                issuer_private_key: sender.private_key,
                subject_id: sender.agent.id,
                allowed_actions: ["query_db"],
                expires_in_hours: 24
            });
            const token = delegationRes.data;

            // Handle specific scenario setups
            let actionToSign = "query_db";
            if (type === 'SCOPE') {
                actionToSign = "delete_db";
                addLog("SCENARIO (SCOPE): Sender attempting unauthorized action 'delete_db'");
            }

            if (type === 'REVOKED') {
                addLog("SCENARIO (REVOKED): Suspending sender's credentials in CRL...");
                await api.post(`/revocation/${sender.agent.id}/revoke`, {
                    reason: "Simulation manual block",
                    revoked_by: "simulation_runner"
                });
            }

            // Sign Instruction
            addLog("Sender generating Ed25519 signature over instruction payload...");
            const signRes = await api.post('/instructions/sign', {
                sender_id: sender.agent.id,
                sender_private_key: sender.private_key,
                receiver_id: receiver.agent.id,
                action: actionToSign,
                payload: { query: "SELECT * FROM users" },
                delegation_token_id: token.token_id
            });

            let signedInstruction = signRes.data;

            if (type === 'MITM') {
                addLog("SCENARIO (MITM): Intercepting instruction in transit and altering payload...");
                signedInstruction.action = "delete_db";
            }

            // Verify
            addLog("Receiver forwarding cryptographically signed instruction to Trust Verifier Engine...");
            const verifyRes = await api.post('/instructions/verify', signedInstruction);
            const outcome = verifyRes.data;

            if (outcome.accepted) {
                addLog(`>> OUTCOME: ACCEPTED. Trust score increased.`);
            } else {
                addLog(`>> OUTCOME: REJECTED. Reason: ${outcome.rejection_reason}`);
            }

        } catch (err: any) {
            addLog(`Error during simulation: ${err.message || String(err)}`);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
            <div className="lg:col-span-1 space-y-4">
                <h2 className="text-xl font-bold mb-6">Threat Simulations</h2>

                <SimulationCard
                    title="Valid Identity & Scope"
                    desc="Simulates a fully valid interaction. Ed25519 signature verified, delegation accepted, reputation increased."
                    icon={<ShieldCheck className="text-emerald-400" />}
                    onClick={() => runSimulation('VALID')}
                    loading={loading}
                    color="emerald"
                />
                <SimulationCard
                    title="MITM / Tampering"
                    desc="Cryptographic signature applied, but instruction action is modified in transit. Engine should instantly reject."
                    icon={<AlertTriangle className="text-warning" />}
                    onClick={() => runSimulation('MITM')}
                    loading={loading}
                    color="warning"
                />
                <SimulationCard
                    title="Scope Exceeded"
                    desc="Agent cryptographic identity is valid, but they attempt an action outside their delegation policy bounds."
                    icon={<ShieldAlert className="text-indigo-400" />}
                    onClick={() => runSimulation('SCOPE')}
                    loading={loading}
                    color="indigo"
                />
                <SimulationCard
                    title="Revoked Credentials"
                    desc="Agent attempts validly signed instruction, but their credentials were independently revoked in the CRL."
                    icon={<Key className="text-red-400" />}
                    onClick={() => runSimulation('REVOKED')}
                    loading={loading}
                    color="red"
                />
            </div>

            <div className="lg:col-span-2">
                <div className="card h-full flex flex-col bg-slate-900 border-slate-700">
                    <div className="p-4 border-b border-slate-700 bg-slate-900 flex justify-between items-center rounded-t-xl">
                        <h3 className="font-mono text-sm tracking-wider text-slate-400 flex items-center">
                            <Play size={14} className="mr-2" />
                            SIMULATION_TERMINAL_OUTPUT
                        </h3>
                        <button onClick={() => setLogs([])} className="text-xs text-slate-500 hover:text-slate-300">Clear</button>
                    </div>
                    <div className="p-4 flex-1 overflow-y-auto font-mono text-xs space-y-2 max-h-[70vh]">
                        {logs.length === 0 ? (
                            <p className="text-slate-600 italic">No simulation running. Select a scenario from the panel.</p>
                        ) : (
                            logs.map((log, i) => (
                                <div key={i} className={`
                  ${log.includes('OUTCOME: ACCEPTED') ? 'text-emerald-400 font-bold' : ''}
                  ${log.includes('OUTCOME: REJECTED') ? 'text-red-400 font-bold' : ''}
                  ${log.includes('SCENARIO') ? 'text-warning font-bold' : ''}
                  ${!log.includes('OUTCOME') && !log.includes('SCENARIO') ? 'text-slate-300' : ''}
                `}>
                                    {log}
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

const SimulationCard = ({ title, desc, icon, onClick, loading, color }: any) => (
    <div className="card p-5 border-l-4 hover:bg-white/5 transition-colors cursor-pointer group" style={{ borderLeftColor: `var(--color-${color})` }} onClick={!loading ? onClick : undefined}>
        <div className="flex justify-between items-start mb-2">
            <div className="flex items-center">
                {icon}
                <h3 className="font-bold ml-3">{title}</h3>
            </div>
            <button disabled={loading} className={`btn-secondary text-xs opacity-0 group-hover:opacity-100 transition-opacity ${loading ? 'opacity-50' : ''}`}>
                Run
            </button>
        </div>
        <p className="text-sm text-dark-muted mt-2">{desc}</p>
    </div>
);

export default Simulation;
