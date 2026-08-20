export interface Agent {
    id: string;
    name: string;
    description: string;
    public_key: string;
    status: 'ACTIVE' | 'SUSPENDED' | 'REVOKED';
    policy_scope: string[];
    created_at: string;
}

export interface VerificationCheck {
    name: string;
    passed: boolean;
    detail: string;
}

export interface AuditLog {
    id: string;
    instruction_id: string;
    sender_id: string;
    sender_name: string;
    receiver_id: string;
    receiver_name: string;
    action: string;
    outcome: 'ACCEPTED' | 'REJECTED';
    reason?: string;
    checks_passed: string[];
    checks_failed: string[];
    timestamp: string;
}

export interface ReputationScore {
    agent_id: string;
    agent_name: string;
    score: number;
    total_accepted: number;
    total_rejected: number;
    needs_scrutiny: boolean;
}

export interface DashboardStats {
    total_agents: number;
    active_agents: number;
    revoked_agents: number;
    suspended_agents: number;
    total_instructions: number;
    total_accepted: number;
    total_rejected: number;
    acceptance_rate: number;
}
