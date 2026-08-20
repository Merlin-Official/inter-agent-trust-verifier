"""
LLM Policy Analysis Integration (OpenAI).

IMPORTANT: The LLM does NOT make security decisions.
The deterministic trust engine makes all accept/reject decisions.

The LLM provides:
1. Natural language explanations of why instructions were accepted/rejected
2. Translation of natural-language policies into structured rules
3. Risk analysis for audit reporting

This is far more defensible in production than letting an LLM make security calls.
"""

from typing import Optional
from openai import AsyncOpenAI
from app.config import get_settings

settings = get_settings()


class LLMPolicyAnalyzer:
    """
    Uses OpenAI to provide natural language analysis and explanations.
    Falls back gracefully if the API key is not configured.
    """

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your-openai-api-key-here":
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    @property
    def is_available(self) -> bool:
        return self._client is not None

    async def explain_verification(
        self,
        action: str,
        sender_name: str,
        receiver_name: str,
        outcome: str,
        reason: Optional[str],
        checks_passed: list,
        checks_failed: list,
    ) -> str:
        """
        Generate a natural language explanation of a verification outcome.

        This is for audit reporting — not for security decisions.
        """
        if not self.is_available:
            return self._fallback_explanation(
                action, sender_name, receiver_name, outcome, reason
            )

        try:
            prompt = f"""You are an AI security auditor. Explain the following inter-agent trust verification outcome in 2-3 concise sentences for an audit report.

Instruction: Agent "{sender_name}" requested Agent "{receiver_name}" to perform action "{action}"
Outcome: {outcome}
{f'Reason: {reason}' if reason else ''}
Checks Passed: {', '.join(checks_passed) if checks_passed else 'None'}
Checks Failed: {', '.join(checks_failed) if checks_failed else 'None'}

Provide a clear, professional explanation suitable for a security audit log."""

            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return self._fallback_explanation(
                action, sender_name, receiver_name, outcome, reason
            )

    async def analyze_policy_compliance(
        self,
        action: str,
        policy_description: str,
        sender_name: str,
    ) -> dict:
        """
        Analyze whether an action complies with a natural language policy.

        Returns a structured assessment (not a security decision).
        Used for enhanced audit reporting when heightened scrutiny is triggered.
        """
        if not self.is_available:
            return {
                "analysis": "LLM analysis unavailable — using rule-based checks only",
                "risk_level": "unknown",
                "recommendation": "Rely on deterministic verification checks",
            }

        try:
            prompt = f"""You are an AI governance analyst. Analyze whether the following action complies with the stated policy.

Action: "{action}" (requested by agent "{sender_name}")
Policy: {policy_description}

Return a JSON object with:
- "analysis": brief analysis (1-2 sentences)
- "risk_level": "low", "medium", or "high"
- "recommendation": brief recommendation (1 sentence)

Be concise and professional."""

            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            import json
            return json.loads(response.choices[0].message.content.strip())
        except Exception:
            return {
                "analysis": "LLM analysis failed — using rule-based checks only",
                "risk_level": "unknown",
                "recommendation": "Rely on deterministic verification checks",
            }

    def _fallback_explanation(
        self,
        action: str,
        sender_name: str,
        receiver_name: str,
        outcome: str,
        reason: Optional[str],
    ) -> str:
        """Fallback explanation when LLM is unavailable."""
        if outcome == "ACCEPTED":
            return (
                f"Instruction from '{sender_name}' to '{receiver_name}' for action "
                f"'{action}' was ACCEPTED. All deterministic trust verification "
                f"checks passed successfully."
            )
        else:
            return (
                f"Instruction from '{sender_name}' to '{receiver_name}' for action "
                f"'{action}' was REJECTED. Reason: {reason or 'Unknown'}."
            )


# Global singleton
llm_analyzer = LLMPolicyAnalyzer()
