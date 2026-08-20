"""
Comprehensive test suite for the Inter-Agent Trust Verifier.

Maps directly to the success criteria from PS-5.2:
  Test 1: Valid signed instruction from authorised Agent A → ACCEPTED
  Test 2: Unsigned instruction (MITM simulation) → REJECTED
  Test 3: Instruction exceeding delegation scope → REJECTED
  Test 4: Revoked credential instruction → REJECTED
  Test 5: Expired delegation instruction → REJECTED (bonus)
  Test 6: Reputation scoring tracks correctly
  Test 7: Crypto operations unit tests
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import init_db, engine, Base
from app.core.crypto import generate_keypair, sign_message, verify_signature, canonical_json
from app.core.instruction import create_signed_instruction, get_instruction_signing_bytes
from app.core.delegation import (
    create_delegation_token,
    verify_delegation_token_signature,
    is_token_expired,
    is_action_in_scope,
)
from app.core.verifier import TrustVerifier, AgentInfo, VerificationResult


# ─── Fixtures ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create fresh database tables for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def registered_agents(client: AsyncClient):
    """Register Agent A (sender) and Agent B (receiver)."""
    # Register Agent A
    resp_a = await client.post("/api/v1/agents/register", json={
        "name": "Agent-A",
        "description": "Requesting agent",
        "policy_scope": ["send_email", "read_data", "generate_report"],
    })
    assert resp_a.status_code == 201
    agent_a = resp_a.json()

    # Register Agent B
    resp_b = await client.post("/api/v1/agents/register", json={
        "name": "Agent-B",
        "description": "Executing agent",
        "policy_scope": ["send_email", "read_data", "generate_report"],
    })
    assert resp_b.status_code == 201
    agent_b = resp_b.json()

    return {
        "agent_a": agent_a,
        "agent_b": agent_b,
    }


@pytest_asyncio.fixture
async def delegation_setup(client: AsyncClient, registered_agents):
    """Create a delegation token from Agent A to instruct Agent B."""
    agents = registered_agents
    agent_a = agents["agent_a"]

    # Create delegation token
    resp = await client.post("/api/v1/delegations", json={
        "issuer_id": agent_a["agent"]["id"],
        "issuer_private_key": agent_a["private_key"],
        "subject_id": agent_a["agent"]["id"],
        "allowed_actions": ["send_email", "read_data"],
        "expires_in_hours": 24,
    })
    assert resp.status_code == 201
    delegation = resp.json()

    return {
        **agents,
        "delegation": delegation,
    }


# ─── Test 7: Crypto Unit Tests ────────────────────────────────────────

class TestCryptoOperations:
    """Unit tests for Ed25519 cryptographic operations."""

    def test_generate_keypair(self):
        private_key, public_key = generate_keypair()
        assert "BEGIN PRIVATE KEY" in private_key
        assert "BEGIN PUBLIC KEY" in public_key

    def test_sign_and_verify(self):
        private_key, public_key = generate_keypair()
        message = b"test message"
        signature = sign_message(private_key, message)
        assert verify_signature(public_key, message, signature)

    def test_verify_wrong_key_fails(self):
        private_key1, public_key1 = generate_keypair()
        _, public_key2 = generate_keypair()
        message = b"test message"
        signature = sign_message(private_key1, message)
        # Different public key should fail
        assert not verify_signature(public_key2, message, signature)

    def test_verify_tampered_message_fails(self):
        private_key, public_key = generate_keypair()
        message = b"original message"
        signature = sign_message(private_key, message)
        # Tampered message should fail
        assert not verify_signature(public_key, b"tampered message", signature)

    def test_canonical_json_deterministic(self):
        data1 = {"b": 2, "a": 1}
        data2 = {"a": 1, "b": 2}
        assert canonical_json(data1) == canonical_json(data2)


# ─── Test: Signed Instruction ─────────────────────────────────────────

class TestSignedInstruction:
    """Tests for instruction signing and serialization."""

    def test_create_signed_instruction(self):
        private_key, public_key = generate_keypair()
        signed = create_signed_instruction(
            private_key_pem=private_key,
            sender_id="agent-a",
            receiver_id="agent-b",
            action="send_email",
            delegation_token_id="token-1",
            payload={"to": "user@example.com"},
        )
        assert signed.instruction_id
        assert signed.signature
        assert signed.action == "send_email"

    def test_instruction_signature_verifiable(self):
        private_key, public_key = generate_keypair()
        signed = create_signed_instruction(
            private_key_pem=private_key,
            sender_id="agent-a",
            receiver_id="agent-b",
            action="send_email",
            delegation_token_id="token-1",
        )
        signing_bytes = get_instruction_signing_bytes(signed)
        assert verify_signature(public_key, signing_bytes, signed.signature)


# ─── Test: Delegation Tokens ─────────────────────────────────────────

class TestDelegationTokens:
    """Tests for delegation token creation and validation."""

    def test_create_delegation_token(self):
        private_key, public_key = generate_keypair()
        expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        token = create_delegation_token(
            issuer_private_key_pem=private_key,
            issuer_id="admin",
            subject_id="agent-a",
            allowed_actions=["send_email", "read_data"],
            expires_at=expires,
        )
        assert token.token_id
        assert token.signature
        assert verify_delegation_token_signature(public_key, token)

    def test_expired_token(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert is_token_expired(past) is True

    def test_valid_token_not_expired(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        assert is_token_expired(future) is False

    def test_action_in_scope(self):
        assert is_action_in_scope("send_email", ["send_email", "read_data"])
        assert not is_action_in_scope("delete_db", ["send_email", "read_data"])

    def test_wildcard_scope(self):
        assert is_action_in_scope("anything", ["*"])


# ─── Trust Verifier Unit Tests ────────────────────────────────────────

class TestTrustVerifier:
    """Unit tests for the deterministic trust verifier engine."""

    def setup_method(self):
        self.verifier = TrustVerifier()
        self.sender_private, self.sender_public = generate_keypair()
        self.issuer_private, self.issuer_public = generate_keypair()

    def _make_delegation(self, actions=None, expires_hours=24):
        if actions is None:
            actions = ["send_email", "read_data"]
        expires = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()
        return create_delegation_token(
            issuer_private_key_pem=self.issuer_private,
            issuer_id="issuer",
            subject_id="sender",
            allowed_actions=actions,
            expires_at=expires,
        )

    def _make_instruction(self, action="send_email", token_id="token-1"):
        return create_signed_instruction(
            private_key_pem=self.sender_private,
            sender_id="sender",
            receiver_id="receiver",
            action=action,
            delegation_token_id=token_id,
        )

    def _sender_info(self, status="ACTIVE"):
        return AgentInfo(
            id="sender",
            name="Agent-A",
            public_key=self.sender_public,
            status=status,
            policy_scope=["send_email", "read_data"],
        )

    def _receiver_info(self, policy=None):
        if policy is None:
            policy = ["send_email", "read_data", "generate_report"]
        return AgentInfo(
            id="receiver",
            name="Agent-B",
            public_key="",
            status="ACTIVE",
            policy_scope=policy,
        )

    def test_valid_instruction_accepted(self):
        """Test 1: Valid signed instruction → ACCEPTED"""
        delegation = self._make_delegation()
        instruction = self._make_instruction(token_id=delegation.token_id)
        result = self.verifier.verify(
            instruction=instruction,
            sender=self._sender_info(),
            receiver=self._receiver_info(),
            delegation_token=delegation,
            issuer_public_key=self.issuer_public,
        )
        assert result.accepted is True
        assert len(result.checks_failed) == 0

    def test_tampered_instruction_rejected(self):
        """Test 2: MITM / tampered instruction → REJECTED"""
        delegation = self._make_delegation()
        instruction = self._make_instruction(token_id=delegation.token_id)

        # Tamper with the action (simulate MITM)
        from app.core.instruction import SignedInstruction
        tampered = SignedInstruction(
            instruction_id=instruction.instruction_id,
            sender_id=instruction.sender_id,
            receiver_id=instruction.receiver_id,
            action="delete_database",  # ← TAMPERED
            payload=instruction.payload,
            delegation_token_id=instruction.delegation_token_id,
            timestamp=instruction.timestamp,
            signature=instruction.signature,  # ← Original signature
        )

        result = self.verifier.verify(
            instruction=tampered,
            sender=self._sender_info(),
            receiver=self._receiver_info(),
            delegation_token=delegation,
            issuer_public_key=self.issuer_public,
        )
        assert result.accepted is False
        assert "signature" in result.rejection_reason.lower()

    def test_scope_exceeded_rejected(self):
        """Test 3: Action outside delegation scope → REJECTED"""
        delegation = self._make_delegation(actions=["send_email"])
        instruction = self._make_instruction(
            action="delete_database",  # Not in allowed actions
            token_id=delegation.token_id,
        )
        result = self.verifier.verify(
            instruction=instruction,
            sender=self._sender_info(),
            receiver=self._receiver_info(),
            delegation_token=delegation,
            issuer_public_key=self.issuer_public,
        )
        assert result.accepted is False
        assert "scope" in result.rejection_reason.lower()

    def test_revoked_agent_rejected(self):
        """Test 4: Revoked agent → REJECTED"""
        delegation = self._make_delegation()
        instruction = self._make_instruction(token_id=delegation.token_id)
        result = self.verifier.verify(
            instruction=instruction,
            sender=self._sender_info(status="REVOKED"),
            receiver=self._receiver_info(),
            delegation_token=delegation,
            issuer_public_key=self.issuer_public,
        )
        assert result.accepted is False
        assert "revoked" in result.rejection_reason.lower()

    def test_expired_delegation_rejected(self):
        """Test 5: Expired delegation → REJECTED"""
        # Create already-expired delegation
        expired_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        delegation = create_delegation_token(
            issuer_private_key_pem=self.issuer_private,
            issuer_id="issuer",
            subject_id="sender",
            allowed_actions=["send_email"],
            expires_at=expired_time,
        )
        instruction = self._make_instruction(token_id=delegation.token_id)
        result = self.verifier.verify(
            instruction=instruction,
            sender=self._sender_info(),
            receiver=self._receiver_info(),
            delegation_token=delegation,
            issuer_public_key=self.issuer_public,
        )
        assert result.accepted is False
        assert "expired" in result.rejection_reason.lower()

    def test_receiver_policy_rejected(self):
        """Action outside receiver's policy scope → REJECTED"""
        delegation = self._make_delegation(actions=["delete_database"])
        instruction = self._make_instruction(
            action="delete_database",
            token_id=delegation.token_id,
        )
        result = self.verifier.verify(
            instruction=instruction,
            sender=self._sender_info(),
            receiver=self._receiver_info(policy=["send_email"]),  # Doesn't allow delete
            delegation_token=delegation,
            issuer_public_key=self.issuer_public,
        )
        assert result.accepted is False
        assert "policy" in result.rejection_reason.lower()

    def test_reputation_below_threshold_rejected(self):
        """Low reputation score → REJECTED"""
        delegation = self._make_delegation()
        instruction = self._make_instruction(token_id=delegation.token_id)
        result = self.verifier.verify(
            instruction=instruction,
            sender=self._sender_info(),
            receiver=self._receiver_info(),
            delegation_token=delegation,
            issuer_public_key=self.issuer_public,
            sender_reputation_score=10.0,  # Below threshold
            reputation_threshold=50.0,
        )
        assert result.accepted is False
        assert "reputation" in result.rejection_reason.lower()


# ─── API Integration Tests ────────────────────────────────────────────

class TestAPIEndpoints:
    """Integration tests for the REST API."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")

    @pytest.mark.asyncio
    async def test_readiness_check(self, client: AsyncClient):
        resp = await client.get("/ready")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_register_agent(self, client: AsyncClient):
        resp = await client.post("/api/v1/agents/register", json={
            "name": "TestAgent",
            "description": "A test agent",
            "policy_scope": ["read_data"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["agent"]["name"] == "TestAgent"
        assert "private_key" in data
        assert "BEGIN PRIVATE KEY" in data["private_key"]

    @pytest.mark.asyncio
    async def test_duplicate_agent_rejected(self, client: AsyncClient):
        await client.post("/api/v1/agents/register", json={"name": "Dup"})
        resp = await client.post("/api/v1/agents/register", json={"name": "Dup"})
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_list_agents(self, client: AsyncClient, registered_agents):
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 200
        agents = resp.json()
        assert len(agents) >= 2

    @pytest.mark.asyncio
    async def test_full_flow_accepted(self, client: AsyncClient, delegation_setup):
        """Full end-to-end: sign → verify → ACCEPTED"""
        setup = delegation_setup
        agent_a = setup["agent_a"]
        agent_b = setup["agent_b"]
        delegation = setup["delegation"]

        # Sign instruction
        sign_resp = await client.post("/api/v1/instructions/sign", json={
            "sender_id": agent_a["agent"]["id"],
            "sender_private_key": agent_a["private_key"],
            "receiver_id": agent_b["agent"]["id"],
            "action": "send_email",
            "delegation_token_id": delegation["token_id"],
            "payload": {"to": "user@example.com"},
        })
        assert sign_resp.status_code == 200
        signed = sign_resp.json()

        # Verify instruction
        verify_resp = await client.post("/api/v1/instructions/verify", json={
            "instruction_id": signed["instruction_id"],
            "sender_id": signed["sender_id"],
            "receiver_id": signed["receiver_id"],
            "action": signed["action"],
            "payload": signed["payload"],
            "delegation_token_id": signed["delegation_token_id"],
            "timestamp": signed["timestamp"],
            "signature": signed["signature"],
        })
        assert verify_resp.status_code == 200
        result = verify_resp.json()
        assert result["accepted"] is True

    @pytest.mark.asyncio
    async def test_full_flow_revoked_rejected(self, client: AsyncClient, delegation_setup):
        """Full end-to-end: revoke → sign → verify → REJECTED"""
        setup = delegation_setup
        agent_a = setup["agent_a"]
        agent_b = setup["agent_b"]
        delegation = setup["delegation"]

        # Revoke Agent A
        revoke_resp = await client.post(
            f"/api/v1/agents/{agent_a['agent']['id']}/revoke",
            json={"reason": "Compromised agent simulation", "revoked_by": "admin"},
        )
        assert revoke_resp.status_code == 200

        # Sign instruction (still possible — signatures are client-side)
        sign_resp = await client.post("/api/v1/instructions/sign", json={
            "sender_id": agent_a["agent"]["id"],
            "sender_private_key": agent_a["private_key"],
            "receiver_id": agent_b["agent"]["id"],
            "action": "send_email",
            "delegation_token_id": delegation["token_id"],
        })
        assert sign_resp.status_code == 200
        signed = sign_resp.json()

        # Verify — should be REJECTED because agent is revoked
        verify_resp = await client.post("/api/v1/instructions/verify", json={
            "instruction_id": signed["instruction_id"],
            "sender_id": signed["sender_id"],
            "receiver_id": signed["receiver_id"],
            "action": signed["action"],
            "delegation_token_id": signed["delegation_token_id"],
            "timestamp": signed["timestamp"],
            "signature": signed["signature"],
        })
        assert verify_resp.status_code == 200
        result = verify_resp.json()
        assert result["accepted"] is False
        assert "revoked" in result["rejection_reason"].lower()

    @pytest.mark.asyncio
    async def test_audit_trail_recorded(self, client: AsyncClient, delegation_setup):
        """Verify that audit logs are created after verification."""
        setup = delegation_setup
        agent_a = setup["agent_a"]
        agent_b = setup["agent_b"]
        delegation = setup["delegation"]

        # Sign and verify
        sign_resp = await client.post("/api/v1/instructions/sign", json={
            "sender_id": agent_a["agent"]["id"],
            "sender_private_key": agent_a["private_key"],
            "receiver_id": agent_b["agent"]["id"],
            "action": "read_data",
            "delegation_token_id": delegation["token_id"],
        })
        signed = sign_resp.json()
        await client.post("/api/v1/instructions/verify", json={
            "instruction_id": signed["instruction_id"],
            "sender_id": signed["sender_id"],
            "receiver_id": signed["receiver_id"],
            "action": signed["action"],
            "delegation_token_id": signed["delegation_token_id"],
            "timestamp": signed["timestamp"],
            "signature": signed["signature"],
        })

        # Check audit logs
        logs_resp = await client.get("/api/v1/audit-logs")
        assert logs_resp.status_code == 200
        logs = logs_resp.json()
        assert len(logs) >= 1
        assert logs[0]["action"] == "read_data"

    @pytest.mark.asyncio
    async def test_dashboard_stats(self, client: AsyncClient):
        resp = await client.get("/api/v1/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert "total_agents" in stats
        assert "total_instructions" in stats
