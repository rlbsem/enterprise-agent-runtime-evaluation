import json

import httpx

from gtm_agent.model import LocalModel


def test_provider_projection_excludes_scenario_labels_clocks_and_receipt_nonces(monkeypatch):
    captured = []
    output = {"operation": "finish", "assessment": "healthy", "topic": "renewal", "claims": [
        {"fact": "account.renewal_days", "value": 45}, {"fact": "usage.active_percent", "value": 85},
        {"fact": "support.critical_tickets", "value": 0}]}
    def post(self, url, json):
        captured.append(json)
        return httpx.Response(200, request=httpx.Request("POST", url), json={"model": "synthetic-provider-contract",
            "choices": [{"finish_reason": "stop", "message": {"content": __import__('json').dumps(output)}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1}})
    monkeypatch.setattr(httpx.Client, "post", post)
    observation = {"objective": "Review account", "context": {"account": {"account": "hidden-case-label", "observed_at": 1.234,
                   "data": {"renewal_days": 45}}}, "receipts": [{"key": "random-nonce", "effect": {"tool": "create_task"}}], "call_index": 1}
    raw, metadata = LocalModel("http://127.0.0.1:9999").decide(observation)
    user_input = captured[0]["messages"][1]["content"]
    assert "hidden-case-label" not in user_input and "observed_at" not in user_input and "random-nonce" not in user_input
    assert json.loads(user_input)["completed_tools"] == ["create_task"]
    assert json.loads(raw)["kind"] == "finish" and metadata["usage"]["completion_tokens"] == 1
