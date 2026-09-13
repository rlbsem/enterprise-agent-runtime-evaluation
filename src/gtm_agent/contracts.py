import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Claim(Closed):
    source: Literal["account", "usage", "support"]
    field: Literal["renewal_days", "active_percent", "critical_tickets"]
    value: int = Field(ge=0, le=10000)


class Decision(Closed):
    kind: Literal["call", "finish", "abstain"]
    tool: Literal["account", "usage", "support", "playbooks", "create_task", "request_escalation", "none"]
    topic: Literal["renewal", "adoption", "incident"]
    assessment: Literal["risk", "healthy", "insufficient"]
    claims: list[Claim] = Field(max_length=3)


class Context(Closed):
    source: Literal["account", "usage", "support", "playbooks"]
    tenant: str
    account: str
    revision: int = Field(ge=1)
    observed_at: float
    data: dict


class Effect(Closed):
    tenant: str
    account: str
    tool: Literal["create_task", "request_escalation"]
    topic: Literal["renewal", "adoption", "incident"]
    versions: dict[str, int]
    policy: str


class Receipt(Closed):
    key: str
    hash: str
    effect: Effect


POLICY = {"version": "renewal-agent/1", "max_model_calls": 9, "max_seconds": 600,
          "context_ttl": 120, "approval_ttl": 120, "max_effect_attempts": 3,
          "max_read_attempts": 3, "max_output_tokens": 320}
POLICY_HASH = digest(POLICY)
READS = {"account", "usage", "support", "playbooks"}
WRITES = {"create_task", "request_escalation"}


def grounded(decision, context):
    if len({(v.source, v.field) for v in decision.claims}) != len(decision.claims):
        return False
    owners = {"renewal_days": "account", "active_percent": "usage", "critical_tickets": "support"}
    return all(owners[v.field] == v.source and context.get(v.source, {}).get("data", {}).get(v.field) == v.value
               for v in decision.claims)


def authorize(decision, context, now):
    if not grounded(decision, context):
        return "deny", "ungrounded_claim"
    if decision.kind == "abstain":
        return "allow", "safe_abstention"
    if decision.kind == "call" and decision.tool in READS:
        return "allow", "scoped_read"
    if not READS <= context.keys():
        return "deny", "missing_context"
    if any(now - context[t]["observed_at"] > POLICY["context_ttl"] for t in READS):
        return "deny", "stale_context"
    if not context["playbooks"]["data"].get("documents"):
        return "deny", "no_approved_playbook"
    critical = context["support"]["data"]["critical_tickets"]
    active = context["usage"]["data"]["active_percent"]
    renewal = context["account"]["data"]["renewal_days"]
    risk = critical > 0 or (active < 40 and renewal <= 60)
    if decision.assessment == "healthy" and (risk or active < 60):
        return "deny", "evidence_contradiction"
    if decision.assessment == "risk" and not risk:
        return "deny", "evidence_contradiction"
    if decision.kind == "finish":
        if {v.field for v in decision.claims} != {"renewal_days", "active_percent", "critical_tickets"}:
            return "deny", "missing_final_evidence"
        return ("allow", "grounded_finish") if decision.tool == "none" else ("deny", "invalid_finish")
    if decision.tool not in WRITES or decision.assessment != "risk":
        return "deny", "unsupported_action"
    if {v.field for v in decision.claims} != {"renewal_days", "active_percent", "critical_tickets"}:
        return "deny", "missing_action_evidence"
    if decision.topic == "incident" and critical == 0:
        return "deny", "wrong_tool_arguments"
    if decision.topic == "adoption" and not (active < 40 and renewal <= 60):
        return "deny", "wrong_tool_arguments"
    if decision.tool == "request_escalation":
        return ("approval", "human_required") if critical else ("deny", "escalation_not_justified")
    return "allow", "grounded_internal_task"
