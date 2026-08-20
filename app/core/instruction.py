"""
Signed instruction creation and serialization.

When Agent A sends a task to Agent B, it:
1. Constructs an instruction with action + payload
2. Serializes it canonically (deterministic JSON)
3. Signs it with Agent A's private key
4. Includes the delegation token ID
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

from app.core.crypto import canonical_json, sign_message


class InstructionPayload(BaseModel):
    """The content of an instruction before signing."""
    sender_id: str
    receiver_id: str
    action: str
    payload: Optional[dict] = None
    delegation_token_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    instruction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class SignedInstruction(BaseModel):
    """A fully signed instruction ready for transmission."""
    instruction_id: str
    sender_id: str
    receiver_id: str
    action: str
    payload: Optional[dict] = None
    delegation_token_id: str
    timestamp: str
    signature: str


def create_signed_instruction(
    private_key_pem: str,
    sender_id: str,
    receiver_id: str,
    action: str,
    delegation_token_id: str,
    payload: Optional[dict] = None,
) -> SignedInstruction:
    """
    Create and sign an instruction.

    Args:
        private_key_pem: Sender's Ed25519 private key (PEM).
        sender_id: ID of the sending agent.
        receiver_id: ID of the receiving agent.
        action: The action being instructed.
        delegation_token_id: ID of the delegation token authorizing this.
        payload: Optional additional data for the instruction.

    Returns:
        A SignedInstruction with a valid Ed25519 signature.
    """
    instruction = InstructionPayload(
        sender_id=sender_id,
        receiver_id=receiver_id,
        action=action,
        payload=payload,
        delegation_token_id=delegation_token_id,
    )

    # Serialize canonically for signing
    signing_data = _get_signing_data(instruction)
    signature = sign_message(private_key_pem, signing_data)

    return SignedInstruction(
        instruction_id=instruction.instruction_id,
        sender_id=instruction.sender_id,
        receiver_id=instruction.receiver_id,
        action=instruction.action,
        payload=instruction.payload,
        delegation_token_id=instruction.delegation_token_id,
        timestamp=instruction.timestamp,
        signature=signature,
    )


def _get_signing_data(instruction: InstructionPayload) -> bytes:
    """
    Get the canonical bytes that are signed.

    Only signs the security-critical fields to prevent tampering.
    """
    signing_dict = {
        "instruction_id": instruction.instruction_id,
        "sender_id": instruction.sender_id,
        "receiver_id": instruction.receiver_id,
        "action": instruction.action,
        "delegation_token_id": instruction.delegation_token_id,
        "timestamp": instruction.timestamp,
    }
    if instruction.payload is not None:
        signing_dict["payload"] = instruction.payload
    return canonical_json(signing_dict)


def get_instruction_signing_bytes(signed_instruction: SignedInstruction) -> bytes:
    """
    Reconstruct the signing bytes from a signed instruction
    for verification purposes.
    """
    signing_dict = {
        "instruction_id": signed_instruction.instruction_id,
        "sender_id": signed_instruction.sender_id,
        "receiver_id": signed_instruction.receiver_id,
        "action": signed_instruction.action,
        "delegation_token_id": signed_instruction.delegation_token_id,
        "timestamp": signed_instruction.timestamp,
    }
    if signed_instruction.payload is not None:
        signing_dict["payload"] = signed_instruction.payload
    return canonical_json(signing_dict)
