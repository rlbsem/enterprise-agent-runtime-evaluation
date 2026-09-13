"""A durable observe/decide/authorize/act/verify loop with model-independent enforcement."""
import json
import time

import httpx
from pydantic import ValidationError

from .contracts import (Context, Decision, POLICY, POLICY_HASH, READS, Receipt, authorize,
                        canonical, digest, strict_json)
from .store import Store


class Engine:
    def __init__(self, store: Store, model, url, read_token, write_token, timeout=0.2, shadow=False):
        self.store, self.model, self.url = store, model, url.rstrip("/")
        self.read_token, self.write_token, self.timeout = read_token, write_token, timeout
        self.shadow = shadow

    def commit(self, run, kind, detail, **fields):
        with self.store.tx() as c:
            current = c.execute("SELECT lease FROM runs WHERE id=?", (run["id"],)).fetchone()
            if current["lease"] != run["lease"]:
                return False
            if fields:
                names = ",".join(k + "=?" for k in fields)
                c.execute(f"UPDATE runs SET {names} WHERE id=?", (*fields.values(), run["id"]))
            self.store.log(c, run["id"], kind, detail)
            return True

    def stop(self, run, reason, kind="guardrail"):
        self.commit(run, kind, {"reason": reason}, status="escalated", reason=reason)

    def advance(self, rid):
        run = self.store.claim(rid)
        if not run:
            return False
        try:
            if run["policy"] != POLICY_HASH:
                self.stop(run, "policy_changed")
                return True
            if time.time() - run["created"] > POLICY["max_seconds"]:
                self.stop(run, "time_budget_exhausted")
                return True
            with self.store.tx() as c:
                action = c.execute("SELECT * FROM actions WHERE run_id=? AND status='pending'", (rid,)).fetchone()
            if action:
                self.perform(run, dict(action))
                return True
            context = json.loads(run["context"])
            missing = [t for t in ("account", "usage", "support", "playbooks") if t not in context]
            if missing:
                critical = context.get("support", {}).get("data", {}).get("critical_tickets", 0)
                active = context.get("usage", {}).get("data", {}).get("active_percent", 100)
                topic = "incident" if critical else "adoption" if active < 40 else "renewal"
                d = Decision(kind="call", tool=missing[0], topic=topic, assessment="insufficient", claims=[])
                self.read(run, d, context)
                return True
            if not run["decision"]:
                self.reason(run)
            else:
                self.act(run)
            return True
        finally:
            with self.store.tx() as c:
                c.execute("UPDATE runs SET lease=NULL,lease_until=NULL WHERE id=? AND lease=?", (rid, run["lease"]))

    def reason(self, run):
        if run["calls"] >= POLICY["max_model_calls"]:
            self.stop(run, "model_call_budget_exhausted")
            return
        context = json.loads(run["context"])
        observation = {"objective": run["objective"], "context": context, "receipts": json.loads(run["receipts"]),
                       "call_index": run["calls"] + 1}
        if not self.commit(run, "model_request", {"input_hash": digest(observation), "call": run["calls"] + 1,
                                                  "mode": self.model.mode}, calls=run["calls"] + 1):
            return
        value = None
        try:
            raw, metadata = self.model.decide(observation)
            if len(raw) > 5000:
                raise ValueError("output_too_large")
            value = strict_json(raw)
            d = Decision.model_validate(value)
        except (ValidationError, ValueError, KeyError, TypeError):
            # Never persist unvalidated prose: an attempted credential dump is not a trace artifact.
            unsupported = isinstance(value, dict) and value.get("tool") not in READS | {"create_task", "request_escalation", "none"}
            self.commit(run, "model_rejected", {"reason": "invalid_model_contract", "unsupported_tool": unsupported},
                        status="escalated", reason="invalid_model_contract")
            return
        except httpx.HTTPError:
            self.commit(run, "model_unavailable", {"retry": "bounded_by_model_call_budget"}, retry_at=time.time() + 0.1)
            return
        decision = d.model_dump()
        history = json.loads(run["history"])
        if digest(decision) in history:
            self.stop(run, "repeated_decision")
            return
        self.commit(run, "model_decision", {"decision": decision, "provider": metadata},
                    decision=canonical(decision), history=canonical(history + [digest(decision)]))

    def act(self, run):
        d = Decision.model_validate(json.loads(run["decision"]))
        context = json.loads(run["context"])
        decision, reason = authorize(d, context, time.time())
        if not self.commit(run, "policy", {"decision": decision, "reason": reason, "policy": POLICY_HASH}):
            return
        if decision == "deny":
            self.stop(run, reason)
            return
        if d.kind == "abstain":
            self.commit(run, "final", {"assessment": "insufficient"}, status="abstained", reason="model_abstained")
            return
        if d.kind == "finish":
            completed = {r["effect"]["tool"] for r in json.loads(run["receipts"])}
            required = {"create_task"} if d.assessment == "risk" else set()
            if context["support"]["data"]["critical_tickets"] > 0:
                required.add("request_escalation")
            if not required <= completed:
                self.stop(run, "unverified_completion")
            else:
                self.commit(run, "final", {"assessment": d.assessment, "verified_tools": sorted(completed)},
                            status="completed", reason="verified_outcome")
            return
        if d.tool in READS:
            self.read(run, d, context)
            return
        payload = {"tenant": run["tenant"], "account": run["account"], "tool": d.tool, "topic": d.topic,
                   "versions": {k: v["revision"] for k, v in context.items()}, "policy": run["policy"]}
        if self.shadow:
            self.commit(run, "shadow_recommendation", {"payload": payload, "authoritative": False},
                        status="shadowed", reason="recommendation_only")
            return
        key = digest({"run": run["id"], "tool": d.tool})
        with self.store.tx() as c:
            if c.execute("SELECT lease FROM runs WHERE id=?", (run["id"],)).fetchone()["lease"] != run["lease"]:
                return
            existing = c.execute("SELECT * FROM actions WHERE key=?", (key,)).fetchone()
            if existing:
                self.store.log(c, run["id"], "guardrail", {"reason": "repeated_action"})
                c.execute("UPDATE runs SET status='escalated',reason='repeated_action' WHERE id=?", (run["id"],))
                return
            status = "approval" if decision == "approval" else "pending"
            c.execute("INSERT INTO actions(key,run_id,payload,hash,status) VALUES (?,?,?,?,?)",
                      (key, run["id"], canonical(payload), digest(payload), status))
            c.execute("UPDATE runs SET decision=NULL,status=? WHERE id=?",
                      ("awaiting_approval" if status == "approval" else "running", run["id"]))
            self.store.log(c, run["id"], "action_proposed", {"key": key, "payload": payload,
                                                            "hash": digest(payload), "approval_required": status == "approval"})

    def client(self, write=False):
        return httpx.Client(base_url=self.url, timeout=self.timeout, trust_env=False,
                            headers={"Authorization": "Bearer " + (self.write_token if write else self.read_token)})

    def read(self, run, d, context):
        try:
            with self.client() as c:
                r = c.get(f"/context/{run['tenant']}/{run['account']}/{d.tool}", params={"topic": d.topic})
                r.raise_for_status()
                value = Context.model_validate(r.json())
            if (value.tenant, value.account, value.source) != (run["tenant"], run["account"], d.tool):
                raise ValueError("scope_conflict")
            field = {"account": "renewal_days", "usage": "active_percent", "support": "critical_tickets"}.get(d.tool)
            if field and (type(value.data.get(field)) is not int or not 0 <= value.data[field] <= 10000):
                raise ValueError("bad_fact")
            allowed = {field, "crm_health_hint"} if d.tool == "account" else {field}
            if field and not value.data.keys() <= allowed:
                raise ValueError("unexpected_context_fields")
            if "crm_health_hint" in value.data and (not isinstance(value.data["crm_health_hint"], str)
                                                    or len(value.data["crm_health_hint"]) > 200):
                raise ValueError("invalid_account_note")
            if d.tool == "usage" and value.data[field] > 100:
                raise ValueError("bad_percentage")
            if len(canonical(value.data)) > 6000:
                raise ValueError("context_too_large")
            if d.tool == "playbooks" and not isinstance(value.data.get("documents"), list):
                raise ValueError("bad_documents")
            if d.tool == "playbooks":
                if set(value.data) != {"documents"} or len(value.data["documents"]) > 2:
                    raise ValueError("invalid_retrieval_envelope")
                for document in value.data["documents"]:
                    if (set(document) != {"id", "revision", "content", "content_hash"}
                            or not isinstance(document["content"], str) or len(document["content"]) > 1000
                            or digest(document["content"]) != document["content_hash"]):
                        raise ValueError("invalid_document")
        except (ValidationError, ValueError, KeyError, TypeError):
            self.stop(run, "invalid_tool_result")
            return
        except httpx.HTTPError:
            attempts = run["read_attempts"] + 1
            if attempts >= POLICY["max_read_attempts"]:
                self.stop(run, "read_retry_exhausted")
            else:
                self.commit(run, "tool_retry", {"tool": d.tool, "attempt": attempts},
                            read_attempts=attempts, retry_at=time.time() + 0.1)
            return
        context[d.tool] = value.model_dump()
        self.commit(run, "context", value.model_dump(), context=canonical(context), decision=None, read_attempts=0)

    def approve(self, rid, actor, accept, expected_hash):
        # Caller identity is supplied by the trusted CLI boundary, never by model output.
        if actor != "reviewer":
            raise PermissionError("reviewer_required")
        with self.store.tx() as c:
            run = c.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
            action = c.execute("SELECT * FROM actions WHERE run_id=? AND status='approval'", (rid,)).fetchone()
            if not action or run["status"] != "awaiting_approval":
                raise ValueError("no_pending_approval")
            if action["hash"] != expected_hash or run["policy"] != POLICY_HASH:
                raise ValueError("approval_binding_mismatch")
            until = time.time() + POLICY["approval_ttl"]
            c.execute("UPDATE actions SET status=?,approved_by=?,approved_until=?,approval_hash=? WHERE key=?",
                      ("pending" if accept else "rejected", actor, until, expected_hash, action["key"]))
            c.execute("UPDATE runs SET status=?,reason=? WHERE id=?",
                      ("running" if accept else "rejected", None if accept else "human_rejected", rid))
            self.store.log(c, rid, "approval", {"actor": actor, "accepted": accept, "hash": expected_hash, "expires": until})

    def perform(self, run, action):
        if self.shadow:
            self.stop(run, "shadow_cannot_resume_effect")
            return
        payload = json.loads(action["payload"])
        try:
            with self.client(write=True) as c:
                # Always reconcile a persisted intent; a process may have died after commit.
                if action["attempts"]:
                    response = c.get("/effects/" + action["key"])
                    if response.status_code == 200:
                        self.accept_receipt(run, action, response.json(), "reconciled")
                        return
                    if response.status_code != 404:
                        raise httpx.ReadError("reconciliation_unavailable")
                context = json.loads(run["context"])
                if any(time.time() - v["observed_at"] > POLICY["context_ttl"] for v in context.values()):
                    self.stop(run, "stale_context")
                    return
                if payload["tool"] == "request_escalation" and (
                    action["approved_by"] != "reviewer" or action["approval_hash"] != action["hash"]
                    or action["approved_until"] <= time.time()):
                    self.stop(run, "approval_invalid_or_expired")
                    return
                if action["attempts"] >= POLICY["max_effect_attempts"]:
                    self.stop(run, "effect_retry_exhausted")
                    return
                with self.store.tx() as tx:
                    if tx.execute("SELECT lease FROM runs WHERE id=?", (run["id"],)).fetchone()["lease"] != run["lease"]:
                        return
                    tx.execute("UPDATE actions SET attempts=attempts+1 WHERE key=?", (action["key"],))
                    self.store.log(tx, run["id"], "dispatch", {"key": action["key"], "attempt": action["attempts"] + 1})
                response = c.post("/effects", json=payload, headers={"Idempotency-Key": action["key"]})
                if response.status_code == 200:
                    self.accept_receipt(run, action, response.json(), "committed")
                elif response.status_code in (400, 401, 403, 409, 422):
                    self.stop(run, "remote_rejected_or_context_changed")
                else:
                    self.commit(run, "effect_retry", {"key": action["key"], "http_status": response.status_code},
                                retry_at=time.time() + (1 if response.status_code == 429 else 0.1))
        except (httpx.HTTPError, ValueError, ValidationError):
            self.commit(run, "uncertain_result", {"key": action["key"]}, retry_at=time.time() + 0.1)

    def accept_receipt(self, run, action, raw, outcome):
        value = Receipt.model_validate(raw).model_dump()
        if value["key"] != action["key"] or value["hash"] != action["hash"] or value["effect"] != json.loads(action["payload"]):
            self.stop(run, "receipt_identity_conflict")
            return
        with self.store.tx() as c:
            current = c.execute("SELECT lease,receipts FROM runs WHERE id=?", (run["id"],)).fetchone()
            if current["lease"] != run["lease"]:
                return
            receipts = json.loads(current["receipts"])
            if not any(r["key"] == value["key"] for r in receipts):
                receipts.append(value)
            c.execute("UPDATE actions SET status='succeeded',receipt=? WHERE key=?", (canonical(value), action["key"]))
            c.execute("UPDATE runs SET receipts=? WHERE id=?", (canonical(receipts), run["id"]))
            self.store.log(c, run["id"], "verified_receipt", {"outcome": outcome, "receipt": value})

    def drive(self, rid, reviewer=False):
        for _ in range(200):
            run = self.store.get(rid)
            if run["status"] == "awaiting_approval" and reviewer:
                with self.store.tx() as c:
                    action = c.execute("SELECT hash FROM actions WHERE run_id=? AND status='approval'", (rid,)).fetchone()
                self.approve(rid, "reviewer", True, action["hash"])
            elif run["status"] != "running":
                return run
            if not self.advance(rid):
                time.sleep(0.05)
        raise RuntimeError("driver_iteration_budget")
