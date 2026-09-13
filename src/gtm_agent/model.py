"""Actual local-model HTTP adapter and prominently separated synthetic test responders."""
import json
import os
from pathlib import Path

import httpx

from .contracts import Decision, POLICY, canonical, digest, strict_json

SYSTEM = Path(__file__).with_name("system.txt").read_text(encoding="utf-8")
PROMPT_HASH = digest(SYSTEM)


class LocalModel:
    mode = "live_local_llm"

    def __init__(self, url, seed=42, prompt=None):
        self.url, self.seed = url.rstrip("/"), seed
        self.prompt = prompt or SYSTEM

    def decide(self, observation):
        # Scenario labels and internal account identifiers never enter the model input.
        observation = json.loads(canonical(observation))
        for value in observation["context"].values():
            value["account"] = "account-under-review"
            value.pop("observed_at", None)
        schema = Decision.model_json_schema()
        completed = {r["effect"]["tool"] for r in observation["receipts"]}
        observation.pop("receipts")
        observation["completed_tools"] = sorted(completed)
        # A single operation avoids contradictory model fields such as kind=call/tool=none.
        schema["properties"].pop("kind")
        schema["properties"].pop("tool")
        schema["properties"]["operation"] = {"type": "string", "enum": sorted(
            {"create_task", "request_escalation", "finish", "abstain"} - completed)}
        schema["required"] = [k for k in schema["required"] if k not in ("kind", "tool")] + ["operation"]
        schema["properties"]["claims"]["minItems"] = 3
        schema["$defs"]["Claim"] = {"type": "object", "properties": {
            "fact": {"type": "string", "enum": ["account.renewal_days", "usage.active_percent", "support.critical_tickets"]},
            "value": {"type": "integer", "minimum": 0, "maximum": 10000}},
            "required": ["fact", "value"], "additionalProperties": False}
        payload = {"model": "local", "messages": [{"role": "system", "content": self.prompt},
                    {"role": "user", "content": canonical(observation)}], "temperature": 0.2,
                   "seed": self.seed, "max_tokens": POLICY["max_output_tokens"],
                   "response_format": {"type": "json_schema", "json_schema": {
                       "name": "next_decision", "strict": True, "schema": schema}}}
        if len(canonical(payload)) > 20000:
            raise ValueError("context_budget")
        with httpx.Client(timeout=120, trust_env=False,
                          headers={"Authorization": "Bearer " + os.environ.get("MODEL_API_KEY", "local-model-only")}) as c:
            r = c.post(self.url + "/v1/chat/completions", json=payload)
            r.raise_for_status()
            body = r.json()
        if body["choices"][0]["finish_reason"] != "stop":
            raise ValueError("incomplete_model_output")
        decision = strict_json(body["choices"][0]["message"]["content"])
        operation = decision.pop("operation")
        decision["kind"] = operation if operation in ("finish", "abstain") else "call"
        decision["tool"] = "none" if operation in ("finish", "abstain") else operation
        decision["claims"] = [{"source": c["fact"].split(".")[0], "field": c["fact"].split(".")[1],
                               "value": c["value"]} for c in decision["claims"]]
        # Validate the adapter's translation before it can enter the run trace.
        Decision.model_validate(decision)
        return canonical(decision), {
            "mode": self.mode, "model": str(body.get("model", "unknown")).replace("\\", "/").rsplit("/", 1)[-1], "usage": body.get("usage"),
            "seed": self.seed, "temperature": 0.2, "prompt_hash": digest(self.prompt),
            "input_hash": digest(payload), "structured_decoding": True}


class FixtureModel:
    """Handwritten responder for software tests. This is NOT an LLM or captured provider behavior."""
    mode = "synthetic_fixture"

    def decide(self, observation):
        context, receipts = observation["context"], observation["receipts"]
        critical = context.get("support", {}).get("data", {}).get("critical_tickets", 0)
        active = context.get("usage", {}).get("data", {}).get("active_percent", 100)
        topic = "incident" if critical else "adoption" if active < 40 else "renewal"
        d = {"kind": "call", "tool": "none", "topic": topic, "assessment": "insufficient", "claims": []}
        for tool in ("account", "usage", "support", "playbooks"):
            if tool not in context:
                d["tool"] = tool
                return canonical(d), {"mode": self.mode}
        days = context["account"]["data"]["renewal_days"]
        risk = critical > 0 or (active < 40 and days <= 60)
        d["claims"] = [{"source": source, "field": field, "value": value} for source, field, value in
                       [("account", "renewal_days", days), ("usage", "active_percent", active),
                        ("support", "critical_tickets", critical)]]
        completed = {r["effect"]["tool"] for r in receipts}
        d["assessment"] = "risk" if risk else "healthy" if active >= 60 else "insufficient"
        if risk and "create_task" not in completed:
            d["tool"] = "create_task"
        elif critical and "request_escalation" not in completed:
            d["tool"] = "request_escalation"
        else:
            d["kind"] = "abstain" if d["assessment"] == "insufficient" else "finish"
        return canonical(d), {"mode": self.mode}


class ScriptedModel:
    mode = "adversarial_fixture"

    def __init__(self, decisions):
        self.decisions = decisions

    def decide(self, observation):
        index = min(observation["call_index"] - 1, len(self.decisions) - 1)
        value = self.decisions[index]
        return value if isinstance(value, str) else json.dumps(value), {"mode": self.mode}
